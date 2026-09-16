from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, Iterable, Mapping

from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.domain.models import SignalFeature
from weekly.services.expected_move_service import (
    ExpectedMoveResult,
    ExpectedMoveService,
)


class ExpectedMoveEvaluationError(ValueError):
    """Invalid expected-move evaluation/persistence input."""


@dataclass(frozen=True)
class ExpectedMoveEvaluation:
    """
    One expected-move evaluation persisted as an immutable
    SignalFeature snapshot.
    """

    result: ExpectedMoveResult
    feature: SignalFeature


class ExpectedMoveEvaluationService:
    """
    Connect ExpectedMoveService to SignalFeatureRepository.

    Responsibilities:
    1. Evaluate expected move for the exact target expiry.
    2. Preserve existing unrelated SignalFeature data.
    3. Write one new immutable SignalFeature snapshot.
    4. Never change Signal state.
    """

    def __init__(
        self,
        *,
        expected_move_service: ExpectedMoveService,
        feature_repository: SignalFeatureRepository,
    ) -> None:
        self.expected_move_service = expected_move_service
        self.feature_repository = feature_repository

    def evaluate_and_persist(
        self,
        *,
        signal_id: int,
        trading_date: date,
        target_expiry: date,
        underlying_price: float | None,
        term_structure_rows: Iterable[Mapping[str, Any]] | None,
        atm_iv: float | None,
        captured_at: datetime,
    ) -> ExpectedMoveEvaluation:
        self._validate_inputs(
            signal_id=signal_id,
            captured_at=captured_at,
        )

        result = self.expected_move_service.evaluate(
            trading_date=trading_date,
            target_expiry=target_expiry,
            underlying_price=underlying_price,
            term_structure_rows=term_structure_rows,
            atm_iv=atm_iv,
        )

        next_sequence = (
            self.feature_repository
            .next_evaluation_sequence(signal_id)
        )

        previous = (
            self.feature_repository
            .get_latest_for_signal(signal_id)
        )

        if previous is None:
            feature = SignalFeature(
                signal_id=signal_id,
                evaluation_sequence=next_sequence,
                captured_at=captured_at,
                underlying_price=underlying_price,
                expected_move=result.expected_move,
                expected_move_perc=result.expected_move_perc,
            )
        else:
            feature = replace(
                previous,
                id=None,
                evaluation_sequence=next_sequence,
                captured_at=captured_at,
                underlying_price=previous.underlying_price,
                expected_move=result.expected_move,
                expected_move_perc=result.expected_move_perc,
            )

        created = self.feature_repository.create(feature)

        return ExpectedMoveEvaluation(
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
            raise ExpectedMoveEvaluationError(
                "signal_id must be >= 1."
            )

        if captured_at.tzinfo is None:
            raise ExpectedMoveEvaluationError(
                "captured_at must be timezone-aware."
            )
