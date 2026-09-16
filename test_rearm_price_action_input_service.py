from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from weekly.services.atr_service import ATR15MinuteBar
from weekly.services.price_action_input_service import (
    PriceActionInputService,
)


ET = ZoneInfo("America/New_York")


def session(day: date):
    return SimpleNamespace(
        date=day,
        open=datetime(
            day.year,
            day.month,
            day.day,
            9,
            30,
            tzinfo=ET,
        ),
        close=datetime(
            day.year,
            day.month,
            day.day,
            16,
            0,
            tzinfo=ET,
        ),
    )


def bar(
    start_at: datetime,
    *,
    volume: float,
):
    return ATR15MinuteBar(
        start_at=start_at,
        end_at=start_at + timedelta(minutes=15),
        open=100.0,
        high=101.0,
        low=99.5,
        close=100.5,
        volume=volume,
        source_minute_bar_count=15,
    )


def main():
    day1 = date(2026, 9, 9)
    day2 = date(2026, 9, 10)
    day3 = date(2026, 9, 11)

    calendar = [
        session(day1),
        session(day2),
        session(day3),
    ]

    bars = [
        # Historical same 10:00 slot.
        bar(
            datetime(
                2026, 9, 9, 10, 0,
                tzinfo=ET,
            ),
            volume=100.0,
        ),
        bar(
            datetime(
                2026, 9, 10, 10, 0,
                tzinfo=ET,
            ),
            volume=120.0,
        ),

        # Current session prior bars.
        bar(
            datetime(
                2026, 9, 11, 9, 30,
                tzinfo=ET,
            ),
            volume=80.0,
        ),
        bar(
            datetime(
                2026, 9, 11, 9, 45,
                tzinfo=ET,
            ),
            volume=90.0,
        ),

        # This bar starts BEFORE confirmed_at=10:05,
        # but closes AFTER it at 10:15.
        # Frozen ReArm rule says it is fresh.
        bar(
            datetime(
                2026, 9, 11, 10, 0,
                tzinfo=ET,
            ),
            volume=200.0,
        ),

        # Not completed by as_of=10:15.
        bar(
            datetime(
                2026, 9, 11, 10, 15,
                tzinfo=ET,
            ),
            volume=220.0,
        ),
    ]

    service = PriceActionInputService(
        participation_lookback_sessions=2,
    )

    confirmed_at = datetime(
        2026,
        9,
        11,
        10,
        5,
        tzinfo=ET,
    )

    as_of = datetime(
        2026,
        9,
        11,
        10,
        15,
        tzinfo=ET,
    )

    result = service.prepare_rearm_inputs(
        confirmed_at=confirmed_at,
        as_of=as_of,
        calendar=calendar,
        fifteen_minute_bars=bars,
    )

    assert len(result) == 1

    prepared = result[0]

    assert (
        prepared.trigger_bar.start_at
        == datetime(
            2026,
            9,
            11,
            10,
            0,
            tzinfo=ET,
        )
    )

    assert (
        prepared.trigger_bar.end_at
        == datetime(
            2026,
            9,
            11,
            10,
            15,
            tzinfo=ET,
        )
    )

    assert (
        prepared.trigger_bar.start_at
        < confirmed_at
    )

    assert (
        prepared.trigger_bar.end_at
        > confirmed_at
    )

    assert len(
        prepared.prior_bars
    ) == 2

    assert (
        prepared.historical_same_slot_volumes
        == (
            100.0,
            120.0,
        )
    )

    print(
        "1. close-after-confirmed_at rule: PASS"
    )
    print(
        "2. start-before-confirmed_at allowed: PASS"
    )
    print(
        "3. incomplete future bar excluded: PASS"
    )
    print(
        "4. same-session prior bars reused: PASS"
    )
    print(
        "5. historical same-slot volumes reused: PASS"
    )

    print()
    print("=" * 70)
    print(
        "REARM PRICE ACTION INPUT: PASS 5/5"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
