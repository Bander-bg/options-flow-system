from __future__ import annotations

from dataclasses import dataclass

from config import load_weekly_config
from weekly.domain.enums import Direction, GateStatus
from weekly.domain.models import FlowSnapshot, SignalFeature


class QualityEvidenceError(ValueError):
    """Invalid weekly_v1 quality-evidence input."""


@dataclass(frozen=True)
class QualityEvidenceSettings:
    absolute_flow_minimum: float
    directional_strong_threshold: float
    all_opening_trades_points: float

    @classmethod
    def from_config(
        cls,
    ) -> "QualityEvidenceSettings":
        config = load_weekly_config(
            require_runtime_ready=True
        )

        quality = config["quality_scoring"]

        return cls(
            absolute_flow_minimum=float(
                quality[
                    "absolute_flow_strength"
                ]["minimum_flow"]
            ),
            directional_strong_threshold=float(
                quality[
                    "directional_flow_confirmation"
                ]["strong_threshold"]
            ),
            all_opening_trades_points=float(
                quality[
                    "opening_evidence"
                ]["all_opening_trades_points"]
            ),
        )


@dataclass(frozen=True)
class QualityEvidenceResult:
    absolute_flow_strength: float
    absolute_flow_strength_status: GateStatus

    vwap_distance_atr: float | None
    vwap_distance_atr_status: GateStatus

    sweep_ratio: float | None
    sweep_ratio_status: GateStatus

    opening_evidence: float | None
    opening_evidence_status: GateStatus

    negative_gamma_regime: bool | None
    negative_gamma_regime_status: GateStatus

    directional_flow_confirmation: float | None
    directional_flow_confirmation_status: GateStatus


class QualityEvidenceService:
    """
    Derive only currently-supported weekly_v1
    atomic quality evidence.

    Sources:
    - absolute flow:
        abs(FlowSnapshot.net_flow)

    - VWAP distance / ATR:
        abs(underlying_price - weekly_vwap) / atr_1h

    - sweep ratio:
        sweep_premium / total_premium

    - directional flow confirmation:
        direction.sign * directional_net
        / (bullish_premium + bearish_premium)

    Missing/undefined evidence becomes UNKNOWN.

    No API calls and no database writes.
    """

    def __init__(
        self,
        settings: QualityEvidenceSettings | None = None,
    ) -> None:
        self.settings = (
            settings
            or QualityEvidenceSettings.from_config()
        )

    def evaluate(
        self,
        *,
        direction: Direction,
        flow_snapshot: FlowSnapshot,
        feature: SignalFeature,
        total_gex: float | None = None,
    ) -> QualityEvidenceResult:

        if not isinstance(direction, Direction):
            raise QualityEvidenceError(
                "direction must be Direction."
            )

        if not isinstance(
            flow_snapshot,
            FlowSnapshot,
        ):
            raise QualityEvidenceError(
                "flow_snapshot must be FlowSnapshot."
            )

        if not isinstance(
            feature,
            SignalFeature,
        ):
            raise QualityEvidenceError(
                "feature must be SignalFeature."
            )

        # --------------------------------------------------
        # ABSOLUTE FLOW STRENGTH
        # --------------------------------------------------

        absolute_flow_strength = abs(
            float(flow_snapshot.net_flow)
        )

        absolute_flow_strength_status = (
            GateStatus.PASS
            if (
                absolute_flow_strength
                >= self.settings.absolute_flow_minimum
            )
            else GateStatus.FAIL
        )

        # --------------------------------------------------
        # VWAP DISTANCE / ATR
        # --------------------------------------------------

        vwap_distance_atr = None
        vwap_distance_atr_status = GateStatus.UNKNOWN

        if (
            feature.underlying_price is not None
            and feature.weekly_vwap is not None
            and feature.atr_1h is not None
            and feature.atr_1h > 0
            and feature.vwap_status
            in (
                GateStatus.PASS,
                GateStatus.FAIL,
            )
        ):
            vwap_distance_atr = (
                abs(
                    float(feature.underlying_price)
                    - float(feature.weekly_vwap)
                )
                / float(feature.atr_1h)
            )

            vwap_distance_atr_status = (
                feature.vwap_status
            )

        # --------------------------------------------------
        # SWEEP RATIO
        # --------------------------------------------------

        sweep_ratio = None
        sweep_ratio_status = GateStatus.UNKNOWN

        if (
            flow_snapshot.total_premium is not None
            and flow_snapshot.sweep_premium is not None
            and flow_snapshot.total_premium > 0
        ):
            sweep_ratio = (
                float(flow_snapshot.sweep_premium)
                / float(flow_snapshot.total_premium)
            )

            sweep_ratio_status = GateStatus.PASS

        # --------------------------------------------------
        # OPENING EVIDENCE
        # --------------------------------------------------

        opening_evidence = None
        opening_evidence_status = GateStatus.UNKNOWN

        if (
            flow_snapshot.deduped_alert_count > 0
            and flow_snapshot.opening_alert_count
            == flow_snapshot.deduped_alert_count
        ):
            opening_evidence = (
                self.settings.all_opening_trades_points
            )
            opening_evidence_status = GateStatus.PASS

        # --------------------------------------------------
        # NEGATIVE GAMMA REGIME
        # --------------------------------------------------

        negative_gamma_regime = None
        negative_gamma_regime_status = GateStatus.UNKNOWN

        if total_gex is not None:
            negative_gamma_regime = (
                float(total_gex) < 0
            )
            negative_gamma_regime_status = (
                GateStatus.PASS
            )

        # --------------------------------------------------
        # DIRECTIONAL FLOW CONFIRMATION
        # --------------------------------------------------

        directional_flow_confirmation = None
        directional_flow_confirmation_status = (
            GateStatus.UNKNOWN
        )

        directional_denominator = (
            float(flow_snapshot.bullish_premium)
            + float(flow_snapshot.bearish_premium)
        )

        if directional_denominator > 0:
            directional_flow_confirmation = (
                float(direction.sign)
                * float(flow_snapshot.directional_net)
                / directional_denominator
            )

            directional_flow_confirmation_status = (
                GateStatus.PASS
                if directional_flow_confirmation > 0
                else GateStatus.FAIL
            )

        return QualityEvidenceResult(
            absolute_flow_strength=(
                absolute_flow_strength
            ),
            absolute_flow_strength_status=(
                absolute_flow_strength_status
            ),

            vwap_distance_atr=(
                vwap_distance_atr
            ),
            vwap_distance_atr_status=(
                vwap_distance_atr_status
            ),

            sweep_ratio=sweep_ratio,
            sweep_ratio_status=(
                sweep_ratio_status
            ),

            opening_evidence=(
                opening_evidence
            ),
            opening_evidence_status=(
                opening_evidence_status
            ),

            negative_gamma_regime=(
                negative_gamma_regime
            ),
            negative_gamma_regime_status=(
                negative_gamma_regime_status
            ),

            directional_flow_confirmation=(
                directional_flow_confirmation
            ),
            directional_flow_confirmation_status=(
                directional_flow_confirmation_status
            ),
        )
