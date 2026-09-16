from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from weekly.db.flow_snapshot_repository import (
    FlowSnapshotRepository,
)
from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.db.signal_repository import (
    SignalRepository,
)
from weekly.domain.models import (
    FlowSnapshot,
    SignalFeature,
)
from weekly.services.quality_evidence_service import (
    QualityEvidenceResult,
    QualityEvidenceService,
)


class QualityEvidenceEvaluationError(ValueError):
    """Invalid quality-evidence evaluation/persistence input."""


@dataclass(frozen=True)
class QualityEvidenceEvaluation:
    """
    One quality-evidence evaluation persisted as an
    immutable SignalFeature snapshot.
    """

    result: QualityEvidenceResult
    flow_snapshot: FlowSnapshot
    feature: SignalFeature


class QualityEvidenceEvaluationService:
    """
    Connect QualityEvidenceService to repositories.

    Responsibilities:
    1. Load the Signal by id.
    2. Load its latest SignalFeature snapshot.
    3. Load the latest FlowSnapshot for the exact
       ticker/session/target-expiry.
    4. Derive supported atomic quality evidence.
    5. Preserve all unrelated SignalFeature fields.
    6. Persist one new immutable SignalFeature snapshot.
    7. Never change Signal state.
    """

    def __init__(
        self,
        *,
        quality_evidence_service: QualityEvidenceService,
        signal_repository: SignalRepository,
        flow_snapshot_repository: FlowSnapshotRepository,
        feature_repository: SignalFeatureRepository,
    ) -> None:
        self.quality_evidence_service = (
            quality_evidence_service
        )
        self.signal_repository = (
            signal_repository
        )
        self.flow_snapshot_repository = (
            flow_snapshot_repository
        )
        self.feature_repository = (
            feature_repository
        )

    def evaluate_and_persist(
        self,
        *,
        signal_id: int,
        captured_at: datetime,
        total_gex: float | None = None,
    ) -> QualityEvidenceEvaluation:
        self._validate_inputs(
            signal_id=signal_id,
            captured_at=captured_at,
        )

        signal = self.signal_repository.get_by_id(
            signal_id
        )

        if signal is None:
            raise QualityEvidenceEvaluationError(
                "Signal not found."
            )

        previous = (
            self.feature_repository
            .get_latest_for_signal(
                signal_id
            )
        )

        if previous is None:
            raise QualityEvidenceEvaluationError(
                "Quality evidence requires an existing "
                "SignalFeature snapshot."
            )

        flow_snapshot = (
            self.flow_snapshot_repository
            .get_latest_for_expiry(
                ticker=signal.ticker,
                trading_date_et=(
                    signal.trading_date_et
                ),
                target_expiry=(
                    signal.target_expiry
                ),
            )
        )

        if flow_snapshot is None:
            raise QualityEvidenceEvaluationError(
                "No FlowSnapshot found for the exact "
                "signal target expiry."
            )

        if captured_at < previous.captured_at:
            raise QualityEvidenceEvaluationError(
                "captured_at cannot be earlier than "
                "the latest SignalFeature snapshot."
            )

        if captured_at < flow_snapshot.captured_at:
            raise QualityEvidenceEvaluationError(
                "captured_at cannot be earlier than "
                "the selected FlowSnapshot."
            )

        result = (
            self.quality_evidence_service.evaluate(
                direction=signal.direction,
                flow_snapshot=flow_snapshot,
                feature=previous,
                total_gex=total_gex,
            )
        )

        next_sequence = (
            self.feature_repository
            .next_evaluation_sequence(
                signal_id
            )
        )

        feature = replace(
            previous,
            id=None,
            evaluation_sequence=next_sequence,
            captured_at=captured_at,

            flow_net=flow_snapshot.net_flow,

            absolute_flow_strength=(
                result.absolute_flow_strength
            ),
            absolute_flow_strength_status=(
                result.absolute_flow_strength_status
            ),

            vwap_distance_atr=(
                result.vwap_distance_atr
            ),
            vwap_distance_atr_status=(
                result.vwap_distance_atr_status
            ),

            sweep_ratio=result.sweep_ratio,
            sweep_ratio_status=(
                result.sweep_ratio_status
            ),

            opening_evidence=(
                result.opening_evidence
            ),
            opening_evidence_status=(
                result.opening_evidence_status
            ),

            negative_gamma_regime=(
                result.negative_gamma_regime
            ),
            negative_gamma_regime_status=(
                result.negative_gamma_regime_status
            ),

            directional_flow_confirmation=(
                result.directional_flow_confirmation
            ),
            directional_flow_confirmation_status=(
                result
                .directional_flow_confirmation_status
            ),
        )

        created = self.feature_repository.create(
            feature
        )

        return QualityEvidenceEvaluation(
            result=result,
            flow_snapshot=flow_snapshot,
            feature=created,
        )

    @staticmethod
    def _validate_inputs(
        *,
        signal_id: int,
        captured_at: datetime,
    ) -> None:
        if signal_id < 1:
            raise QualityEvidenceEvaluationError(
                "signal_id must be >= 1."
            )

        if captured_at.tzinfo is None:
            raise QualityEvidenceEvaluationError(
                "captured_at must be timezone-aware."
            )
