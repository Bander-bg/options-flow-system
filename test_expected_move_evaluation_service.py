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
from weekly.services.expected_move_evaluation_service import (
    ExpectedMoveEvaluationService,
)
from weekly.services.expected_move_service import ExpectedMoveService


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    prod = dbmod.get_database_path().resolve()
    if not prod.exists():
        raise RuntimeError(f"Production database not found: {prod}")

    before = sha256_file(prod)

    with tempfile.TemporaryDirectory(
        prefix="weekly_expected_move_eval_test_"
    ) as td:
        temp_db = Path(td) / "weekly_trading_test.db"

        src = sqlite3.connect(
            f"{prod.as_uri()}?mode=ro",
            uri=True,
        )
        dst = sqlite3.connect(temp_db)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        original_get_database_path = dbmod.get_database_path
        dbmod.get_database_path = lambda: temp_db

        try:
            signal_repository = SignalRepository()
            feature_repository = SignalFeatureRepository()

            trading_date = date(2099, 1, 5)
            target_expiry = date(2099, 1, 9)

            candidate_sequence = (
                signal_repository.next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker="AAPL",
                    trading_date_et=trading_date,
                    target_expiry=target_expiry,
                    direction=Direction.BULLISH,
                )
            )

            signal = signal_repository.create(
                Signal(
                    strategy_version="weekly_v1",
                    config_hash="expected-move-eval-temp-test",
                    ticker="AAPL",
                    trading_date_et=trading_date,
                    target_expiry=target_expiry,
                    direction=Direction.BULLISH,
                    candidate_sequence=candidate_sequence,
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

            previous = feature_repository.create(
                SignalFeature(
                    signal_id=signal.id,
                    evaluation_sequence=1,
                    captured_at=datetime(
                        2099, 1, 5, 16, 0,
                        tzinfo=timezone.utc,
                    ),
                    flow_net=650000.0,
                    flow_threshold=500000.0,
                    underlying_price=200.0,
                    weekly_vwap=198.5,
                    vwap_status=GateStatus.PASS,
                    efficiency_ratio=0.55,
                    efficiency_ratio_status=GateStatus.PASS,
                    structure_status=GateStatus.PASS,
                    impulse_status=GateStatus.FAIL,
                    participation_status=GateStatus.PASS,
                    price_action_pass_count=2,
                    price_action_status=GateStatus.PASS,
                    atr_1h=4.50,
                    atr_15m=1.25,
                )
            )

            service = ExpectedMoveEvaluationService(
                expected_move_service=ExpectedMoveService(),
                feature_repository=feature_repository,
            )

            evaluation = service.evaluate_and_persist(
                signal_id=signal.id,
                trading_date=trading_date,
                target_expiry=target_expiry,
                underlying_price=210.0,
                term_structure_rows=(
                    {
                        "expiry": "2099-01-09",
                        "implied_move": 8.0,
                        "volatility": 0.40,
                        "implied_move_perc": 4.0,
                    },
                ),
                atm_iv=0.99,
                captured_at=datetime(
                    2099, 1, 5, 17, 0,
                    tzinfo=timezone.utc,
                ),
            )

            feature = evaluation.feature
            result = evaluation.result

            assert result.status is GateStatus.PASS
            assert result.source == "UW_TERM_STRUCTURE"
            assert result.expected_move == 8.0
            assert abs(
                result.expected_move_perc
                - (8.0 / 210.0)
            ) < 1e-12

            assert feature.id is not None
            assert feature.id != previous.id
            assert feature.evaluation_sequence == 2
            assert feature.expected_move == 8.0
            assert abs(
                feature.expected_move_perc
                - (8.0 / 210.0)
            ) < 1e-12

            # Existing underlying-price evidence belongs to the previous
            # market-regime snapshot and must not be silently rewritten
            # by this evaluation layer.
            assert feature.underlying_price == 200.0

            # Unrelated feature evidence must be carried forward.
            assert feature.flow_net == 650000.0
            assert feature.flow_threshold == 500000.0
            assert feature.weekly_vwap == 198.5
            assert feature.vwap_status is GateStatus.PASS
            assert feature.efficiency_ratio == 0.55
            assert feature.efficiency_ratio_status is GateStatus.PASS
            assert feature.structure_status is GateStatus.PASS
            assert feature.impulse_status is GateStatus.FAIL
            assert feature.participation_status is GateStatus.PASS
            assert feature.price_action_pass_count == 2
            assert feature.price_action_status is GateStatus.PASS
            assert feature.atr_1h == 4.50
            assert feature.atr_15m == 1.25

            latest = feature_repository.get_latest_for_signal(
                signal.id
            )
            assert latest is not None
            assert latest.id == feature.id
            assert latest.expected_move == 8.0
            assert abs(
                latest.expected_move_perc
                - (8.0 / 210.0)
            ) < 1e-12

            reloaded_signal = signal_repository.get_by_id(
                signal.id
            )
            assert reloaded_signal is not None
            assert reloaded_signal.state is SignalState.CANDIDATE

        finally:
            dbmod.get_database_path = original_get_database_path

    assert before == sha256_file(prod)

    print("1. temporary database copy: PASS")
    print("2. exact-expiry UW expected move persisted: PASS")
    print("3. canonical expected_move_perc persisted: PASS")
    print("4. evaluation_sequence incremented: PASS")
    print("5. previous underlying_price preserved: PASS")
    print("6. unrelated Flow/Regime/PA/ATR fields preserved: PASS")
    print("7. latest SignalFeature reload: PASS")
    print("8. Signal state unchanged: PASS")
    print("9. production database unchanged: PASS")
    print()
    print("=" * 70)
    print("EXPECTED MOVE EVALUATION SERVICE: PASS 9/9")
    print("=" * 70)


if __name__ == "__main__":
    main()
