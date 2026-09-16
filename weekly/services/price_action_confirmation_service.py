from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from weekly.domain.enums import GateStatus
from weekly.domain.models import SignalFeature


class PriceActionConfirmationError(ValueError):
    """Invalid Price Action confirmation-window input."""


@dataclass(frozen=True)
class PriceActionConfirmationResult:
    status: GateStatus

    is_final: bool
    reason: str

    evaluations_seen: int

    pass_evaluations: int
    fail_evaluations: int
    unknown_evaluations: int

    matched_feature_id: int | None = None
    matched_evaluation_sequence: int | None = None
    matched_bar_at: datetime | None = None


class PriceActionConfirmationService:
    """
    Resolve the 30-minute Price Action confirmation window.

    Rules
    -----
    1. Any completed eligible 15m bar with PASS:
       -> final PASS immediately.

    2. A single FAIL does NOT reject the signal while
       the confirmation window is still open.

    3. Before the deadline, if no PASS exists:
       -> UNKNOWN / not final.

    4. At or after the deadline:
       - no evaluations -> final UNKNOWN
       - any unresolved UNKNOWN evaluation -> final UNKNOWN
       - otherwise all available evaluations are FAIL
         -> final FAIL

    This service does NOT mutate Signal state.
    """

    def resolve(
        self,
        *,
        candidate_at: datetime,
        confirmation_deadline_at: datetime,
        as_of: datetime,
        features: Sequence[SignalFeature],
    ) -> PriceActionConfirmationResult:

        self._validate_times(
            candidate_at=candidate_at,
            confirmation_deadline_at=(
                confirmation_deadline_at
            ),
            as_of=as_of,
        )

        evaluations = (
            self._eligible_evaluations(
                candidate_at=candidate_at,
                confirmation_deadline_at=(
                    confirmation_deadline_at
                ),
                features=features,
            )
        )

        passes = [
            feature
            for feature in evaluations
            if (
                feature.price_action_status
                == GateStatus.PASS
            )
        ]

        fails = [
            feature
            for feature in evaluations
            if (
                feature.price_action_status
                == GateStatus.FAIL
            )
        ]

        unknowns = [
            feature
            for feature in evaluations
            if (
                feature.price_action_status
                == GateStatus.UNKNOWN
            )
        ]

        # --------------------------------------------------
        # PASS CONFIRMS IMMEDIATELY
        # --------------------------------------------------

        if passes:
            matched = min(
                passes,
                key=lambda feature: (
                    feature.price_action_bar_at,
                    feature.evaluation_sequence,
                ),
            )

            return PriceActionConfirmationResult(
                status=GateStatus.PASS,
                is_final=True,
                reason=(
                    "PRICE_ACTION_CONFIRMED"
                ),
                evaluations_seen=len(
                    evaluations
                ),
                pass_evaluations=len(passes),
                fail_evaluations=len(fails),
                unknown_evaluations=len(
                    unknowns
                ),
                matched_feature_id=(
                    matched.id
                ),
                matched_evaluation_sequence=(
                    matched.evaluation_sequence
                ),
                matched_bar_at=(
                    matched.price_action_bar_at
                ),
            )

        # --------------------------------------------------
        # WINDOW STILL OPEN
        # --------------------------------------------------

        if as_of < confirmation_deadline_at:
            return PriceActionConfirmationResult(
                status=GateStatus.UNKNOWN,
                is_final=False,
                reason=(
                    "CONFIRMATION_WINDOW_OPEN"
                ),
                evaluations_seen=len(
                    evaluations
                ),
                pass_evaluations=0,
                fail_evaluations=len(fails),
                unknown_evaluations=len(
                    unknowns
                ),
            )

        # --------------------------------------------------
        # WINDOW CLOSED — NO EVALUATIONS
        # --------------------------------------------------

        if not evaluations:
            return PriceActionConfirmationResult(
                status=GateStatus.UNKNOWN,
                is_final=True,
                reason=(
                    "NO_PRICE_ACTION_EVALUATIONS"
                ),
                evaluations_seen=0,
                pass_evaluations=0,
                fail_evaluations=0,
                unknown_evaluations=0,
            )

        # --------------------------------------------------
        # WINDOW CLOSED — DATA WAS UNRESOLVED
        # --------------------------------------------------

        if unknowns:
            return PriceActionConfirmationResult(
                status=GateStatus.UNKNOWN,
                is_final=True,
                reason=(
                    "PRICE_ACTION_DATA_UNRESOLVED"
                ),
                evaluations_seen=len(
                    evaluations
                ),
                pass_evaluations=0,
                fail_evaluations=len(fails),
                unknown_evaluations=len(
                    unknowns
                ),
            )

        # --------------------------------------------------
        # WINDOW CLOSED — NO PASS, ALL EVALUATED BARS FAIL
        # --------------------------------------------------

        return PriceActionConfirmationResult(
            status=GateStatus.FAIL,
            is_final=True,
            reason=(
                "CONFIRMATION_WINDOW_EXPIRED_NO_PASS"
            ),
            evaluations_seen=len(
                evaluations
            ),
            pass_evaluations=0,
            fail_evaluations=len(fails),
            unknown_evaluations=0,
        )

    # ==================================================
    # ELIGIBLE EVALUATIONS
    # ==================================================

    def _eligible_evaluations(
        self,
        *,
        candidate_at: datetime,
        confirmation_deadline_at: datetime,
        features: Sequence[SignalFeature],
    ) -> list[SignalFeature]:
        """
        Extract unique Price Action bar evaluations.

        SignalFeature is an immutable snapshot, so a later
        unrelated snapshot may carry forward the same
        price_action_bar_at and status.

        Therefore evaluations are deduplicated by
        price_action_bar_at. For the same bar timestamp,
        the highest evaluation_sequence wins.
        """

        by_bar_at: dict[
            datetime,
            SignalFeature,
        ] = {}

        for feature in features:
            bar_at = (
                feature.price_action_bar_at
            )

            status = (
                feature.price_action_status
            )

            if (
                bar_at is None
                or status is None
            ):
                continue

            if bar_at.tzinfo is None:
                raise PriceActionConfirmationError(
                    "price_action_bar_at must be "
                    "timezone-aware."
                )

            # A fresh trigger bar evaluated by the existing
            # PriceActionService closes AFTER candidate_at.
            if bar_at <= candidate_at:
                continue

            if (
                bar_at
                > confirmation_deadline_at
            ):
                continue

            existing = by_bar_at.get(
                bar_at
            )

            if (
                existing is None
                or (
                    feature.evaluation_sequence
                    > existing.evaluation_sequence
                )
            ):
                by_bar_at[
                    bar_at
                ] = feature

        return sorted(
            by_bar_at.values(),
            key=lambda feature: (
                feature.price_action_bar_at,
                feature.evaluation_sequence,
            ),
        )

    # ==================================================
    # VALIDATION
    # ==================================================

    def _validate_times(
        self,
        *,
        candidate_at: datetime,
        confirmation_deadline_at: datetime,
        as_of: datetime,
    ) -> None:
        for name, value in (
            (
                "candidate_at",
                candidate_at,
            ),
            (
                "confirmation_deadline_at",
                confirmation_deadline_at,
            ),
            (
                "as_of",
                as_of,
            ),
        ):
            if value.tzinfo is None:
                raise PriceActionConfirmationError(
                    f"{name} must be "
                    "timezone-aware."
                )

        if (
            confirmation_deadline_at
            < candidate_at
        ):
            raise PriceActionConfirmationError(
                "confirmation_deadline_at "
                "cannot be before candidate_at."
            )

        if as_of < candidate_at:
            raise PriceActionConfirmationError(
                "as_of cannot be before candidate_at."
            )