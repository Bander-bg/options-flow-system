from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from weekly.domain.enums import Direction
from weekly.domain.models import Signal
from weekly.services.flow_service import get_base_flow_direction


class SignalInvalidationError(ValueError):
    """Raised when signal invalidation inputs are invalid."""


@dataclass(frozen=True)
class SignalInvalidationResult:
    invalidated: bool
    reason: str
    current_base_direction: Direction | None
    session_cut_window: bool


class SignalInvalidationService:
    """
    Re-validates the PRIMARY Base Flow hypothesis for an unresolved
    weekly_v1 Candidate.

    Directional Net is intentionally excluded because it is
    quality-only evidence and must never invalidate the primary
    Candidate hypothesis by itself.
    """

    def evaluate(
        self,
        *,
        signal: Signal,
        current_net_flow: float,
        flow_threshold: float,
        as_of: datetime,
    ) -> SignalInvalidationResult:

        self._validate(
            signal=signal,
            current_net_flow=current_net_flow,
            flow_threshold=flow_threshold,
            as_of=as_of,
        )

        current_direction = get_base_flow_direction(
            net_flow=current_net_flow,
            threshold=flow_threshold,
        )

        session_cut_window = (
            signal.requested_confirmation_deadline_at
            > signal.confirmation_deadline_at
        )

        # Highest-priority hypothesis check:
        # the original Base Flow hypothesis disappeared.
        if current_direction is None:
            return SignalInvalidationResult(
                invalidated=True,
                reason="FLOW_HYPOTHESIS_DISAPPEARED",
                current_base_direction=None,
                session_cut_window=session_cut_window,
            )

        # Original Base Flow hypothesis reversed.
        if current_direction is not signal.direction:
            return SignalInvalidationResult(
                invalidated=True,
                reason="FLOW_DIRECTION_REVERSED",
                current_base_direction=current_direction,
                session_cut_window=session_cut_window,
            )

        # The requested confirmation window did not fully fit inside
        # the official trading session. This becomes invalid only
        # when the clipped actual deadline is reached.
        if (
            session_cut_window
            and as_of >= signal.confirmation_deadline_at
        ):
            return SignalInvalidationResult(
                invalidated=True,
                reason="SESSION_CLOSED_BEFORE_FULL_CONFIRMATION_WINDOW",
                current_base_direction=current_direction,
                session_cut_window=True,
            )

        return SignalInvalidationResult(
            invalidated=False,
            reason="FLOW_HYPOTHESIS_VALID",
            current_base_direction=current_direction,
            session_cut_window=session_cut_window,
        )

    @staticmethod
    def _validate(
        *,
        signal: Signal,
        current_net_flow: float,
        flow_threshold: float,
        as_of: datetime,
    ) -> None:

        if signal.direction not in (
            Direction.BULLISH,
            Direction.BEARISH,
        ):
            raise SignalInvalidationError(
                "signal.direction must be BULLISH or BEARISH."
            )

        if signal.requested_confirmation_deadline_at is None:
            raise SignalInvalidationError(
                "signal.requested_confirmation_deadline_at is required."
            )

        if signal.confirmation_deadline_at is None:
            raise SignalInvalidationError(
                "signal.confirmation_deadline_at is required."
            )

        if flow_threshold <= 0:
            raise SignalInvalidationError(
                "flow_threshold must be > 0."
            )

        if as_of.tzinfo is None:
            raise SignalInvalidationError(
                "as_of must be timezone-aware."
            )

        if not isinstance(current_net_flow, (int, float)):
            raise SignalInvalidationError(
                "current_net_flow must be numeric."
            )
