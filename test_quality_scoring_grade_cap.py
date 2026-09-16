from dataclasses import replace
from datetime import datetime, timezone

from weekly.domain.enums import GateStatus
from weekly.domain.models import SignalFeature
from weekly.services.quality_scoring_service import (
    QualityScoringService,
    QualityScoringSettings,
)


def main():
    # Test-only settings:
    # enable Relative Flow so maximum available Base Score
    # can reach 80 while Coverage remains below 75%.
    settings = replace(
        QualityScoringSettings.from_config(),
        relative_enabled=True,
    )

    service = QualityScoringService(
        settings=settings
    )

    feature = SignalFeature(
        signal_id=1,
        evaluation_sequence=1,
        captured_at=datetime(
            2026, 9, 12, 18, 0,
            tzinfo=timezone.utc,
        ),

        absolute_flow_strength=1_500_000.0,
        absolute_flow_strength_status=GateStatus.PASS,

        relative_flow_strength=1.0,
        relative_flow_strength_status=GateStatus.PASS,

        vwap_distance_atr=0.50,
        vwap_distance_atr_status=GateStatus.PASS,

        efficiency_ratio=1.00,
        efficiency_ratio_status=GateStatus.PASS,

        sweep_ratio=1.00,
        sweep_ratio_status=GateStatus.PASS,

        opening_evidence=10.0,
        opening_evidence_status=GateStatus.PASS,

        risk_reversal=None,
        risk_reversal_status=GateStatus.UNKNOWN,

        target_expiry_gex_alignment=None,
        target_expiry_gex_alignment_status=GateStatus.UNKNOWN,

        negative_gamma_regime=True,
        negative_gamma_regime_status=GateStatus.PASS,

        off_exchange_cluster_score=None,
        off_exchange_cluster_score_status=GateStatus.UNKNOWN,

        directional_flow_confirmation=0.25,
        directional_flow_confirmation_status=GateStatus.PASS,

        iv_percentile=50.0,
        iv_percentile_status=GateStatus.PASS,

        term_structure_inversion=None,
        term_structure_inversion_status=GateStatus.UNKNOWN,

        iv_vs_realized_vol=None,
        iv_vs_realized_vol_status=GateStatus.UNKNOWN,
    )

    result = service.evaluate(
        feature=feature
    )

    assert result.base_score == 80.0, result
    assert result.volatility_penalty == 0.0, result
    assert result.final_score == 80.0, result

    assert result.coverage_points == 85.0, result
    assert abs(
        result.coverage_pct - (85.0 / 115.0)
    ) < 1e-12, result

    assert 0.60 <= result.coverage_pct < 0.75, result

    assert result.raw_grade == "A", result
    assert result.final_grade == "B", result

    print("1. Base Score reaches A threshold: PASS")
    print("2. Coverage remains below 75%: PASS")
    print("3. Raw Grade A: PASS")
    print("4. Coverage cap changes Final Grade A -> B: PASS")

    print()
    print("=" * 70)
    print("QUALITY SCORING GRADE CAP: PASS 4/4")
    print("=" * 70)


if __name__ == "__main__":
    main()
