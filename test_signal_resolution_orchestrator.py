from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import weekly.db.database as dbmod
from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import Direction, GateStatus, SignalState
from weekly.domain.models import Signal, SignalFeature
from weekly.services.signal_resolution_orchestrator import (
    SignalResolutionOrchestrator,
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_signal(
    repo: SignalRepository,
    *,
    sequence: int,
    candidate_at: datetime,
    deadline: datetime,
) -> Signal:
    return repo.create(
        Signal(
            strategy_version="weekly_v1",
            config_hash="orchestrator-temp-test",
            ticker="AAPL",
            trading_date_et=date(2099, 1, 5),
            target_expiry=date(2099, 1, 9),
            direction=Direction.BULLISH,
            candidate_sequence=sequence,
            state=SignalState.CANDIDATE,
            candidate_at=candidate_at,
            requested_confirmation_deadline_at=deadline,
            confirmation_deadline_at=deadline,
            net_flow_at_candidate=650000.0,
            flow_dedup_level="alert_uuid",
            stock_data_provider="ALPACA",
            stock_data_feed="IEX",
            options_data_provider="ALPACA",
            options_data_feed="INDICATIVE",
            scenario_return_enabled=False,
        )
    )


def feature(
    *,
    signal_id: int,
    sequence: int,
    captured_at: datetime,
    bar_at: datetime,
    pa_status: GateStatus,
) -> SignalFeature:
    return SignalFeature(
        signal_id=signal_id,
        evaluation_sequence=sequence,
        captured_at=captured_at,
        vwap_status=GateStatus.PASS,
        efficiency_ratio_status=GateStatus.PASS,
        eligible_contract_status=GateStatus.PASS,
        earnings_event_risk_status=GateStatus.PASS,
        price_action_bar_at=bar_at,
        price_action_status=pa_status,
    )


def main() -> None:
    prod = dbmod.get_database_path().resolve()
    if not prod.exists():
        raise RuntimeError(f"Production database not found: {prod}")

    before = sha256(prod)

    with tempfile.TemporaryDirectory(
        prefix="weekly_resolution_orchestrator_test_"
    ) as td:
        temp_db = Path(td) / "weekly_trading_test.db"

        src = sqlite3.connect(f"{prod.as_uri()}?mode=ro", uri=True)
        dst = sqlite3.connect(temp_db)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        old = dbmod.get_database_path
        dbmod.get_database_path = lambda: temp_db

        try:
            sr = SignalRepository()
            fr = SignalFeatureRepository()

            svc = SignalResolutionOrchestrator(
                signal_repository=sr,
                feature_repository=fr,
            )

            base = datetime(
                2099, 1, 5, 14, 30,
                tzinfo=timezone.utc,
            )
            deadline = base + timedelta(minutes=30)

            # ------------------------------------------
            # 1) Window open + PA FAIL -> DATA_BLOCKED
            # ------------------------------------------

            s1 = create_signal(
                sr,
                sequence=sr.next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker="AAPL",
                    trading_date_et=date(2099, 1, 5),
                    target_expiry=date(2099, 1, 9),
                    direction=Direction.BULLISH,
                ),
                candidate_at=base,
                deadline=deadline,
            )

            fr.create(
                feature(
                    signal_id=s1.id,
                    sequence=1,
                    captured_at=base + timedelta(minutes=16),
                    bar_at=base + timedelta(minutes=15),
                    pa_status=GateStatus.FAIL,
                )
            )

            r1 = svc.resolve_and_persist(
                signal_id=s1.id,
                as_of=base + timedelta(minutes=20),
                invalidated=False,
            )

            assert r1.price_action_confirmation.status is GateStatus.UNKNOWN
            assert r1.price_action_confirmation.is_final is False
            assert r1.hard_gate_result.status is GateStatus.UNKNOWN
            assert r1.transition.signal.state is SignalState.DATA_BLOCKED

            # ------------------------------------------
            # 2) Later PA PASS -> CONFIRMED
            # ------------------------------------------

            fr.create(
                feature(
                    signal_id=s1.id,
                    sequence=2,
                    captured_at=base + timedelta(minutes=29),
                    bar_at=base + timedelta(minutes=28),
                    pa_status=GateStatus.PASS,
                )
            )

            r2 = svc.resolve_and_persist(
                signal_id=s1.id,
                as_of=base + timedelta(minutes=29),
                invalidated=False,
                net_flow_at_confirmation=725000.0,
            )

            assert r2.price_action_confirmation.status is GateStatus.PASS
            assert r2.price_action_confirmation.is_final is True
            assert r2.hard_gate_result.status is GateStatus.PASS
            assert r2.transition.signal.state is SignalState.CONFIRMED
            assert r2.transition.signal.net_flow_at_confirmation == 725000.0

            # ------------------------------------------
            # 3) Closed window + final PA FAIL -> REJECTED
            # ------------------------------------------

            s2 = create_signal(
                sr,
                sequence=sr.next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker="AAPL",
                    trading_date_et=date(2099, 1, 5),
                    target_expiry=date(2099, 1, 9),
                    direction=Direction.BULLISH,
                ),
                candidate_at=base + timedelta(minutes=1),
                deadline=deadline + timedelta(minutes=1),
            )

            fr.create(
                feature(
                    signal_id=s2.id,
                    sequence=1,
                    captured_at=base + timedelta(minutes=17),
                    bar_at=base + timedelta(minutes=16),
                    pa_status=GateStatus.FAIL,
                )
            )

            r3 = svc.resolve_and_persist(
                signal_id=s2.id,
                as_of=deadline + timedelta(minutes=1),
                invalidated=False,
            )

            assert r3.price_action_confirmation.status is GateStatus.FAIL
            assert r3.price_action_confirmation.is_final is True
            assert r3.hard_gate_result.status is GateStatus.FAIL
            assert r3.transition.signal.state is SignalState.REJECTED

            # ------------------------------------------
            # 4) INVALIDATED has highest precedence
            # ------------------------------------------

            s3 = create_signal(
                sr,
                sequence=sr.next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker="AAPL",
                    trading_date_et=date(2099, 1, 5),
                    target_expiry=date(2099, 1, 9),
                    direction=Direction.BULLISH,
                ),
                candidate_at=base + timedelta(minutes=2),
                deadline=deadline + timedelta(minutes=2),
            )

            r4 = svc.resolve_and_persist(
                signal_id=s3.id,
                as_of=base + timedelta(minutes=10),
                invalidated=True,
            )

            assert r4.hard_gate_result.status is GateStatus.UNKNOWN
            assert r4.transition.signal.state is SignalState.INVALIDATED

            # ------------------------------------------
            # Reload persistence
            # ------------------------------------------

            confirmed = sr.get_by_id(s1.id)
            rejected = sr.get_by_id(s2.id)
            invalidated = sr.get_by_id(s3.id)

            assert confirmed is not None
            assert confirmed.state is SignalState.CONFIRMED
            assert rejected is not None
            assert rejected.state is SignalState.REJECTED
            assert invalidated is not None
            assert invalidated.state is SignalState.INVALIDATED

        finally:
            dbmod.get_database_path = old

    assert before == sha256(prod)

    print("1. full SignalFeature history loaded: PASS")
    print("2. open-window PA FAIL remains non-final UNKNOWN: PASS")
    print("3. UNKNOWN Hard Gates -> DATA_BLOCKED: PASS")
    print("4. later PA PASS -> final PASS: PASS")
    print("5. all Hard Gates PASS -> CONFIRMED: PASS")
    print("6. confirmation flow persisted: PASS")
    print("7. closed-window final PA FAIL -> REJECTED: PASS")
    print("8. INVALIDATED precedence preserved: PASS")
    print("9. persisted Signal states reload correctly: PASS")
    print("10. production database unchanged: PASS")
    print()
    print("=" * 70)
    print("SIGNAL RESOLUTION ORCHESTRATOR: PASS 10/10")
    print("=" * 70)


if __name__ == "__main__":
    main()