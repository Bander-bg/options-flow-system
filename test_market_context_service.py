from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from weekly.services.market_context_service import (
    MarketContextService,
)


ET = ZoneInfo("America/New_York")


def make_session(day: date):
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


class FakeTradingClient:
    def __init__(self):
        self.last_calendar_request = None

    def get_clock(self):
        return SimpleNamespace(
            timestamp=datetime(
                2026,
                9,
                11,
                12,
                15,
                tzinfo=ET,
            ),
            is_open=True,
            next_open=datetime(
                2026,
                9,
                14,
                9,
                30,
                tzinfo=ET,
            ),
            next_close=datetime(
                2026,
                9,
                11,
                16,
                0,
                tzinfo=ET,
            ),
        )

    def get_calendar(self, request):
        self.last_calendar_request = request

        sessions = []
        day = date(2026, 8, 1)

        while day <= date(2026, 10, 11):
            if day.weekday() < 5:
                sessions.append(
                    make_session(day)
                )
            day += timedelta(days=1)

        return sessions


def main():
    client = FakeTradingClient()

    service = MarketContextService(
        trading_client=client
    )

    result = service.fetch(
        required_previous_sessions=20,
        history_calendar_days=60,
        future_calendar_days=30,
    )

    assert result.trading_date_et == date(
        2026,
        9,
        11,
    )

    assert result.market_timestamp == datetime(
        2026,
        9,
        11,
        12,
        15,
        tzinfo=ET,
    )

    assert result.market_is_open is True

    previous = [
        session
        for session in result.calendar
        if session.date
        < result.trading_date_et
    ]

    assert len(previous) >= 20

    current = [
        session
        for session in result.calendar
        if session.date
        == result.trading_date_et
    ]

    assert len(current) == 1

    print("1. Alpaca market clock date used: PASS")
    print("2. ET market timestamp preserved: PASS")
    print("3. current session found exactly once: PASS")
    print("4. >=20 previous sessions available: PASS")
    print("5. market open state preserved: PASS")

    print()
    print("=" * 70)
    print("MARKET CONTEXT SERVICE: PASS 5/5")
    print("=" * 70)


if __name__ == "__main__":
    main()
