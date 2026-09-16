from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.domain.models import SignalFeature
from weekly.services.earnings_event_risk_service import (
    EarningsEventRiskResult,
    EarningsEventRiskService,
)


class EarningsEventRiskEvaluationError(ValueError):
    """Invalid earnings-event evaluation/persistence input."""


@dataclass(frozen=True)
class EarningsEventRiskEvaluation:
    result: EarningsEventRiskResult
    feature: SignalFeature


class EarningsEventRiskEvaluationService:
    """
    Connect EarningsEventRiskService to SignalFeatureRepository.

    Preserves unrelated SignalFeature fields and never changes Signal state.
    """

    def __init__(
        self,
        *,
        earnings_event_risk_service: EarningsEventRiskService,
        feature_repository: SignalFeatureRepository,
    ) -> None:
        self.earnings_event_risk_service = earnings_event_risk_service
        self.feature_repository = feature_repository

    def evaluate_and_persist(
        self,
        *,
        signal_id: int,
        trading_date_et: date,
        target_expiry: date,
        next_earnings_date: date | None,
        earnings_time: str | None,
        captured_at: datetime,
    ) -> EarningsEventRiskEvaluation:
        self._validate_inputs(
            signal_id=signal_id,
            captured_at=captured_at,
        )

        result = self.earnings_event_risk_service.evaluate(
            trading_date_et=trading_date_et,
            target_expiry=target_expiry,
            next_earnings_date=next_earnings_date,
            earnings_time=earnings_time,
        )

        next_sequence = (
            self.feature_repository.next_evaluation_sequence(signal_id)
        )
        previous = (
            self.feature_repository.get_latest_for_signal(signal_id)
        )

        if previous is None:
            feature = SignalFeature(
                signal_id=signal_id,
                evaluation_sequence=next_sequence,
                captured_at=captured_at,
                next_earnings_date=result.next_earnings_date,
                earnings_event_risk_status=result.status,
            )
        else:
            feature = replace(
                previous,
                id=None,
                evaluation_sequence=next_sequence,
                captured_at=captured_at,
                next_earnings_date=result.next_earnings_date,
                earnings_event_risk_status=result.status,
            )

        created = self.feature_repository.create(feature)

        return EarningsEventRiskEvaluation(
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
            raise EarningsEventRiskEvaluationError(
                "signal_id must be >= 1."
            )

        if captured_at.tzinfo is None:
            raise EarningsEventRiskEvaluationError(
                "captured_at must be timezone-aware."
            )