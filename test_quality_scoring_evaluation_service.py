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
from weekly.services.quality_scoring_evaluation_service import (
    QualityScoringEvaluationService,
)
from weekly.services.quality_scoring_service import (
    QualityScoringService,
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
        prefix="weekly_quality_scoring_eval_test_"
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

        original_get_database_path = (
            dbmod.get_database_path
        )
        dbmod.get_database_path = lambda: temp_db

        try:
            signal_repository = SignalRepository()
            feature_repository = (
                SignalFeatureRepository()
            )

            trading_date = date(
                2099,
                1,
                5,
            )
            target_expiry = date(
                2099,
                1,
                9,
            )

            candidate_sequence = (
                signal_repository
                .next_candidate_sequence(
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
                    config_hash=(
                        "quality-scoring-eval-temp-test"
                    ),
                    ticker="AAPL",
                    trading_date_et=trading_date,
                    target_expiry=target_expiry,
                    direction=Direction.BULLISH,
                    candidate_sequence=(
                        candidate_sequence
                    ),
                    state=SignalState.CANDIDATE,
                    candidate_at=datetime(
                        2099,
                        1,
                        5,
                        14,
                        35,
                        tzinfo=timezone.utc,
                    ),
                    net_flow_at_candidate=(
                        1_500_000.0
                    ),
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
                        2099,
                        1,
                        5,
                        16,
                        0,
                        tzinfo=timezone.utc,
                    ),

                    flow_net=1_500_000.0,
                    flow_threshold=500_000.0,

                    underlying_price=200.0,
                    weekly_vwap=198.0,
                    vwap_status=GateStatus.PASS,

                    efficiency_ratio=1.0,
                    efficiency_ratio_status=(
                        GateStatus.PASS
                    ),

                    structure_status=GateStatus.PASS,
                    impulse_status=GateStatus.FAIL,
                    participation_status=GateStatus.PASS,
                    price_action_pass_count=2,
                    price_action_status=GateStatus.PASS,

                    atr_1h=4.0,
                    atr_15m=1.0,

                    absolute_flow_strength=(
                        1_500_000.0
                    ),
                    absolute_flow_strength_status=(
                        GateStatus.PASS
                    ),

                    relative_flow_strength=None,
                    relative_flow_strength_status=(
                        GateStatus.UNKNOWN
                    ),

                    vwap_distance_atr=0.50,
                    vwap_distance_atr_status=(
                        GateStatus.PASS
                    ),

                    sweep_ratio=1.0,
                    sweep_ratio_status=(
                        GateStatus.PASS
                    ),

                    opening_evidence=10.0,
                    opening_evidence_status=(
                        GateStatus.PASS
                    ),

                    risk_reversal=None,
                    risk_reversal_status=(
                        GateStatus.UNKNOWN
                    ),

                    target_expiry_gex_alignment=None,
                    target_expiry_gex_alignment_status=(
                        GateStatus.UNKNOWN
                    ),

                    negative_gamma_regime=True,
                    negative_gamma_regime_status=(
                        GateStatus.PASS
                    ),

                    off_exchange_cluster_score=None,
                    off_exchange_cluster_score_status=(
                        GateStatus.UNKNOWN
                    ),

                    directional_flow_confirmation=0.25,
                    directional_flow_confirmation_status=(
                        GateStatus.PASS
                    ),

                    iv_percentile=85.0,
                    iv_percentile_status=(
                        GateStatus.FAIL
                    ),

                    term_structure_inversion=None,
                    term_structure_inversion_status=(
                        GateStatus.UNKNOWN
                    ),

                    iv_vs_realized_vol=None,
                    iv_vs_realized_vol_status=(
                        GateStatus.UNKNOWN
                    ),
                )
            )

            service = QualityScoringEvaluationService(
                quality_scoring_service=(
                    QualityScoringService()
                ),
                feature_repository=feature_repository,
            )

            evaluation = service.evaluate_and_persist(
                signal_id=signal.id,
                captured_at=datetime(
                    2099,
                    1,
                    5,
                    17,
                    0,
                    tzinfo=timezone.utc,
                ),
            )

            result = evaluation.result
            feature = evaluation.feature

            assert result.base_score == 75.0
            assert result.volatility_penalty == 5.0
            assert result.final_score == 70.0

            assert result.coverage_points == 80.0
            assert abs(
                result.coverage_pct
                - (80.0 / 115.0)
            ) < 1e-12

            assert result.raw_grade == "B"
            assert result.final_grade == "B"

            assert feature.id is not None
            assert feature.id != previous.id
            assert feature.evaluation_sequence == 2

            assert feature.base_score == 75.0
            assert feature.volatility_penalty == 5.0
            assert feature.final_score == 70.0
            assert feature.coverage_points == 80.0
            assert abs(
                feature.coverage_pct
                - (80.0 / 115.0)
            ) < 1e-12
            assert feature.raw_grade == "B"
            assert feature.final_grade == "B"

            # Atomic quality evidence must survive unchanged.
            assert (
                feature.absolute_flow_strength
                == 1_500_000.0
            )
            assert (
                feature.absolute_flow_strength_status
                is GateStatus.PASS
            )
            assert feature.vwap_distance_atr == 0.50
            assert (
                feature.vwap_distance_atr_status
                is GateStatus.PASS
            )
            assert feature.sweep_ratio == 1.0
            assert (
                feature.sweep_ratio_status
                is GateStatus.PASS
            )
            assert feature.opening_evidence == 10.0
            assert (
                feature.opening_evidence_status
                is GateStatus.PASS
            )
            assert (
                feature.negative_gamma_regime
                is True
            )
            assert (
                feature.negative_gamma_regime_status
                is GateStatus.PASS
            )
            assert (
                feature.directional_flow_confirmation
                == 0.25
            )
            assert (
                feature.iv_percentile
                == 85.0
            )

            # Unrelated evidence must also survive.
            assert feature.flow_net == 1_500_000.0
            assert feature.flow_threshold == 500_000.0
            assert feature.underlying_price == 200.0
            assert feature.weekly_vwap == 198.0
            assert feature.vwap_status is GateStatus.PASS
            assert feature.efficiency_ratio == 1.0
            assert (
                feature.efficiency_ratio_status
                is GateStatus.PASS
            )
            assert (
                feature.structure_status
                is GateStatus.PASS
            )
            assert (
                feature.impulse_status
                is GateStatus.FAIL
            )
            assert (
                feature.participation_status
                is GateStatus.PASS
            )
            assert feature.price_action_pass_count == 2
            assert (
                feature.price_action_status
                is GateStatus.PASS
            )
            assert feature.atr_1h == 4.0
            assert feature.atr_15m == 1.0

            latest = (
                feature_repository
                .get_latest_for_signal(
                    signal.id
                )
            )

            assert latest is not None
            assert latest.id == feature.id
            assert latest.base_score == 75.0
            assert latest.final_score == 70.0
            assert latest.coverage_points == 80.0
            assert latest.raw_grade == "B"
            assert latest.final_grade == "B"

            reloaded_signal = (
                signal_repository.get_by_id(
                    signal.id
                )
            )

            assert reloaded_signal is not None
            assert (
                reloaded_signal.state
                is SignalState.CANDIDATE
            )

        finally:
            dbmod.get_database_path = (
                original_get_database_path
            )

    assert before == sha256_file(prod)

    print("1. temporary database copy: PASS")
    print("2. quality score calculated: PASS")
    print("3. volatility penalty calculated: PASS")
    print("4. coverage and grades calculated: PASS")
    print("5. immutable snapshot persisted: PASS")
    print("6. atomic quality evidence preserved: PASS")
    print("7. unrelated feature evidence preserved: PASS")
    print("8. latest SignalFeature reload: PASS")
    print("9. Signal state unchanged: PASS")
    print("10. production database unchanged: PASS")
    print()
    print("=" * 70)
    print(
        "QUALITY SCORING EVALUATION SERVICE: "
        "PASS 10/10"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
