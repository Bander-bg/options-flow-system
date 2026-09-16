from dataclasses import replace
from datetime import datetime, timezone

from weekly.domain.enums import GateStatus
from weekly.domain.models import SignalFeature
from weekly.services.quality_scoring_service import (
    QualityScoringError,
    QualityScoringService,
)


def make_feature():
    return SignalFeature(
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


def main():
    service = QualityScoringService()

    # 1. IV penalty is strict: exactly 80 is not penalized.
    boundary = service.evaluate(
        feature=make_feature()
    )
    assert boundary.volatility_penalty == 0.0
    print("1. IV percentile = 80 has no penalty: PASS")

    # 2. Just below IV threshold must not be penalized.
    below_iv = service.evaluate(
        feature=replace(
            make_feature(),
            iv_percentile=79.999,
            iv_percentile_status=GateStatus.PASS,
        )
    )
    assert below_iv.volatility_penalty == 0.0
    print("2. IV percentile below 80: PASS")

    # 3. Disabled factors remain unavailable even if a caller
    # accidentally supplies apparently valid evidence.
    disabled = service.evaluate(
        feature=replace(
            make_feature(),

            relative_flow_strength=1.0,
            relative_flow_strength_status=GateStatus.PASS,

            risk_reversal=1.0,
            risk_reversal_status=GateStatus.PASS,

            target_expiry_gex_alignment=True,
            target_expiry_gex_alignment_status=GateStatus.PASS,

            off_exchange_cluster_score=1.0,
            off_exchange_cluster_score_status=GateStatus.PASS,
        )
    )

    disabled_names = {
        "relative_flow_strength",
        "risk_reversal",
        "target_expiry_gex_alignment",
        "off_exchange_cluster_score",
    }

    assert disabled_names.issubset(
        set(disabled.unknown_components)
    )

    for name, points in disabled.component_points:
        if name in disabled_names:
            assert points == 0.0

    assert disabled.coverage_points == 80.0
    print("3. Disabled factors cannot earn score/coverage: PASS")

    # 4. Known status without the corresponding value is invalid.
    try:
        service.evaluate(
            feature=replace(
                make_feature(),
                sweep_ratio=None,
                sweep_ratio_status=GateStatus.PASS,
            )
        )
    except QualityScoringError:
        pass
    else:
        raise AssertionError(
            "Known status without value was not rejected."
        )

    print("4. Known status requires evidence value: PASS")

    # 5. Current realistically available subset:
    # abs + VWAP + ER + sweep + directional + IV
    # coverage = 65 / 115 < 60%, therefore UNRATED.
    limited = service.evaluate(
        feature=replace(
            make_feature(),

            opening_evidence=None,
            opening_evidence_status=GateStatus.UNKNOWN,

            negative_gamma_regime=None,
            negative_gamma_regime_status=GateStatus.UNKNOWN,

            iv_percentile=50.0,
            iv_percentile_status=GateStatus.PASS,
        )
    )

    assert limited.coverage_points == 65.0
    assert abs(
        limited.coverage_pct - (65.0 / 115.0)
    ) < 1e-12

    assert limited.final_grade == "UNRATED"
    print("5. Coverage below 60% -> UNRATED: PASS")

    # 6. UNKNOWN evidence must not be silently renormalized.
    assert limited.base_score == 60.0
    assert limited.final_score == 60.0
    print("6. Missing factors are not renormalized: PASS")

    print()
    print("=" * 70)
    print("QUALITY SCORING EDGE CASES: PASS 6/6")
    print("=" * 70)


if __name__ == "__main__":
    main()
