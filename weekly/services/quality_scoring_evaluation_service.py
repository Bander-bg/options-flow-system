from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.domain.models import SignalFeature
from weekly.services.quality_scoring_service import (
    QualityScoringResult,
    QualityScoringService,
)


class QualityScoringEvaluationError(ValueError):
    """Invalid quality-scoring evaluation/persistence input."""


@dataclass(frozen=True)
class QualityScoringEvaluation:
    """
    One completed quality-scoring evaluation persisted
    as an immutable SignalFeature snapshot.
    """

    result: QualityScoringResult
    feature: SignalFeature


class QualityScoringEvaluationService:
    """
    Connect QualityScoringService to SignalFeatureRepository.

    Responsibilities:
    1. Load the latest SignalFeature evidence snapshot.
    2. Calculate quality score, volatility penalty,
       coverage, and grades.
    3. Preserve all existing atomic/unrelated fields.
    4. Write one new immutable SignalFeature snapshot.
    5. Never change Signal state.

    A previous SignalFeature is required because quality
    scoring must operate on already-collected evidence.
    """

    def __init__(
        self,
        *,
        quality_scoring_service: QualityScoringService,
        feature_repository: SignalFeatureRepository,
    ) -> None:
        self.quality_scoring_service = (
            quality_scoring_service
        )
        self.feature_repository = (
            feature_repository
        )

    def evaluate_and_persist(
        self,
        *,
        signal_id: int,
        captured_at: datetime,
    ) -> QualityScoringEvaluation:
        self._validate_inputs(
            signal_id=signal_id,
            captured_at=captured_at,
        )

        previous = (
            self.feature_repository
            .get_latest_for_signal(
                signal_id
            )
        )

        if previous is None:
            raise QualityScoringEvaluationError(
                "Quality scoring requires an existing "
                "SignalFeature evidence snapshot."
            )

        if captured_at < previous.captured_at:
            raise QualityScoringEvaluationError(
                "captured_at cannot be earlier than "
                "the latest SignalFeature snapshot."
            )

        result = (
            self.quality_scoring_service.evaluate(
                feature=previous
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

            base_score=result.base_score,
            volatility_penalty=(
                result.volatility_penalty
            ),
            final_score=result.final_score,

            coverage_points=(
                result.coverage_points
            ),
            coverage_pct=result.coverage_pct,

            raw_grade=result.raw_grade,
            final_grade=result.final_grade,
        )

        created = (
            self.feature_repository.create(
                feature
            )
        )

        return QualityScoringEvaluation(
            result=result,
            feature=created,
        )

    @staticmethod
    def _validate_inputs(
        *,
        signal_id: int,
        captured_at: datetime,
    ) -> None:
        if signal_id < 1:
            raise QualityScoringEvaluationError(
                "signal_id must be >= 1."
            )

        if captured_at.tzinfo is None:
            raise QualityScoringEvaluationError(
                "captured_at must be timezone-aware."
            )
