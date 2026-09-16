from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Sequence

from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.domain.enums import Direction
from weekly.domain.models import SignalFeature
from weekly.services.price_action_service import (
    PriceActionResult,
    PriceActionService,
    PriceBar,
)


class PriceActionEvaluationError(ValueError):
    """Invalid Price Action evaluation/persistence input."""


@dataclass(frozen=True)
class PriceActionEvaluation:
    """
    One completed Price Action evaluation.

    result:
        Pure calculation result.

    feature:
        Immutable SignalFeature snapshot persisted
        to SQLite.
    """

    result: PriceActionResult
    feature: SignalFeature


class PriceActionEvaluationService:
    """
    Connect PriceActionService to SignalFeatureRepository.

    Responsibilities:
    1. Evaluate one completed 15m trigger bar.
    2. Preserve existing non-Price-Action feature data.
    3. Write a new immutable SignalFeature snapshot.
    4. Never change Signal state.

    State transitions are intentionally handled
    elsewhere.
    """

    def __init__(
        self,
        *,
        price_action_service: PriceActionService,
        feature_repository: SignalFeatureRepository,
    ) -> None:
        self.price_action_service = (
            price_action_service
        )

        self.feature_repository = (
            feature_repository
        )

    def evaluate_and_persist(
        self,
        *,
        signal_id: int,
        direction: Direction,
        candidate_at: datetime,
        confirmation_deadline_at: datetime,
        captured_at: datetime,
        trigger_bar: PriceBar,
        prior_bars: Sequence[PriceBar],
        atr_15m: float | None,
        historical_same_slot_volumes: Sequence[
            float
        ],
        atr_1h: float | None = None,
    ) -> PriceActionEvaluation:
        """
        Evaluate and persist one completed 15m bar.

        A previous SignalFeature snapshot, if one exists,
        is carried forward so unrelated feature values
        are not lost.

        Price Action fields are always replaced with the
        newest evaluation result.
        """

        self._validate_inputs(
            signal_id=signal_id,
            captured_at=captured_at,
            atr_1h=atr_1h,
        )

        result = (
            self.price_action_service
            .evaluate_bar(
                direction=direction,
                candidate_at=candidate_at,
                confirmation_deadline_at=(
                    confirmation_deadline_at
                ),
                trigger_bar=trigger_bar,
                prior_bars=prior_bars,
                atr_15m=atr_15m,
                historical_same_slot_volumes=(
                    historical_same_slot_volumes
                ),
            )
        )

        if (
            captured_at
            < result.price_action_bar_at
        ):
            raise PriceActionEvaluationError(
                "captured_at cannot be earlier "
                "than price_action_bar_at."
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
                evaluation_sequence=(
                    next_sequence
                ),
                captured_at=captured_at,

                structure_status=(
                    result.structure_status
                ),

                impulse_status=(
                    result.impulse_status
                ),

                participation_status=(
                    result.participation_status
                ),

                price_action_pass_count=(
                    result
                    .price_action_pass_count
                ),

                price_action_status=(
                    result.price_action_status
                ),

                price_action_bar_at=(
                    result.price_action_bar_at
                ),

                trigger_open=(
                    result.trigger_open
                ),

                trigger_high=(
                    result.trigger_high
                ),

                trigger_low=(
                    result.trigger_low
                ),

                trigger_close=(
                    result.trigger_close
                ),

                trigger_volume=(
                    result.trigger_volume
                ),

                structure_reference_level=(
                    result
                    .structure_reference_level
                ),

                structure_break_level=(
                    result
                    .structure_break_level
                ),

                impulse_body=(
                    result.impulse_body
                ),

                impulse_median_body=(
                    result
                    .impulse_median_body
                ),

                impulse_body_atr_ratio=(
                    result
                    .impulse_body_atr_ratio
                ),

                impulse_engulfing_match=(
                    result
                    .impulse_engulfing_match
                ),

                impulse_expansion_match=(
                    result
                    .impulse_expansion_match
                ),

                # Legacy field intentionally unused.
                participation_avg_slot_volume=None,

                participation_median_slot_volume=(
                    result
                    .participation_median_slot_volume
                ),

                participation_reference_sessions=(
                    result
                    .participation_reference_sessions
                ),

                participation_rvol=(
                    result.participation_rvol
                ),

                atr_1h=atr_1h,
                atr_15m=atr_15m,
            )

        else:
            feature = replace(
                previous,

                id=None,

                evaluation_sequence=(
                    next_sequence
                ),

                captured_at=captured_at,

                structure_status=(
                    result.structure_status
                ),

                impulse_status=(
                    result.impulse_status
                ),

                participation_status=(
                    result.participation_status
                ),

                price_action_pass_count=(
                    result
                    .price_action_pass_count
                ),

                price_action_status=(
                    result.price_action_status
                ),

                price_action_bar_at=(
                    result.price_action_bar_at
                ),

                trigger_open=(
                    result.trigger_open
                ),

                trigger_high=(
                    result.trigger_high
                ),

                trigger_low=(
                    result.trigger_low
                ),

                trigger_close=(
                    result.trigger_close
                ),

                trigger_volume=(
                    result.trigger_volume
                ),

                structure_reference_level=(
                    result
                    .structure_reference_level
                ),

                structure_break_level=(
                    result
                    .structure_break_level
                ),

                impulse_body=(
                    result.impulse_body
                ),

                impulse_median_body=(
                    result
                    .impulse_median_body
                ),

                impulse_body_atr_ratio=(
                    result
                    .impulse_body_atr_ratio
                ),

                impulse_engulfing_match=(
                    result
                    .impulse_engulfing_match
                ),

                impulse_expansion_match=(
                    result
                    .impulse_expansion_match
                ),

                participation_avg_slot_volume=None,

                participation_median_slot_volume=(
                    result
                    .participation_median_slot_volume
                ),

                participation_reference_sessions=(
                    result
                    .participation_reference_sessions
                ),

                participation_rvol=(
                    result.participation_rvol
                ),

                atr_1h=(
                    previous.atr_1h
                    if atr_1h is None
                    else atr_1h
                ),

                atr_15m=atr_15m,
            )

        created = (
            self.feature_repository.create(
                feature
            )
        )

        return PriceActionEvaluation(
            result=result,
            feature=created,
        )

    def _validate_inputs(
        self,
        *,
        signal_id: int,
        captured_at: datetime,
        atr_1h: float | None,
    ) -> None:
        if signal_id < 1:
            raise PriceActionEvaluationError(
                "signal_id must be >= 1."
            )

        if captured_at.tzinfo is None:
            raise PriceActionEvaluationError(
                "captured_at must be "
                "timezone-aware."
            )

        if (
            atr_1h is not None
            and atr_1h <= 0
        ):
            raise PriceActionEvaluationError(
                "atr_1h must be > 0 "
                "when provided."
            )