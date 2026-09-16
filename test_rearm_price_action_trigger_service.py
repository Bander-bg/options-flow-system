from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from weekly.domain.enums import Direction, GateStatus
from weekly.services.price_action_input_service import (
    PriceActionInput,
)
from weekly.services.price_action_service import PriceBar
from weekly.services.rearm_price_action_trigger_service import (
    ReArmPriceActionTriggerService,
)


ET = ZoneInfo("America/New_York")


def make_input(hour: int, minute: int) -> PriceActionInput:
    start = datetime(
        2026,
        9,
        11,
        hour,
        minute,
        tzinfo=ET,
    )

    return PriceActionInput(
        trigger_bar=PriceBar(
            start_at=start,
            end_at=start + timedelta(minutes=15),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=100.0,
        ),
        prior_bars=(),
        historical_same_slot_volumes=(),
    )


class FakePriceActionService:
    def __init__(self, statuses):
        self.statuses = statuses
        self.calls = []

    def evaluate_bar(
        self,
        *,
        direction,
        candidate_at,
        confirmation_deadline_at,
        trigger_bar,
        prior_bars,
        atr_15m,
        historical_same_slot_volumes,
    ):
        self.calls.append(
            trigger_bar.end_at
        )

        status = self.statuses[
            trigger_bar.end_at
        ]

        return SimpleNamespace(
            price_action_status=status,
            price_action_bar_at=(
                trigger_bar.end_at
            ),
        )


def main():
    first = make_input(10, 0)
    second = make_input(10, 15)
    third = make_input(10, 30)

    statuses = {
        first.trigger_bar.end_at:
            GateStatus.FAIL,
        second.trigger_bar.end_at:
            GateStatus.PASS,
        third.trigger_bar.end_at:
            GateStatus.PASS,
    }

    fake = FakePriceActionService(
        statuses
    )

    service = (
        ReArmPriceActionTriggerService(
            price_action_service=fake,
        )
    )

    # Deliberately unordered input.
    result = service.find_first_pass(
        direction=Direction.BULLISH,
        inputs=[
            third,
            first,
            second,
        ],
        atr_15m=1.0,
    )

    assert result.found is True
    assert (
        result.reason
        == "FRESH_PRICE_ACTION_PASS"
    )

    assert (
        result.trigger_bar_close
        == second.trigger_bar.end_at
    )

    assert result.evaluations_checked == 2

    assert fake.calls == [
        first.trigger_bar.end_at,
        second.trigger_bar.end_at,
    ]

    print(
        "1. chronological evaluation: PASS"
    )
    print(
        "2. earlier FAIL skipped: PASS"
    )
    print(
        "3. earliest PASS selected: PASS"
    )
    print(
        "4. evaluation stops after first PASS: PASS"
    )

    no_pass_fake = FakePriceActionService(
        {
            first.trigger_bar.end_at:
                GateStatus.FAIL,
            second.trigger_bar.end_at:
                GateStatus.UNKNOWN,
        }
    )

    no_pass_service = (
        ReArmPriceActionTriggerService(
            price_action_service=no_pass_fake,
        )
    )

    no_pass = no_pass_service.find_first_pass(
        direction=Direction.BEARISH,
        inputs=[
            second,
            first,
        ],
        atr_15m=None,
    )

    assert no_pass.found is False
    assert (
        no_pass.reason
        == "NO_FRESH_PRICE_ACTION_PASS"
    )

    assert no_pass.trigger_bar_close is None
    assert no_pass.price_action_result is None
    assert no_pass.evaluations_checked == 2

    print(
        "5. no PASS handled cleanly: PASS"
    )

    print()
    print("=" * 70)
    print(
        "REARM PRICE ACTION TRIGGER SERVICE: PASS 5/5"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
