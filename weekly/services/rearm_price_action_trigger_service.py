from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from weekly.domain.enums import Direction, GateStatus
from weekly.services.price_action_input_service import (
    PriceActionInput,
)
from weekly.services.price_action_service import (
    PriceActionResult,
    PriceActionService,
)


@dataclass(frozen=True)
class ReArmPriceActionTriggerResult:
    found: bool
    reason: str
    trigger_bar_close: datetime | None
    price_action_result: PriceActionResult | None
    evaluations_checked: int


class ReArmPriceActionTriggerService:
    """
    Find the earliest fresh Price Action PASS
    for weekly_v1 ReArm.

    Inputs must already satisfy the frozen
    ReArm freshness rule:
        trigger_bar.end_at > previous confirmed_at

    This service:
    - reuses the existing PriceActionService
    - uses the same 2-of-3 PASS rule
    - selects the earliest PASS chronologically
    - performs no persistence
    - creates no Candidate #2+
    - defines no new confirmation window
    """

    def __init__(
        self,
        *,
        price_action_service: PriceActionService,
    ) -> None:
        self.price_action_service = (
            price_action_service
        )

    def find_first_pass(
        self,
        *,
        direction: Direction,
        inputs: Sequence[PriceActionInput],
        atr_15m: float | None,
    ) -> ReArmPriceActionTriggerResult:

        ordered = sorted(
            inputs,
            key=lambda item: (
                item.trigger_bar.end_at
            ),
        )

        checked = 0

        for item in ordered:
            trigger = item.trigger_bar

            result = (
                self.price_action_service
                .evaluate_bar(
                    direction=direction,

                    # ReArm has no new 30-minute
                    # confirmation window.
                    #
                    # These bounds only allow the
                    # existing PriceActionService to
                    # evaluate this exact completed
                    # 15m trigger bar.
                    candidate_at=(
                        trigger.start_at
                    ),
                    confirmation_deadline_at=(
                        trigger.end_at
                    ),

                    trigger_bar=trigger,
                    prior_bars=(
                        item.prior_bars
                    ),
                    atr_15m=atr_15m,
                    historical_same_slot_volumes=(
                        item
                        .historical_same_slot_volumes
                    ),
                )
            )

            checked += 1

            if (
                result.price_action_status
                == GateStatus.PASS
            ):
                return (
                    ReArmPriceActionTriggerResult(
                        found=True,
                        reason=(
                            "FRESH_PRICE_ACTION_PASS"
                        ),
                        trigger_bar_close=(
                            result.price_action_bar_at
                        ),
                        price_action_result=result,
                        evaluations_checked=checked,
                    )
                )

        return ReArmPriceActionTriggerResult(
            found=False,
            reason="NO_FRESH_PRICE_ACTION_PASS",
            trigger_bar_close=None,
            price_action_result=None,
            evaluations_checked=checked,
        )
