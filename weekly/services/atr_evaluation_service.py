from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Sequence

from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.domain.models import SignalFeature
from weekly.providers.alpaca_stock_provider import (
    StockMinuteBar,
)
from weekly.services.atr_service import (
    ATRResult,
    ATRService,
)


class ATREvaluationError(ValueError):
    """Invalid ATR evaluation/persistence input."""


@dataclass(frozen=True)
class ATREvaluation:
    """
    One ATR evaluation persisted as an immutable
    SignalFeature snapshot.
    """

    result: ATRResult
    feature: SignalFeature


class ATREvaluationService:
    """
    Connect ATRService to SignalFeatureRepository.

    Responsibilities:
    1. Calculate rolling 1H and 15m ATR.
    2. Preserve unrelated SignalFeature evidence.
    3. Persist one immutable SignalFeature snapshot.
    4. Never change Signal state.
    """

    def __init__(
        self,
        *,
        atr_service: ATRService,
        feature_repository: SignalFeatureRepository,
    ) -> None:
        self.atr_service = atr_service
        self.feature_repository = feature_repository

    def evaluate_and_persist(
        self,
        *,
        signal_id: int,
        as_of: datetime,
        trading_date_et: date,
        calendar,
        minute_bars: Sequence[StockMinuteBar],
        captured_at: datetime,
    ) -> ATREvaluation:
        self._validate_inputs(
            signal_id=signal_id,
            as_of=as_of,
            captured_at=captured_at,
        )

        result = self.atr_service.evaluate(
            as_of=as_of,
            trading_date_et=trading_date_et,
            calendar=calendar,
            minute_bars=minute_bars,
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
                atr_1h=result.atr_1h,
                atr_15m=result.atr_15m,
            )
        else:
            feature = replace(
                previous,
                id=None,
                evaluation_sequence=next_sequence,
                captured_at=captured_at,
                atr_1h=result.atr_1h,
                atr_15m=result.atr_15m,
            )

        created = self.feature_repository.create(
            feature
        )

        return ATREvaluation(
            result=result,
            feature=created,
        )

    @staticmethod
    def _validate_inputs(
        *,
        signal_id: int,
        as_of: datetime,
        captured_at: datetime,
    ) -> None:
        if signal_id < 1:
            raise ATREvaluationError(
                "signal_id must be >= 1."
            )

        if as_of.tzinfo is None:
            raise ATREvaluationError(
                "as_of must be timezone-aware."
            )

        if captured_at.tzinfo is None:
            raise ATREvaluationError(
                "captured_at must be timezone-aware."
            )

        if captured_at < as_of:
            raise ATREvaluationError(
                "captured_at cannot be earlier than as_of."
            )
