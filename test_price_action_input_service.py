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

    bars = []

    # Same 12:00 ET slot on previous sessions.
    bars.append(
        bar(
            datetime(
                2026, 9, 9, 12, 0,
                tzinfo=ET,
            ),
            volume=100.0,
        )
    )

    bars.append(
        bar(
            datetime(
                2026, 9, 10, 12, 0,
                tzinfo=ET,
            ),
            volume=120.0,
        )
    )

    # Current-session prior bars:
    # 09:30 through 11:45 = 10 bars.
    current_start = datetime(
        2026,
        9,
        11,
        9,
        30,
        tzinfo=ET,
    )

    for i in range(10):
        bars.append(
            bar(
                current_start
                + timedelta(minutes=15 * i),
                volume=80.0 + i,
            )
        )

    trigger = bar(
        datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=ET,
        ),
        volume=200.0,
    )

    bars.append(trigger)

    service = PriceActionInputService(
        participation_lookback_sessions=2,
    )

    candidate_at = datetime(
        2026,
        9,
        11,
        12,
        0,
        tzinfo=ET,
    )

    deadline = datetime(
        2026,
        9,
        11,
        12,
        30,
        tzinfo=ET,
    )

    result = service.prepare_inputs(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        calendar=calendar,
        fifteen_minute_bars=bars,
        existing_features=[],
    )

    assert len(result) == 1

    prepared = result[0]

    assert (
        prepared.trigger_bar.start_at
        == trigger.start_at
    )

    assert (
        prepared.trigger_bar.end_at
        == trigger.end_at
    )

    assert len(
        prepared.prior_bars
    ) == 10

    assert all(
        item.start_at.date()
        == day3
        for item in prepared.prior_bars
    )

    assert (
        prepared.prior_bars[0].start_at
        == datetime(
            2026,
            9,
            11,
            9,
            30,
            tzinfo=ET,
        )
    )

    assert (
        prepared.prior_bars[-1].start_at
        == datetime(
            2026,
            9,
            11,
            11,
            45,
            tzinfo=ET,
        )
    )

    assert (
        prepared.historical_same_slot_volumes
        == (
            100.0,
            120.0,
        )
    )

    # Existing evaluation must suppress same trigger.
    dedup_result = service.prepare_inputs(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        calendar=calendar,
        fifteen_minute_bars=bars,
        existing_features=[
            SimpleNamespace(
                price_action_bar_at=(
                    trigger.end_at
                )
            )
        ],
    )

    assert dedup_result == ()

    print(
        "1. trigger window selection: PASS"
    )
    print(
        "2. same-session prior bars: PASS"
    )
    print(
        "3. prior bars chronological order: PASS"
    )
    print(
        "4. historical same-slot matching: PASS"
    )
    print(
        "5. participation lookback applied: PASS"
    )
    print(
        "6. previously evaluated trigger skipped: PASS"
    )

    print()
    print("=" * 70)
    print(
        "PRICE ACTION INPUT SERVICE: PASS 6/6"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
