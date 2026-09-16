from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from weekly.domain.enums import GateStatus
from weekly.providers.alpaca_stock_provider import StockMinuteBar
from weekly.services.efficiency_ratio_service import (
    EfficiencyRatioService,
    EfficiencyRatioSettings,
)


ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class FakeSession:
    date: date
    open: datetime
    close: datetime


def make_session(
    day: date,
    *,
    close_hour: int = 16,
    close_minute: int = 0,
) -> FakeSession:
    return FakeSession(
        date=day,
        open=datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET),
        close=datetime(
            day.year,
            day.month,
            day.day,
            close_hour,
            close_minute,
            tzinfo=ET,
        ),
     )


def make_minute_bar(
    when: datetime,
    close: float,
) -> StockMinuteBar:
    return StockMinuteBar(
        start_at=when,
        end_at=when + timedelta(minutes=1),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100,
        vwap=close,
    )


def add_hour_window(
    bars: list[StockMinuteBar],
    start: datetime,
    *,
    open_close: float,
    end_close: float,
) -> None:
    bars.append(
        make_minute_bar(
            start,
            open_close,
         )
    )
    bars.append(
        make_minute_bar(
            start + timedelta(minutes=59),
            end_close,
        )
    )


def main() -> None:
    settings = EfficiencyRatioSettings(
        minimum_er=0.30,
        min_er_bars=4,
    )
    service = EfficiencyRatioService(
        settings=settings,
    )

    tue = date(2026, 9, 8)
    calendar = [
        make_session(tue),
    ]

    session_open = datetime(
        2026, 9, 8, 9, 30, tzinfo=ET
    )

    pass_bars: list[StockMinuteBar] = []
    for index, close in enumerate(
        [100, 102, 104, 106]
    ):
        start = (
            session_open
            + timedelta(hours=index)
        )
        add_hour_window(
            pass_bars,
            start,
            open_close=close - 0.5,
            end_close=close,
        )

    add_hour_window(
        pass_bars,
        session_open + timedelta(hours=4),
        open_close=200,
        end_close=200,
    )

    pass_result = service.evaluate(
        as_of=datetime(
            2026, 9, 8, 13, 45, tzinfo=ET
        ),
        trading_date_et=tue,
        calendar=calendar,
        minute_bars=pass_bars,
    )

    assert pass_result.status is GateStatus.PASS
    assert abs(
        pass_result.efficiency_ratio - 1.0
    ) < 1e-12
    assert len(
        pass_result.hourly_bars
    ) == 4
    assert pass_result.anchor_at == session_open

    expected_starts = [
        session_open + timedelta(hours=i)
        for i in range(4)
    ]
    actual_starts = [
        bar.start_at
        for bar in pass_result.hourly_bars
    ]
    assert actual_starts == expected_starts

    fail_bars: list[StockMinuteBar] = []
    for index, close in enumerate(
        [100, 102, 99, 100]
    ):
        start = (
            session_open
            + timedelta(hours=index)
        )
        add_hour_window(
            fail_bars,
            start,
            open_close=close,
            end_close=close,
        )

    fail_result = service.evaluate(
        as_of=datetime(
            2026, 9, 8, 13, 30, tzinfo=ET
        ),
        trading_date_et=tue,
        calendar=calendar,
        minute_bars=fail_bars,
    )

    assert fail_result.status is GateStatus.FAIL
    assert fail_result.efficiency_ratio == 0.0

    flat_bars: list[StockMinuteBar] = []
    for index in range(4):
        start = (
            session_open
            + timedelta(hours=index)
        )
        add_hour_window(
            flat_bars,
            start,
            open_close=100,
            end_close=100,
        )

    flat_result = service.evaluate(
        as_of=datetime(
            2026, 9, 8, 13, 30, tzinfo=ET
        ),
        trading_date_et=tue,
        calendar=calendar,
        minute_bars=flat_bars,
    )

    assert flat_result.status is GateStatus.FAIL
    assert flat_result.efficiency_ratio == 0.0

    insufficient = service.evaluate(
        as_of=datetime(
            2026, 9, 8, 12, 45, tzinfo=ET
        ),
        trading_date_et=tue,
        calendar=calendar,
        minute_bars=pass_bars,
    )

    assert insufficient.status is GateStatus.UNKNOWN
    assert (
        insufficient.reason
        == "INSUFFICIENT_COMPLETED_1H_BARS"
    )
    assert len(
        insufficient.hourly_bars
    ) == 3

    early_calendar = [
        make_session(
            tue,
            close_hour=13,
            close_minute=0,
        )
    ]

    early_bars: list[StockMinuteBar] = []
    for index, close in enumerate(
        [100, 101, 102]
    ):
        start = (
            session_open
            + timedelta(hours=index)
        )
        add_hour_window(
            early_bars,
            start,
            open_close=close,
            end_close=close,
        )

    early_bars.append(
        make_minute_bar(
            datetime(
                2026, 9, 8, 12, 45, tzinfo=ET
            ),
            150,
        )
    )

    early_result = service.evaluate(
        as_of=datetime(
            2026, 9, 8, 13, 0, tzinfo=ET
        ),
        trading_date_et=tue,
        calendar=early_calendar,
        minute_bars=early_bars,
    )

    assert early_result.status is GateStatus.UNKNOWN
    assert len(
        early_result.hourly_bars
    ) == 3

    print("1. first actual weekly-session anchor: PASS")
    print("2. manual 1H bars anchored at 09:30 ET: PASS")
    print("3. incomplete current 1H bar excluded: PASS")
    print("4. ER >= 0.30 gate: PASS")
    print("5. ER below threshold / zero denominator: PASS")
    print("6. fewer than 4 completed 1H bars -> UNKNOWN: PASS")
    print("7. early-close partial hour excluded: PASS")
    print()
    print("=" * 70)
    print("EFFICIENCY RATIO SERVICE: PASS 7/7")
    print("=" * 70)


if __name__ == "__main__":
    main()
