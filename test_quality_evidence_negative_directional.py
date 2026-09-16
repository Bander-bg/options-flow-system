from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import weekly.db.database as dbmod
from weekly.db.flow_snapshot_repository import FlowSnapshotRepository
from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import Direction, GateStatus, SignalState
from weekly.domain.models import FlowSnapshot, Signal, SignalFeature
from weekly.services.quality_evidence_evaluation_service import (
    QualityEvidenceEvaluationService,
)
from weekly.services.quality_evidence_service import (
    QualityEvidenceService,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    prod = dbmod.get_database_path().resolve()

    if not prod.exists():
        raise RuntimeError(
            f"Production database not found: {prod}"
        )

    before = sha256_file(prod)

    with tempfile.TemporaryDirectory(
        prefix="weekly_quality_evidence_eval_test_"
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
            flow_repository = FlowSnapshotRepository()
            feature_repository = SignalFeatureRepository()

            trading_date = date(2099, 1, 5)
            target_expiry = date(2099, 1, 9)
            other_expiry = date(2099, 1, 16)

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
                    config_hash="quality-evidence-eval-temp-test",
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
                    net_flow_at_candidate=800_000.0,
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
                    underlying_price=204.0,
                    weekly_vwap=200.0,
                    vwap_status=GateStatus.PASS,
                    efficiency_ratio=0.55,
                    efficiency_ratio_status=GateStatus.PASS,
                    atr_1h=8.0,
                    atr_15m=2.0,
                    structure_status=GateStatus.PASS,
                    impulse_status=GateStatus.FAIL,
                    participation_status=GateStatus.PASS,
                    price_action_pass_count=2,
                    price_action_status=GateStatus.PASS,
                )
            )

            exact_flow = flow_repository.create(
                FlowSnapshot(
                    ticker="AAPL",
                    trading_date_et=trading_date,
                    captured_at=datetime(
                        2099, 1, 5, 16, 5,
                        tzinfo=timezone.utc,
                    ),
                    target_expiry=target_expiry,

                    call_ask_premium=900_000.0,
                    put_ask_premium=100_000.0,
                    net_flow=800_000.0,

                    call_bid_premium=200_000.0,
                    put_bid_premium=300_000.0,

                    bullish_premium=450_000.0,
                    bearish_premium=750_000.0,
                    directional_net=-300_000.0,

                    raw_alert_count=10,
                    clean_alert_count=10,
                    deduped_alert_count=10,

                    flow_dedup_level="alert_uuid",
                    trade_overlap_detected=False,

                    sweep_alert_count=3,
                    opening_alert_count=0,

                    provider="UNUSUAL_WHALES",
                    feed="UNKNOWN",

                    source_timestamp=datetime(
                        2099, 1, 5, 16, 5,
                        tzinfo=timezone.utc,
                    ),
                    fetched_at=datetime(
                        2099, 1, 5, 16, 5,
                        tzinfo=timezone.utc,
                    ),

                    freshness_status="PASS",

                    total_premium=2_000_000.0,
                    sweep_premium=1_200_000.0,
                )
            )

            # Newer globally, but wrong expiry.
            flow_repository.create(
                FlowSnapshot(
                    ticker="AAPL",
                    trading_date_et=trading_date,
                    captured_at=datetime(
                        2099, 1, 5, 16, 10,
                        tzinfo=timezone.utc,
                    ),
                    target_expiry=other_expiry,

                    call_ask_premium=2_100_000.0,
                    put_ask_premium=100_000.0,
                    net_flow=2_000_000.0,

                    call_bid_premium=100_000.0,
                    put_bid_premium=50_000.0,

                    bullish_premium=2_150_000.0,
                    bearish_premium=200_000.0,
                    directional_net=1_950_000.0,

                    raw_alert_count=10,
                    clean_alert_count=10,
                    deduped_alert_count=10,

                    flow_dedup_level="alert_uuid",
                    trade_overlap_detected=False,

                    sweep_alert_count=5,
                    opening_alert_count=0,

                    provider="UNUSUAL_WHALES",
                    feed="UNKNOWN",

                    source_timestamp=datetime(
                        2099, 1, 5, 16, 10,
                        tzinfo=timezone.utc,
                    ),
                    fetched_at=datetime(
                        2099, 1, 5, 16, 10,
                        tzinfo=timezone.utc,
                    ),

                    freshness_status="PASS",

                    total_premium=3_000_000.0,
                    sweep_premium=2_000_000.0,
                )
            )

            service = QualityEvidenceEvaluationService(
                quality_evidence_service=QualityEvidenceService(),
                signal_repository=signal_repository,
                flow_snapshot_repository=flow_repository,
                feature_repository=feature_repository,
            )

            evaluation = service.evaluate_and_persist(
                signal_id=signal.id,
                captured_at=datetime(
                    2099, 1, 5, 16, 15,
                    tzinfo=timezone.utc,
                ),
            )

            result = evaluation.result
            feature = evaluation.feature

            assert evaluation.flow_snapshot.id == exact_flow.id
            assert evaluation.flow_snapshot.target_expiry == target_expiry

            assert result.absolute_flow_strength == 800_000.0
            assert (
                result.absolute_flow_strength_status
                is GateStatus.PASS
            )

            assert result.vwap_distance_atr == 0.5
            assert (
                result.vwap_distance_atr_status
                is GateStatus.PASS
            )

            assert result.sweep_ratio == 0.6
            assert (
                result.sweep_ratio_status
                is GateStatus.PASS
            )

            assert result.directional_flow_confirmation == -0.25
            assert (
                result.directional_flow_confirmation_status
                is GateStatus.FAIL
            )

            assert feature.id is not None
            assert feature.id != previous.id
            assert feature.evaluation_sequence == 2

            assert feature.flow_net == 800_000.0
            assert feature.absolute_flow_strength == 800_000.0
            assert feature.vwap_distance_atr == 0.5
            assert feature.sweep_ratio == 0.6
            assert feature.directional_flow_confirmation == -0.25

            assert feature.underlying_price == 204.0
            assert feature.weekly_vwap == 200.0
            assert feature.vwap_status is GateStatus.PASS
            assert feature.efficiency_ratio == 0.55
            assert (
                feature.efficiency_ratio_status
                is GateStatus.PASS
            )
            assert feature.atr_1h == 8.0
            assert feature.atr_15m == 2.0
            assert feature.structure_status is GateStatus.PASS
            assert feature.impulse_status is GateStatus.FAIL
            assert (
                feature.participation_status
                is GateStatus.PASS
            )
            assert feature.price_action_pass_count == 2
            assert (
                feature.price_action_status
                is GateStatus.PASS
            )

            latest = feature_repository.get_latest_for_signal(
                signal.id
            )

            assert latest is not None
            assert latest.id == feature.id
            assert latest.absolute_flow_strength == 800_000.0
            assert latest.vwap_distance_atr == 0.5
            assert latest.sweep_ratio == 0.6
            assert latest.directional_flow_confirmation == -0.25

            reloaded_signal = signal_repository.get_by_id(
                signal.id
            )

            assert reloaded_signal is not None
            assert (
                reloaded_signal.state
                is SignalState.CANDIDATE
            )

        finally:
            dbmod.get_database_path = original_get_database_path

    assert before == sha256_file(prod)

    print("1. temporary database copy: PASS")
    print("2. exact-expiry FlowSnapshot selected: PASS")
    print("3. newer wrong-expiry FlowSnapshot ignored: PASS")
    print("4. atomic quality evidence derived: PASS")
    print("5. immutable SignalFeature snapshot persisted: PASS")
    print("6. unrelated feature evidence preserved: PASS")
    print("7. latest SignalFeature reload: PASS")
    print("8. Signal state unchanged: PASS")
    print("9. production database unchanged: PASS")

    print()
    print("=" * 70)
    print("QUALITY EVIDENCE EVALUATION SERVICE: PASS 9/9")
    print("=" * 70)


if __name__ == "__main__":
    main()
