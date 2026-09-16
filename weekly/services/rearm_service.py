from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from weekly.domain.models import Signal
from weekly.services.calendar_service import as_et


@dataclass(frozen=True)
class ReArmEvaluation:
    allowed: bool
    reason: str
    aligned_flow: float | None
    cooldown_until: datetime | None


class ReArmService:
    """
    Evaluate frozen weekly_v1 same-session ReArm rules.

    This service intentionally does NOT yet:
    - create Candidate #2+
    - define a new confirmation window
    - transition to ACCELERATED
    - submit or prepare trades

    Candidate creation timing is kept separate until
    its exact runtime timestamp semantics are fixed.
    """

    @staticmethod
    def calculate_aligned_flow(
        *,
        signal: Signal,
        current_net_flow: float,
    ) -> float:
        if signal.net_flow_at_confirmation is None:
            raise ValueError(
                "signal.net_flow_at_confirmation is required"
            )

        return signal.signal_sign * (
            current_net_flow
            - signal.net_flow_at_confirmation
        )

    def evaluate(
        self,
        *,
        previous_signal: Signal,
        current_trading_date_et: date,
        as_of: datetime,
        current_net_flow: float,
        rearm_aligned_flow_min: float,
        cooldown_minutes: int,
        new_trigger_bar_close: datetime | None,
    ) -> ReArmEvaluation:
        if as_of.tzinfo is None:
            raise ValueError(
                "as_of must be timezone-aware"
            )

        if rearm_aligned_flow_min <= 0:
            raise ValueError(
                "rearm_aligned_flow_min must be > 0"
            )

        if cooldown_minutes <= 0:
            raise ValueError(
                "cooldown_minutes must be > 0"
            )

        if previous_signal.confirmed_at is None:
            raise ValueError(
                "previous_signal.confirmed_at is required"
            )

        if (
            previous_signal.net_flow_at_confirmation
            is None
        ):
            raise ValueError(
                "previous_signal.net_flow_at_confirmation "
                "is required"
            )

        confirmed_at = as_et(
            previous_signal.confirmed_at
        )
        as_of_et = as_et(as_of)

        cooldown_until = (
            confirmed_at
            + timedelta(minutes=cooldown_minutes)
        )

        if (
            current_trading_date_et
            != previous_signal.trading_date_et
        ):
            return ReArmEvaluation(
                allowed=False,
                reason="DIFFERENT_TRADING_DATE_ET",
                aligned_flow=None,
                cooldown_until=cooldown_until,
            )

        if as_of_et < cooldown_until:
            return ReArmEvaluation(
                allowed=False,
                reason="COOLDOWN_ACTIVE",
                aligned_flow=None,
                cooldown_until=cooldown_until,
            )

        aligned_flow = self.calculate_aligned_flow(
            signal=previous_signal,
            current_net_flow=current_net_flow,
        )

        if aligned_flow < rearm_aligned_flow_min:
            return ReArmEvaluation(
                allowed=False,
                reason="INSUFFICIENT_ALIGNED_FLOW",
                aligned_flow=aligned_flow,
                cooldown_until=cooldown_until,
            )

        if new_trigger_bar_close is None:
            return ReArmEvaluation(
                allowed=False,
                reason="NO_NEW_PRICE_TRIGGER",
                aligned_flow=aligned_flow,
                cooldown_until=cooldown_until,
            )

        if new_trigger_bar_close.tzinfo is None:
            raise ValueError(
                "new_trigger_bar_close must be "
                "timezone-aware"
            )

        trigger_close_et = as_et(
            new_trigger_bar_close
        )

        if trigger_close_et <= confirmed_at:
            return ReArmEvaluation(
                allowed=False,
                reason="STALE_PRICE_TRIGGER",
                aligned_flow=aligned_flow,
                cooldown_until=cooldown_until,
            )

        return ReArmEvaluation(
            allowed=True,
            reason="REARM_ALLOWED",
            aligned_flow=aligned_flow,
            cooldown_until=cooldown_until,
        )
