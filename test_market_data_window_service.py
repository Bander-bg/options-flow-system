from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from weekly.services.market_data_window_service import (
    MarketDataWindowService,
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


def main():
    start_day = date(2026, 8, 3)

    sessions = []

    day = start_day

    while len(sessions) < 25:
        if day.weekday() < 5:
            sessions.append(
                make_session(day)
            )
        day += timedelta(days=1)

    current = sessions[-1]

    as_of = datetime(
        current.date.year,
        current.date.month,
        current.date.day,
        12,
        45,
        tzinfo=ET,
    )

    service = MarketDataWindowService()

    result = service.build(
        trading_date_et=current.date,
        as_of=as_of,
        calendar=sessions,
        previous_sessions=20,
    )

    assert len(result.sessions) == 21
    assert result.previous_session_count == 20
    assert result.sessions[-1].date == current.date
    assert result.sessions[0].date == sessions[-21].date
    assert result.start_at == sessions[-21].open
    assert result.end_at == as_of

    print("1. previous 20 sessions selected: PASS")
    print("2. current session included: PASS")
    print("3. oldest start boundary correct: PASS")
    print("4. as_of end boundary correct: PASS")
    print("5. session ordering preserved: PASS")

    print()
    print("=" * 70)
    print("MARKET DATA WINDOW SERVICE: PASS 5/5")
    print("=" * 70)


if __name__ == "__main__":
    main()
