from datetime import datetime, timezone

from weekly.domain.enums import GateStatus
from weekly.domain.models import SignalFeature
from weekly.services.quality_scoring_service import (
    QualityScoringService,
)


def main():
    service = QualityScoringService()

    feature = SignalFeature(
        signal_id=1,
        evaluation_sequence=1,
        captured_at=datetime(
            2026, 9, 12, 18, 0,
            tzinfo=timezone.utc,
        ),

        absolute_flow_strength=1_500_000.0,
        absolute_flow_strength_status=GateStatus.PASS,

        relative_flow_strength=None,
        relative_flow_strength_status=GateStatus.UNKNOWN,

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

        iv_percentile=80.0,
        iv_percentile_status=GateStatus.FAIL,

        term_structure_inversion=None,
        term_structure_inversion_status=GateStatus.UNKNOWN,

        iv_vs_realized_vol=None,
        iv_vs_realized_vol_status=GateStatus.UNKNOWN,
    )

    result = service.evaluate(
        feature=feature
    )

    assert result.base_score == 75.0, result
    assert result.volatility_penalty == 0.0, result
    assert result.final_score == 75.0, result

    assert result.coverage_points == 80.0, result
    assert abs(
        result.coverage_pct - (80.0 / 115.0)
    ) < 1e-12, result

    assert result.raw_grade == "B", result
    assert result.final_grade == "B", result

    print("1. Base score direct sum: PASS")
    print("2. Volatility penalty: PASS")
    print("3. Final score: PASS")
    print("4. Coverage denominator 115: PASS")
    print("5. UNKNOWN not renormalized: PASS")
    print("6. Grade calculation: PASS")

    print()
    print("=" * 70)
    print("QUALITY SCORING SERVICE: PASS 6/6")
    print("=" * 70)


if __name__ == "__main__":
    main()

