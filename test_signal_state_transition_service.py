from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import weekly.db.database as dbmod
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import Direction, GateStatus, SignalState
from weekly.domain.models import Signal
from weekly.services.hard_gate_service import HardGateResult
from weekly.services.signal_state_transition_service import SignalStateTransitionService


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hard_gate(status: GateStatus) -> HardGateResult:
    if status is GateStatus.PASS:
        gate = GateStatus.PASS
        failed = ()
        unknown = ()
        reason = "ALL_HARD_GATES_PASS"
    elif status is GateStatus.FAIL:
        gate = GateStatus.PASS
        failed = ("VWAP",)
        unknown = ()
        reason = "HARD_GATE_FAIL"
    else:
        gate = GateStatus.UNKNOWN
        failed = ()
        unknown = ("VWAP",)
        reason = "HARD_GATE_UNKNOWN"

    return HardGateResult(
        status=status,
        vwap_status=GateStatus.FAIL if status is GateStatus.FAIL else gate,
        efficiency_ratio_status=gate,
        price_action_status=gate,
        eligible_contract_status=gate,
        earnings_event_risk_status=gate,
        failed_gates=failed,
        unknown_gates=unknown,
        price_action_is_final=True,
        price_action_reason="TEST",
        reason=reason,
    )


def create_signal(
    repo: SignalRepository,
    *,
    candidate_sequence: int,
    candidate_at: datetime,
) -> Signal:
    trading_date = date(2099, 1, 5)
    expiry = date(2099, 1, 9)

    return repo.create(
        Signal(
            strategy_version="weekly_v1",
            config_hash="state-transition-temp-test",
            ticker="AAPL",
            trading_date_et=trading_date,
            target_expiry=expiry,
            direction=Direction.BULLISH,
            candidate_sequence=candidate_sequence,
            state=SignalState.CANDIDATE,
            candidate_at=candidate_at,
            net_flow_at_candidate=650000.0,
            flow_dedup_level="alert_uuid",
            stock_data_provider="ALPACA",
            stock_data_feed="IEX",
            options_data_provider="ALPACA",
            options_data_feed="INDICATIVE",
            scenario_return_enabled=False,
        )
    )


def main() -> None:
    prod = dbmod.get_database_path().resolve()
    if not prod.exists():
        raise RuntimeError(f"Production database not found: {prod}")

    before = sha256(prod)

    with tempfile.TemporaryDirectory(prefix="weekly_state_transition_test_") as td:
        temp_db = Path(td) / "weekly_trading_test.db"

        src = sqlite3.connect(f"{prod.as_uri()}?mode=ro", uri=True)
        dst = sqlite3.connect(temp_db)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        original_get_database_path = dbmod.get_database_path
        dbmod.get_database_path = lambda: temp_db

        try:
            repo = SignalRepository()
            svc = SignalStateTransitionService(signal_repository=repo)

            base_at = datetime(2099, 1, 5, 14, 35, tzinfo=timezone.utc)

            s1 = create_signal(
                repo,
                candidate_sequence=repo.next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker="AAPL",
                    trading_date_et=date(2099, 1, 5),
                    target_expiry=date(2099, 1, 9),
                    direction=Direction.BULLISH,
                ),
                candidate_at=base_at,
            )
            confirmed_at = base_at + timedelta(minutes=20)

            r1 = svc.resolve_and_persist(
                signal=s1,
                hard_gate_result=hard_gate(GateStatus.PASS),
                invalidated=False,
                resolution_window_closed=False,
                resolved_at=confirmed_at,
                net_flow_at_confirmation=725000.0,
            )

            assert r1.persisted is True
            assert r1.signal.state is SignalState.CONFIRMED
            assert r1.signal.confirmed_at == confirmed_at
            assert r1.signal.net_flow_at_confirmation == 725000.0
            assert r1.signal.terminal_at is None
            assert r1.signal.terminal_reason is None

            s2 = create_signal(
                repo,
                candidate_sequence=repo.next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker="AAPL",
                    trading_date_et=date(2099, 1, 5),
                    target_expiry=date(2099, 1, 9),
                    direction=Direction.BULLISH,
                ),
                candidate_at=base_at + timedelta(minutes=1),
            )
            rejected_at = base_at + timedelta(minutes=25)

            r2 = svc.resolve_and_persist(
                signal=s2,
                hard_gate_result=hard_gate(GateStatus.FAIL),
                invalidated=False,
                resolution_window_closed=False,
                resolved_at=rejected_at,
                net_flow_at_confirmation=999999.0,
            )

            assert r2.persisted is True
            assert r2.signal.state is SignalState.REJECTED
            assert r2.signal.terminal_at == rejected_at
            assert r2.signal.terminal_reason == "HARD_GATE_FAIL"
            assert r2.signal.confirmed_at is None
            assert r2.signal.net_flow_at_confirmation is None

            s3 = create_signal(
                repo,
                candidate_sequence=repo.next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker="AAPL",
                    trading_date_et=date(2099, 1, 5),
                    target_expiry=date(2099, 1, 9),
                    direction=Direction.BULLISH,
                ),
                candidate_at=base_at + timedelta(minutes=2),
            )

            r3 = svc.resolve_and_persist(
                signal=s3,
                hard_gate_result=hard_gate(GateStatus.UNKNOWN),
                invalidated=False,
                resolution_window_closed=False,
                resolved_at=base_at + timedelta(minutes=10),
            )

            assert r3.persisted is True
            assert r3.signal.state is SignalState.DATA_BLOCKED
            assert r3.signal.confirmed_at is None
            assert r3.signal.terminal_at is None
            assert r3.signal.terminal_reason is None

            r4 = svc.resolve_and_persist(
                signal=r3.signal,
                hard_gate_result=hard_gate(GateStatus.PASS),
                invalidated=False,
                resolution_window_closed=False,
                resolved_at=base_at + timedelta(minutes=28),
                net_flow_at_confirmation=810000.0,
            )

            assert r4.persisted is True
            assert r4.signal.state is SignalState.CONFIRMED
            assert r4.signal.confirmed_at == base_at + timedelta(minutes=28)
            assert r4.signal.net_flow_at_confirmation == 810000.0

            locked = svc.resolve_and_persist(
                signal=r1.signal,
                hard_gate_result=hard_gate(GateStatus.FAIL),
                invalidated=True,
                resolution_window_closed=True,
                resolved_at=base_at + timedelta(minutes=40),
            )

            assert locked.persisted is False
            assert locked.signal.state is SignalState.CONFIRMED

            reloaded = repo.get_by_id(r1.signal.id)
            assert reloaded is not None
            assert reloaded.state is SignalState.CONFIRMED
            assert reloaded.confirmed_at == confirmed_at
            assert reloaded.net_flow_at_confirmation == 725000.0

        finally:
            dbmod.get_database_path = original_get_database_path

    assert before == sha256(prod)

    print("1. temporary database copy: PASS")
    print("2. CANDIDATE -> CONFIRMED persisted: PASS")
    print("3. confirmed_at + confirmation flow persisted: PASS")
    print("4. Hard FAIL -> REJECTED + terminal metadata persisted: PASS")
    print("5. confirmation-only fields excluded from REJECTED: PASS")
    print("6. UNKNOWN -> DATA_BLOCKED persisted without terminal metadata: PASS")
    print("7. DATA_BLOCKED re-evaluated -> CONFIRMED: PASS")
    print("8. locked CONFIRMED state causes no write: PASS")
    print("9. persisted signal reload matches expected state: PASS")
    print("10. production database unchanged: PASS")
    print()
    print("=" * 70)
    print("SIGNAL STATE TRANSITION SERVICE: PASS 10/10")
    print("=" * 70)


if __name__ == "__main__":
    main()

