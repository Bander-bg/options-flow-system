from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from weekly.domain.enums import Direction
from weekly.services.rearm_service import ReArmService

from test_trade_repository import make_signal


ET = ZoneInfo("America/New_York")


def dt(
    hour: int,
    minute: int = 0,
    *,
    day: int = 4,
) -> datetime:
    return datetime(
        2026,
        9,
        day,
        hour,
        minute,
        tzinfo=ET,
    )


def main() -> None:
    service = ReArmService()

    bullish = replace(
        make_signal(),
        confirmed_at=dt(10, 0),
        net_flow_at_confirmation=600_000,
    )

    success = service.evaluate(
        previous_signal=bullish,
        current_trading_date_et=date(2026, 9, 4),
        as_of=dt(11, 5),
        current_net_flow=1_100_000,
        rearm_aligned_flow_min=500_000,
        cooldown_minutes=60,
        new_trigger_bar_close=dt(11, 15),
    )

    assert success.allowed is True
    assert success.reason == "REARM_ALLOWED"
    assert success.aligned_flow == 500_000
    assert success.cooldown_until == dt(11, 0)

    bearish = replace(
        make_signal(),
        ticker="TSLA",
        direction=Direction.BEARISH,
        confirmed_at=dt(10, 0),
        net_flow_at_confirmation=-600_000,
    )

    bearish_success = service.evaluate(
        previous_signal=bearish,
        current_trading_date_et=date(2026, 9, 4),
        as_of=dt(11, 5),
        current_net_flow=-1_100_000,
        rearm_aligned_flow_min=500_000,
        cooldown_minutes=60,
        new_trigger_bar_close=dt(11, 15),
    )

    assert bearish_success.allowed is True
    assert bearish_success.aligned_flow == 500_000

    cross_session = service.evaluate(
        previous_signal=bullish,
        current_trading_date_et=date(2026, 9, 8),
        as_of=dt(11, 5, day=8),
        current_net_flow=2_000_000,
        rearm_aligned_flow_min=500_000,
        cooldown_minutes=60,
        new_trigger_bar_close=dt(11, 15, day=8),
    )
    assert cross_session.allowed is False
    assert (
        cross_session.reason
        == "DIFFERENT_TRADING_DATE_ET"
    )

    cooldown = service.evaluate(
        previous_signal=bullish,
        current_trading_date_et=date(2026, 9, 4),
        as_of=dt(10, 45),
        current_net_flow=1_500_000,
        rearm_aligned_flow_min=500_000,
        cooldown_minutes=60,
        new_trigger_bar_close=dt(10, 45),
    )
    assert cooldown.allowed is False
    assert cooldown.reason == "COOLDOWN_ACTIVE"

    insufficient = service.evaluate(
        previous_signal=bullish,
        current_trading_date_et=date(2026, 9, 4),
        as_of=dt(11, 5),
        current_net_flow=900_000,
        rearm_aligned_flow_min=500_000,
        cooldown_minutes=60,
        new_trigger_bar_close=dt(11, 15),
    )
    assert insufficient.allowed is False
    assert (
        insufficient.reason
        == "INSUFFICIENT_ALIGNED_FLOW"
    )
    assert insufficient.aligned_flow == 300_000

    stale = service.evaluate(
        previous_signal=bullish,
        current_trading_date_et=date(2026, 9, 4),
        as_of=dt(11, 5),
        current_net_flow=1_200_000,
        rearm_aligned_flow_min=500_000,
        cooldown_minutes=60,
        new_trigger_bar_close=dt(10, 0),
    )
    assert stale.allowed is False
    assert stale.reason == "STALE_PRICE_TRIGGER"

    no_trigger = service.evaluate(
        previous_signal=bullish,
        current_trading_date_et=date(2026, 9, 4),
        as_of=dt(11, 5),
        current_net_flow=1_200_000,
        rearm_aligned_flow_min=500_000,
        cooldown_minutes=60,
        new_trigger_bar_close=None,
    )
    assert no_trigger.allowed is False
    assert no_trigger.reason == "NO_NEW_PRICE_TRIGGER"

    reversal = service.evaluate(
        previous_signal=bullish,
        current_trading_date_et=date(2026, 9, 4),
        as_of=dt(11, 5),
        current_net_flow=100_000,
        rearm_aligned_flow_min=500_000,
        cooldown_minutes=60,
        new_trigger_bar_close=dt(11, 15),
    )
    assert reversal.allowed is False
    assert (
        reversal.reason
        == "INSUFFICIENT_ALIGNED_FLOW"
    )
    assert reversal.aligned_flow == -500_000

    print("REARM SERVICE: PASS 8/8")


if __name__ == "__main__":
    main()
