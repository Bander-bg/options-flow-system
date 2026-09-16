from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import weekly.db.database as dbmod
from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import Direction, GateStatus, SignalState
from weekly.domain.models import Signal, SignalFeature
from weekly.services.earnings_event_risk_evaluation_service import (
    EarningsEventRiskEvaluationService,
)
from weekly.services.earnings_event_risk_service import (
    EarningsEventRiskService,
)


def h(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    prod = dbmod.get_database_path().resolve()
    if not prod.exists():
        raise RuntimeError(f"Production database not found: {prod}")

    before = h(prod)

    with tempfile.TemporaryDirectory(
        prefix="weekly_earnings_eval_test_"
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

            trading_date = date(2099, 1, 5)
            expiry = date(2099, 1, 9)

            seq = sr.next_candidate_sequence(
                strategy_version="weekly_v1",
                ticker="AAPL",
                trading_date_et=trading_date,
                target_expiry=expiry,
                direction=Direction.BULLISH,
            )

            sig = sr.create(
                Signal(
                    strategy_version="weekly_v1",
                    config_hash="earnings-eval-temp-test",
                    ticker="AAPL",
                    trading_date_et=trading_date,
                    target_expiry=expiry,
                    direction=Direction.BULLISH,
                    candidate_sequence=seq,
                    state=SignalState.CANDIDATE,
                    candidate_at=datetime(
                        2099, 1, 5, 14, 35,
                        tzinfo=timezone.utc,
                    ),
                    net_flow_at_candidate=650000.0,
                    flow_dedup_level="alert_uuid",
                    stock_data_provider="ALPACA",
                    stock_data_feed="IEX",
                    options_data_provider="ALPACA",
                    options_data_feed="INDICATIVE",
                    scenario_return_enabled=False,
                )
            )

            prior = fr.create(
                SignalFeature(
                    signal_id=sig.id,
                    evaluation_sequence=1,
                    captured_at=datetime(
                        2099, 1, 5, 14, 50,
                        tzinfo=timezone.utc,
                    ),
                    flow_net=650000.0,
                    flow_threshold=500000.0,
                    weekly_vwap=198.0,
                    underlying_price=200.0,
                    vwap_status=GateStatus.PASS,
                    efficiency_ratio=0.55,
                    efficiency_ratio_status=GateStatus.PASS,
                    expected_move=10.0,
                    expected_move_perc=0.05,
                    eligible_contract_status=GateStatus.PASS,
                    structure_status=GateStatus.PASS,
                    impulse_status=GateStatus.FAIL,
                    participation_status=GateStatus.PASS,
                    price_action_pass_count=2,
                    price_action_status=GateStatus.PASS,
                    atr_1h=3.25,
                    atr_15m=2.25,
                )
            )

            svc = EarningsEventRiskEvaluationService(
                earnings_event_risk_service=EarningsEventRiskService(),
                feature_repository=fr,
            )

            ev = svc.evaluate_and_persist(
                signal_id=sig.id,
                trading_date_et=trading_date,
                target_expiry=expiry,
                next_earnings_date=date(2099, 1, 20),
                earnings_time="AMC",
                captured_at=datetime(
                    2099, 1, 5, 15, 1,
                    tzinfo=timezone.utc,
                ),
            )

            f = ev.feature

            assert ev.result.status is GateStatus.PASS
            assert ev.result.reason == "EARNINGS_AFTER_TARGET_EXPIRY"

            assert f.id is not None
            assert f.id != prior.id
            assert f.evaluation_sequence == 2

            assert f.next_earnings_date == date(2099, 1, 20)
            assert f.earnings_event_risk_status is GateStatus.PASS

            assert f.flow_net == 650000.0
            assert f.flow_threshold == 500000.0
            assert f.weekly_vwap == 198.0
            assert f.underlying_price == 200.0
            assert f.vwap_status is GateStatus.PASS
            assert f.efficiency_ratio == 0.55
            assert f.efficiency_ratio_status is GateStatus.PASS
            assert f.expected_move == 10.0
            assert f.expected_move_perc == 0.05
            assert f.eligible_contract_status is GateStatus.PASS
            assert f.structure_status is GateStatus.PASS
            assert f.impulse_status is GateStatus.FAIL
            assert f.participation_status is GateStatus.PASS
            assert f.price_action_pass_count == 2
            assert f.price_action_status is GateStatus.PASS
            assert f.atr_1h == 3.25
            assert f.atr_15m == 2.25

            latest = fr.get_latest_for_signal(sig.id)
            assert latest is not None
            assert latest.id == f.id
            assert latest.next_earnings_date == date(2099, 1, 20)
            assert (
                latest.earnings_event_risk_status
                is GateStatus.PASS
            )

            reloaded = sr.get_by_id(sig.id)
            assert reloaded is not None
            assert reloaded.state is SignalState.CANDIDATE

        finally:
            dbmod.get_database_path = old

    assert before == h(prod)

    print("1. temporary database copy: PASS")
    print("2. earnings Hard Gate PASS persisted: PASS")
    print("3. next earnings date persisted: PASS")
    print("4. evaluation_sequence incremented: PASS")
    print("5. unrelated Flow/Regime/ExpectedMove/Contract/PA/ATR preserved: PASS")
    print("6. latest SignalFeature reload: PASS")
    print("7. Signal state unchanged: PASS")
    print("8. production database unchanged: PASS")
    print()
    print("=" * 70)
    print("EARNINGS EVENT RISK EVALUATION SERVICE: PASS 8/8")
    print("=" * 70)


if __name__ == "__main__":
    main()