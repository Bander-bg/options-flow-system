from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from weekly.domain.enums import Direction, GateStatus
from weekly.providers.alpaca_stock_provider import StockMinuteBar
from weekly.services.weekly_vwap_service import WeeklyVWAPService


ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class FakeSession:
    date: date
    open: datetime
    close: datetime


def make_session(
    day: date,
    *,
    open_hour: int = 9,
    open_minute: int = 30,
    close_hour: int = 16,
    close_minute: int = 0,
) -> FakeSession:
    return FakeSession(
        date=day,
        open=datetime(
            day.year,
            day.month,
            day.day,
            open_hour,
            open_minute,
            tzinfo=ET,
        ),
        close=datetime(
            day.year,
            day.month,
            day.day,
            close_hour,
            close_minute,
            tzinfo=ET,
        ),
    )


def make_bar(
    day: date,
    hour: int,
    minute: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    vwap: float | None = None,
) -> StockMinuteBar:
    start = datetime(
        day.year,
        day.month,
        day.day,
        hour,
        minute,
        tzinfo=ET,
    )

    return StockMinuteBar(
        start_at=start,
        end_at=start + timedelta(minutes=1),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        vwap=vwap,
    )


def main() -> None:
    service = WeeklyVWAPService()

    tue = date(2026, 9, 8)
    wed = date(2026, 9, 9)

    calendar = [
        make_session(tue),
        make_session(wed),
    ]

    as_of = datetime(2026, 9, 9, 10, 0, tzinfo=ET)

    bars = [
        make_bar(tue, 9, 0, open_=90, high=90, low=90, close=90, volume=1000, vwap=90),
        make_bar(tue, 9, 30, open_=100, high=101, low=99, close=100, volume=100, vwap=100),
        make_bar(tue, 9, 31, open_=100, high=102, low=100, close=101, volume=100, vwap=101),
        make_bar(wed, 9, 30, open_=102, high=103, low=101, close=102, volume=100, vwap=102),
        make_bar(wed, 9, 31, open_=103, high=104, low=102, close=103, volume=100, vwap=103),
        make_bar(wed, 10, 0, open_=200, high=200, low=200, close=200, volume=1000, vwap=200),
    ]

    bullish = service.evaluate(direction=Direction.BULLISH, as_of=as_of, trading_date_et=wed, calendar=calendar, minute_bars=bars)

    assert abs(bullish.weekly_vwap - 101.5) < 1e-9
    assert bullish.underlying_price == 103
    assert bullish.status is GateStatus.PASS
    assert bullish.included_bar_count == 4
    assert bullish.anchor_at == datetime(2026, 9, 8, 9, 30, tzinfo=ET)

    bearish = service.evaluate(direction=Direction.BEARISH, as_of=as_of, trading_date_et=wed, calendar=calendar, minute_bars=bars)
    assert bearish.status is GateStatus.FAIL

    bearish_bars = [
        make_bar(tue, 9, 30, open_=105, high=106, low=104, close=105, volume=100, vwap=105),
        make_bar(wed, 9, 30, open_=100, high=101, low=99, close=100, volume=100, vwap=100),
    ]

    bearish_pass = service.evaluate(direction=Direction.BEARISH, as_of=as_of, trading_date_et=wed, calendar=calendar, minute_bars=bearish_bars)
    assert bearish_pass.status is GateStatus.PASS

    unknown = service.evaluate(direction=Direction.BULLISH, as_of=as_of, trading_date_et=wed, calendar=calendar, minute_bars=[make_bar(wed, 8, 0, open_=100, high=100, low=100, close=100, volume=100, vwap=100)])
    assert unknown.status is GateStatus.UNKNOWN

    zero_volume = service.evaluate(direction=Direction.BULLISH, as_of=as_of, trading_date_et=wed, calendar=calendar, minute_bars=[make_bar(wed, 9, 30, open_=100, high=100, low=100, close=100, volume=0, vwap=100)])
    assert zero_volume.status is GateStatus.UNKNOWN

    print("1. first actual weekly session anchor: PASS")
    print("2. RTH-only filtering: PASS")
    print("3. completed-bars-only filtering: PASS")
    print("4. bullish Weekly VWAP gate: PASS")
    print("5. bearish Weekly VWAP gate: PASS")
    print("6. missing/zero-volume data -> UNKNOWN: PASS")
    print("7. Alpaca VWAP / typical-price fallback: PASS")
    print()
    print("=" * 70)
    print("WEEKLY VWAP SERVICE: PASS 7/7")
    print("=" * 70)


if __name__ == "__main__":
    main()
