from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Sequence

from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.domain.enums import Direction
from weekly.domain.models import SignalFeature
from weekly.providers.alpaca_stock_provider import (
    StockMinuteBar,
)
from weekly.services.efficiency_ratio_service import (
    EfficiencyRatioResult,
    EfficiencyRatioService,
)
from weekly.services.weekly_vwap_service import (
    WeeklyVWAPResult,
    WeeklyVWAPService,
)


class MarketRegimeEvaluationError(ValueError):
    """Invalid market-regime evaluation/persistence input."""


@dataclass(frozen=True)
class MarketRegimeEvaluation:
    """
    One completed Weekly VWAP + ER evaluation.

    vwap_result:
        Pure Weekly VWAP calculation result.

    efficiency_ratio_result:
        Pure weekly Efficiency Ratio calculation result.

    feature:
        Immutable SignalFeature snapshot persisted
        to SQLite.
    """

    vwap_result: WeeklyVWAPResult
    efficiency_ratio_result: EfficiencyRatioResult
    feature: SignalFeature


class MarketRegimeEvaluationService:
    """
    Connect WeeklyVWAPService and EfficiencyRatioService
    to SignalFeatureRepository.

    Responsibilities:
    1. Evaluate Weekly VWAP.
    2. Evaluate weekly Efficiency Ratio.
    3. Preserve existing unrelated SignalFeature data.
    4. Write one new immutable SignalFeature snapshot.
    5. Never change Signal state.

    State resolution is intentionally handled elsewhere.
    """

    def __init__(
        self,
        *,
        weekly_vwap_service: WeeklyVWAPService,
        efficiency_ratio_service: EfficiencyRatioService,
        feature_repository: SignalFeatureRepository,
    ) -> None:
        self.weekly_vwap_service = weekly_vwap_service
        self.efficiency_ratio_service = (
            efficiency_ratio_service
        )
        self.feature_repository = feature_repository

    def evaluate_and_persist(
        self,
        *,
        signal_id: int,
        direction: Direction,
        as_of: datetime,
        trading_date_et: date,
        calendar,
        minute_bars: Sequence[StockMinuteBar],
        captured_at: datetime,
    ) -> MarketRegimeEvaluation:
        """
        Evaluate both market-regime gates and persist
        one SignalFeature snapshot.

        If a previous SignalFeature exists, every unrelated
        field is carried forward unchanged.
        """

        self._validate_inputs(
            signal_id=signal_id,
            as_of=as_of,
            captured_at=captured_at,
        )

        vwap_result = (
            self.weekly_vwap_service.evaluate(
                direction=direction,
                as_of=as_of,
                trading_date_et=trading_date_et,
                calendar=calendar,
                minute_bars=minute_bars,
            )
        )

        efficiency_ratio_result = (
            self.efficiency_ratio_service.evaluate(
                as_of=as_of,
                trading_date_et=trading_date_et,
                calendar=calendar,
                minute_bars=minute_bars,
            )
        )

        next_sequence = (
            self.feature_repository
            .next_evaluation_sequence(
                signal_id
            )
        )

        previous = (
            self.feature_repository
            .get_latest_for_signal(
                signal_id
            )
        )

        if previous is None:
            feature = SignalFeature(
                signal_id=signal_id,
                evaluation_sequence=next_sequence,
                captured_at=captured_at,
                weekly_vwap=(
                    vwap_result.weekly_vwap
                ),
                underlying_price=(
                    vwap_result.underlying_price
                ),
                vwap_status=(
                    vwap_result.status
                ),
                efficiency_ratio=(
                    efficiency_ratio_result
                    .efficiency_ratio
                ),
                efficiency_ratio_status=(
                    efficiency_ratio_result.status
                ),
            )

        else:
            feature = replace(
                previous,
                id=None,
                evaluation_sequence=next_sequence,
                captured_at=captured_at,
                weekly_vwap=(
                    vwap_result.weekly_vwap
                ),
                underlying_price=(
                    vwap_result.underlying_price
                ),
                vwap_status=(
                    vwap_result.status
                ),
                efficiency_ratio=(
                    efficiency_ratio_result
                    .efficiency_ratio
                ),
                efficiency_ratio_status=(
                    efficiency_ratio_result.status
                ),
            )

        created = (
            self.feature_repository.create(
                feature
            )
        )

        return MarketRegimeEvaluation(
            vwap_result=vwap_result,
            efficiency_ratio_result=(
                efficiency_ratio_result
            ),
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
            raise MarketRegimeEvaluationError(
                "signal_id must be >= 1."
            )

        if as_of.tzinfo is None:
            raise MarketRegimeEvaluationError(
                "as_of must be timezone-aware."
            )

        if captured_at.tzinfo is None:
            raise MarketRegimeEvaluationError(
                "captured_at must be timezone-aware."
            )

        if captured_at < as_of:
            raise MarketRegimeEvaluationError(
                "captured_at cannot be earlier than as_of."
            )
