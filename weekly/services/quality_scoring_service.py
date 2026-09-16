from __future__ import annotations

from dataclasses import dataclass

from config import load_weekly_config
from weekly.domain.enums import GateStatus
from weekly.domain.models import SignalFeature


class QualityScoringError(ValueError):
    """Invalid weekly_v1 quality-scoring input."""


@dataclass(frozen=True)
class QualityScoringSettings:
    absolute_weight: float
    absolute_minimum: float
    absolute_full_score: float

    relative_weight: float
    relative_enabled: bool

    vwap_weight: float
    vwap_interpolation: tuple[tuple[float, float], ...]

    er_weight: float
    er_minimum: float
    er_maximum: float

    sweep_weight: float
    sweep_breakpoint_ratio: float
    sweep_breakpoint_points: float
    sweep_maximum_ratio: float
    sweep_maximum_points: float

    opening_weight: float

    risk_reversal_weight: float
    risk_reversal_enabled: bool

    gex_alignment_weight: float
    gex_alignment_enabled: bool

    negative_gamma_weight: float
    negative_gamma_enabled: bool

    off_exchange_weight: float
    off_exchange_enabled: bool

    directional_weight: float
    directional_strong_threshold: float
    directional_strong_points: float
    directional_weak_points: float
    directional_conflict_points: float

    iv_percentile_weight: float
    iv_percentile_penalty: float
    iv_percentile_enabled: bool
    iv_percentile_high: float

    term_structure_weight: float
    term_structure_penalty: float
    term_structure_enabled: bool

    iv_vs_rv_weight: float
    iv_vs_rv_penalty: float
    iv_vs_rv_enabled: bool

    maximum_penalty: float

    coverage_total: float
    coverage_a_min: float
    coverage_b_min: float
    coverage_minimum: float

    grade_a_min: float
    grade_b_min: float

    @classmethod
    def from_config(
        cls,
    ) -> "QualityScoringSettings":
        config = load_weekly_config(
            require_runtime_ready=True
        )

        quality = config["quality_scoring"]
        volatility_penalty = (
            config["volatility_penalty"]
        )
        market_structure = (
            quality["market_structure"]
        )

        interpolation = tuple(
            (
                float(point["x"]),
                float(point["points"]),
            )
            for point in quality[
                "vwap_distance_atr"
            ]["interpolation_points"]
        )

        return cls(
            absolute_weight=float(
                quality[
                    "absolute_flow_strength"
                ]["weight"]
            ),
            absolute_minimum=float(
                quality[
                    "absolute_flow_strength"
                ]["minimum_flow"]
            ),
            absolute_full_score=float(
                quality[
                    "absolute_flow_strength"
                ]["full_score_flow"]
            ),

            relative_weight=float(
                quality[
                    "relative_flow_strength"
                ]["weight"]
            ),
            relative_enabled=bool(
                quality[
                    "relative_flow_strength"
                ]["enabled"]
            ),

            vwap_weight=float(
                quality[
                    "vwap_distance_atr"
                ]["weight"]
            ),
            vwap_interpolation=interpolation,

            er_weight=float(
                quality[
                    "efficiency_ratio_strength"
                ]["weight"]
            ),
            er_minimum=float(
                quality[
                    "efficiency_ratio_strength"
                ]["minimum_er"]
            ),
            er_maximum=float(
                quality[
                    "efficiency_ratio_strength"
                ]["maximum_er"]
            ),

            sweep_weight=float(
                quality[
                    "sweep_ratio"
                ]["weight"]
            ),
            sweep_breakpoint_ratio=float(
                quality[
                    "sweep_ratio"
                ]["breakpoint_ratio"]
            ),
            sweep_breakpoint_points=float(
                quality[
                    "sweep_ratio"
                ]["points_at_breakpoint"]
            ),
            sweep_maximum_ratio=float(
                quality[
                    "sweep_ratio"
                ]["maximum_ratio"]
            ),
            sweep_maximum_points=float(
                quality[
                    "sweep_ratio"
                ]["maximum_points"]
            ),

            opening_weight=float(
                quality[
                    "opening_evidence"
                ]["weight"]
            ),

            risk_reversal_weight=float(
                quality[
                    "risk_reversal"
                ]["weight"]
            ),
            risk_reversal_enabled=bool(
                quality[
                    "risk_reversal"
                ]["enabled"]
            ),

            gex_alignment_weight=float(
                market_structure[
                    "target_expiry_gex_alignment"
                ]["weight"]
            ),
            gex_alignment_enabled=bool(
                market_structure[
                    "target_expiry_gex_alignment"
                ]["enabled"]
            ),

            negative_gamma_weight=float(
                market_structure[
                    "negative_gamma_regime"
                ]["weight"]
            ),
            negative_gamma_enabled=bool(
                market_structure[
                    "negative_gamma_regime"
                ]["enabled"]
            ),

            off_exchange_weight=float(
                market_structure[
                    "off_exchange_cluster_score"
                ]["weight"]
            ),
            off_exchange_enabled=bool(
                market_structure[
                    "off_exchange_cluster_score"
                ]["enabled"]
            ),

            directional_weight=float(
                quality[
                    "directional_flow_confirmation"
                ]["weight"]
            ),
            directional_strong_threshold=float(
                quality[
                    "directional_flow_confirmation"
                ]["strong_threshold"]
            ),
            directional_strong_points=float(
                quality[
                    "directional_flow_confirmation"
                ]["strong_points"]
            ),
            directional_weak_points=float(
                quality[
                    "directional_flow_confirmation"
                ]["weak_points"]
            ),
            directional_conflict_points=float(
                quality[
                    "directional_flow_confirmation"
                ]["conflict_points"]
            ),

            iv_percentile_weight=float(
                volatility_penalty[
                    "iv_percentile"
                ]["weight"]
            ),
            iv_percentile_penalty=float(
                volatility_penalty[
                    "iv_percentile"
                ]["penalty"]
            ),
            iv_percentile_enabled=bool(
                volatility_penalty[
                    "iv_percentile"
                ]["enabled"]
            ),
            iv_percentile_high=float(
                config["volatility"][
                    "iv_percentile_high"
                ]
            ),

            term_structure_weight=float(
                volatility_penalty[
                    "term_structure"
                ]["weight"]
            ),
            term_structure_penalty=float(
                volatility_penalty[
                    "term_structure"
                ]["penalty"]
            ),
            term_structure_enabled=bool(
                volatility_penalty[
                    "term_structure"
                ]["enabled"]
            ),

            iv_vs_rv_weight=float(
                volatility_penalty[
                    "iv_vs_rv"
                ]["weight"]
            ),
            iv_vs_rv_penalty=float(
                volatility_penalty[
                    "iv_vs_rv"
                ]["penalty"]
            ),
            iv_vs_rv_enabled=bool(
                volatility_penalty[
                    "iv_vs_rv"
                ]["enabled"]
            ),

            maximum_penalty=float(
                volatility_penalty[
                    "maximum_penalty"
                ]
            ),

            coverage_total=float(
                config["coverage"][
                    "total_availability_weight"
                ]
            ),
            coverage_a_min=float(
                config["coverage"][
                    "coverage_a_min"
                ]
            ),
            coverage_b_min=float(
                config["coverage"][
                    "coverage_b_min"
                ]
            ),
            coverage_minimum=float(
                config["coverage"][
                    "coverage_minimum_for_rating"
                ]
            ),

            grade_a_min=float(
                config["grades"][
                    "grade_a_min_score"
                ]
            ),
            grade_b_min=float(
                config["grades"][
                    "grade_b_min_score"
                ]
            ),
        )


@dataclass(frozen=True)
class QualityScoringResult:
    base_score: float
    volatility_penalty: float
    final_score: float

    coverage_points: float
    coverage_pct: float

    raw_grade: str
    final_grade: str

    component_points: tuple[
        tuple[str, float],
        ...
    ]

    available_components: tuple[str, ...]
    unknown_components: tuple[str, ...]


class QualityScoringService:
    """
    Pure weekly_v1 quality scorer.

    Responsibilities:
    - convert available atomic evidence to earned points
    - preserve UNKNOWN as unavailable evidence
    - never renormalize Base Score around missing data
    - calculate Volatility Penalty separately
    - calculate Coverage against fixed denominator 115
    - calculate Raw Grade from Final Score
    - apply Coverage cap only to displayed Final Grade

    No API calls and no database writes.
    """

    def __init__(
        self,
        settings: QualityScoringSettings | None = None,
    ) -> None:
        self.settings = (
            settings
            or QualityScoringSettings.from_config()
        )

    @staticmethod
    def _is_known(
        status: GateStatus | None,
    ) -> bool:
        return (
            status is GateStatus.PASS
            or status is GateStatus.FAIL
        )

    @staticmethod
    def _require_value(
        *,
        name: str,
        value,
        status: GateStatus | None,
    ):
        if (
            status is not None
            and not isinstance(status, GateStatus)
        ):
            raise QualityScoringError(
                f"{name} status must be "
                "GateStatus or None."
            )

        if (
            QualityScoringService._is_known(status)
            and value is None
        ):
            raise QualityScoringError(
                f"{name} is marked available "
                "but its value is missing."
            )

        return value

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return max(
            minimum,
            min(maximum, value),
        )

    @staticmethod
    def _interpolate(
        value: float,
        points: tuple[
            tuple[float, float],
            ...
        ],
    ) -> float:
        if value <= points[0][0]:
            return points[0][1]

        if value >= points[-1][0]:
            return points[-1][1]

        for (
            left_x,
            left_points,
        ), (
            right_x,
            right_points,
        ) in zip(
            points,
            points[1:],
        ):
            if left_x <= value <= right_x:
                span = right_x - left_x

                if span <= 0:
                    raise QualityScoringError(
                        "Invalid interpolation span."
                    )

                fraction = (
                    (value - left_x)
                    / span
                )

                return (
                    left_points
                    + fraction
                    * (
                        right_points
                        - left_points
                    )
                )

        raise QualityScoringError(
            "Interpolation failed."
        )

    def evaluate(
        self,
        *,
        feature: SignalFeature,
    ) -> QualityScoringResult:

        if not isinstance(
            feature,
            SignalFeature,
        ):
            raise QualityScoringError(
                "feature must be SignalFeature."
            )

        settings = self.settings

        component_points: dict[str, float] = {}
        available: list[str] = []
        unknown: list[str] = []

        coverage_points = 0.0

        def register(
            *,
            name: str,
            weight: float,
            status: GateStatus | None,
            points: float = 0.0,
            enabled: bool = True,
        ) -> None:
            nonlocal coverage_points

            if not enabled:
                component_points[name] = 0.0
                unknown.append(name)
                return

            if not self._is_known(status):
                component_points[name] = 0.0
                unknown.append(name)
                return

            coverage_points += weight
            available.append(name)

            component_points[name] = self._clamp(
                float(points),
                0.0,
                weight,
            )

        # --------------------------------------------------
        # 1. ABSOLUTE FLOW
        # --------------------------------------------------

        absolute = self._require_value(
            name="absolute_flow_strength",
            value=feature.absolute_flow_strength,
            status=feature.absolute_flow_strength_status,
        )

        absolute_points = 0.0

        if (
            absolute is not None
            and self._is_known(
                feature.absolute_flow_strength_status
            )
        ):
            denominator = (
                settings.absolute_full_score
                - settings.absolute_minimum
            )

            absolute_points = (
                (
                    float(absolute)
                    - settings.absolute_minimum
                )
                / denominator
                * settings.absolute_weight
            )

        register(
            name="absolute_flow_strength",
            weight=settings.absolute_weight,
            status=(
                feature
                .absolute_flow_strength_status
            ),
            points=absolute_points,
        )

        # --------------------------------------------------
        # 1B. RELATIVE FLOW
        # --------------------------------------------------

        self._require_value(
            name="relative_flow_strength",
            value=feature.relative_flow_strength,
            status=feature.relative_flow_strength_status,
        )

        relative_points = (
            settings.relative_weight
            if (
                feature.relative_flow_strength_status
                is GateStatus.PASS
            )
            else 0.0
        )

        register(
            name="relative_flow_strength",
            weight=settings.relative_weight,
            status=(
                feature
                .relative_flow_strength_status
            ),
            points=relative_points,
            enabled=settings.relative_enabled,
        )

        # --------------------------------------------------
        # 2. VWAP DISTANCE / ATR
        # --------------------------------------------------

        vwap_distance = self._require_value(
            name="vwap_distance_atr",
            value=feature.vwap_distance_atr,
            status=feature.vwap_distance_atr_status,
        )

        vwap_points = 0.0

        if (
            vwap_distance is not None
            and self._is_known(
                feature.vwap_distance_atr_status
            )
        ):
            vwap_points = self._interpolate(
                float(vwap_distance),
                settings.vwap_interpolation,
            )

        register(
            name="vwap_distance_atr",
            weight=settings.vwap_weight,
            status=feature.vwap_distance_atr_status,
            points=vwap_points,
        )

        # --------------------------------------------------
        # 3. EFFICIENCY RATIO
        # --------------------------------------------------

        er = self._require_value(
            name="efficiency_ratio",
            value=feature.efficiency_ratio,
            status=feature.efficiency_ratio_status,
        )

        er_points = 0.0

        if (
            er is not None
            and self._is_known(
                feature.efficiency_ratio_status
            )
        ):
            er_points = (
                (
                    float(er)
                    - settings.er_minimum
                )
                / (
                    settings.er_maximum
                    - settings.er_minimum
                )
                * settings.er_weight
            )

        register(
            name="efficiency_ratio",
            weight=settings.er_weight,
            status=feature.efficiency_ratio_status,
            points=er_points,
        )

        # --------------------------------------------------
        # 4. SWEEP RATIO
        # --------------------------------------------------

        sweep = self._require_value(
            name="sweep_ratio",
            value=feature.sweep_ratio,
            status=feature.sweep_ratio_status,
        )

        sweep_points = 0.0

        if (
            sweep is not None
            and self._is_known(
                feature.sweep_ratio_status
            )
        ):
            sweep = float(sweep)

            if sweep <= settings.sweep_breakpoint_ratio:
                if settings.sweep_breakpoint_ratio > 0:
                    sweep_points = (
                        sweep
                        / settings.sweep_breakpoint_ratio
                        * settings.sweep_breakpoint_points
                    )

            else:
                second_span = (
                    settings.sweep_maximum_ratio
                    - settings.sweep_breakpoint_ratio
                )

                if second_span <= 0:
                    sweep_points = (
                        settings.sweep_maximum_points
                    )
                else:
                    fraction = (
                        sweep
                        - settings.sweep_breakpoint_ratio
                    ) / second_span

                    sweep_points = (
                        settings.sweep_breakpoint_points
                        + fraction
                        * (
                            settings.sweep_maximum_points
                            - settings.sweep_breakpoint_points
                        )
                    )

        register(
            name="sweep_ratio",
            weight=settings.sweep_weight,
            status=feature.sweep_ratio_status,
            points=sweep_points,
        )

        # --------------------------------------------------
        # 5. OPENING EVIDENCE
        # --------------------------------------------------

        opening = self._require_value(
            name="opening_evidence",
            value=feature.opening_evidence,
            status=feature.opening_evidence_status,
        )

        register(
            name="opening_evidence",
            weight=settings.opening_weight,
            status=feature.opening_evidence_status,
            points=(
                float(opening)
                if opening is not None
                else 0.0
            ),
        )

        # --------------------------------------------------
        # 6. RISK REVERSAL
        # --------------------------------------------------

        self._require_value(
            name="risk_reversal",
            value=feature.risk_reversal,
            status=feature.risk_reversal_status,
        )

        risk_reversal_points = (
            settings.risk_reversal_weight
            if (
                feature.risk_reversal_status
                is GateStatus.PASS
            )
            else 0.0
        )

        register(
            name="risk_reversal",
            weight=settings.risk_reversal_weight,
            status=feature.risk_reversal_status,
            points=risk_reversal_points,
            enabled=settings.risk_reversal_enabled,
        )

        # --------------------------------------------------
        # 7A. GEX ALIGNMENT
        # --------------------------------------------------

        self._require_value(
            name="target_expiry_gex_alignment",
            value=feature.target_expiry_gex_alignment,
            status=(
                feature
                .target_expiry_gex_alignment_status
            ),
        )

        register(
            name="target_expiry_gex_alignment",
            weight=settings.gex_alignment_weight,
            status=(
                feature
                .target_expiry_gex_alignment_status
            ),
            points=(
                settings.gex_alignment_weight
                if feature.target_expiry_gex_alignment
                is True
                else 0.0
            ),
            enabled=settings.gex_alignment_enabled,
        )

        # --------------------------------------------------
        # 7B. NEGATIVE GAMMA
        # --------------------------------------------------

        self._require_value(
            name="negative_gamma_regime",
            value=feature.negative_gamma_regime,
            status=feature.negative_gamma_regime_status,
        )

        register(
            name="negative_gamma_regime",
            weight=settings.negative_gamma_weight,
            status=feature.negative_gamma_regime_status,
            points=(
                settings.negative_gamma_weight
                if feature.negative_gamma_regime
                is True
                else 0.0
            ),
            enabled=settings.negative_gamma_enabled,
        )

        # --------------------------------------------------
        # 7C. OFF-EXCHANGE
        # --------------------------------------------------

        self._require_value(
            name="off_exchange_cluster_score",
            value=feature.off_exchange_cluster_score,
            status=(
                feature
                .off_exchange_cluster_score_status
            ),
        )

        off_exchange_points = (
            settings.off_exchange_weight
            if (
                feature
                .off_exchange_cluster_score_status
                is GateStatus.PASS
            )
            else 0.0
        )

        register(
            name="off_exchange_cluster_score",
            weight=settings.off_exchange_weight,
            status=(
                feature
                .off_exchange_cluster_score_status
            ),
            points=off_exchange_points,
            enabled=settings.off_exchange_enabled,
        )

        # --------------------------------------------------
        # 8. DIRECTIONAL FLOW CONFIRMATION
        # --------------------------------------------------

        directional = self._require_value(
            name="directional_flow_confirmation",
            value=feature.directional_flow_confirmation,
            status=(
                feature
                .directional_flow_confirmation_status
            ),
        )

        directional_points = 0.0

        if (
            directional is not None
            and self._is_known(
                feature
                .directional_flow_confirmation_status
            )
        ):
            directional = float(
                directional
            )

            if (
                directional
                >= settings.directional_strong_threshold
            ):
                directional_points = (
                    settings.directional_strong_points
                )

            elif directional > 0:
                directional_points = (
                    settings.directional_weak_points
                )

            else:
                directional_points = (
                    settings.directional_conflict_points
                )

        register(
            name="directional_flow_confirmation",
            weight=settings.directional_weight,
            status=(
                feature
                .directional_flow_confirmation_status
            ),
            points=directional_points,
        )

        base_score = sum(
            component_points.values()
        )

        base_score = self._clamp(
            base_score,
            0.0,
            100.0,
        )

        # --------------------------------------------------
        # VOLATILITY PENALTY + COVERAGE
        # --------------------------------------------------

        volatility_penalty = 0.0

        iv_percentile = self._require_value(
            name="iv_percentile",
            value=feature.iv_percentile,
            status=feature.iv_percentile_status,
        )

        iv_penalty_points = 0.0

        if (
            settings.iv_percentile_enabled
            and self._is_known(
                feature.iv_percentile_status
            )
        ):
            coverage_points += (
                settings.iv_percentile_weight
            )
            available.append(
                "iv_percentile"
            )

            if (
                iv_percentile is not None
                and float(iv_percentile)
                > settings.iv_percentile_high
            ):
                iv_penalty_points = (
                    settings.iv_percentile_penalty
                )

        else:
            unknown.append(
                "iv_percentile"
            )

        volatility_penalty += (
            iv_penalty_points
        )

        self._require_value(
            name="term_structure_inversion",
            value=feature.term_structure_inversion,
            status=(
                feature
                .term_structure_inversion_status
            ),
        )

        if (
            settings.term_structure_enabled
            and self._is_known(
                feature
                .term_structure_inversion_status
            )
        ):
            coverage_points += (
                settings.term_structure_weight
            )
            available.append(
                "term_structure_inversion"
            )

            if (
                feature.term_structure_inversion
                is True
            ):
                volatility_penalty += (
                    settings.term_structure_penalty
                )

        else:
            unknown.append(
                "term_structure_inversion"
            )

        self._require_value(
            name="iv_vs_realized_vol",
            value=feature.iv_vs_realized_vol,
            status=feature.iv_vs_realized_vol_status,
        )

        if (
            settings.iv_vs_rv_enabled
            and self._is_known(
                feature.iv_vs_realized_vol_status
            )
        ):
            coverage_points += (
                settings.iv_vs_rv_weight
            )
            available.append(
                "iv_vs_realized_vol"
            )

            if (
                feature.iv_vs_realized_vol_status
                is GateStatus.FAIL
            ):
                volatility_penalty += (
                    settings.iv_vs_rv_penalty
                )

        else:
            unknown.append(
                "iv_vs_realized_vol"
            )

        volatility_penalty = self._clamp(
            volatility_penalty,
            0.0,
            settings.maximum_penalty,
        )

        final_score = self._clamp(
            base_score
            - volatility_penalty,
            0.0,
            100.0,
        )

        coverage_pct = (
            coverage_points
            / settings.coverage_total
        )

        coverage_pct = self._clamp(
            coverage_pct,
            0.0,
            1.0,
        )

        if final_score >= settings.grade_a_min:
            raw_grade = "A"

        elif final_score >= settings.grade_b_min:
            raw_grade = "B"

        else:
            raw_grade = "C"

        if (
            coverage_pct
            < settings.coverage_minimum
        ):
            final_grade = "UNRATED"

        elif (
            coverage_pct
            < settings.coverage_a_min
            and raw_grade == "A"
        ):
            final_grade = "B"

        else:
            final_grade = raw_grade

        return QualityScoringResult(
            base_score=base_score,
            volatility_penalty=(
                volatility_penalty
            ),
            final_score=final_score,

            coverage_points=(
                coverage_points
            ),
            coverage_pct=coverage_pct,

            raw_grade=raw_grade,
            final_grade=final_grade,

            component_points=tuple(
                component_points.items()
            ),

            available_components=tuple(
                available
            ),

            unknown_components=tuple(
                unknown
            ),
        )
