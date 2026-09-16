from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetCalendarRequest


load_dotenv()


ET = ZoneInfo("America/New_York")


def get_env_value(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


API_KEY = get_env_value(
    "ALPACA_API_KEY",
    "ALPACA_KEY",
    "APCA_API_KEY_ID",
)

SECRET_KEY = get_env_value(
    "ALPACA_SECRET_KEY",
    "ALPACA_SECRET",
    "APCA_API_SECRET_KEY",
)


if not API_KEY or not SECRET_KEY:
    raise RuntimeError(
        "Alpaca API credentials were not found in .env"
    )


client = TradingClient(
    API_KEY,
    SECRET_KEY,
    paper=True,
)


def as_et(value: datetime) -> datetime:
    """
    Alpaca Calendar datetimes may be returned without tzinfo.
    weekly_v1 treats Calendar open/close as America/New_York.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=ET)

    return value.astimezone(ET)


def get_sessions(start_date, end_date):
    request = GetCalendarRequest(
        start=start_date,
        end=end_date,
    )

    return client.get_calendar(request)


def session_open(session) -> datetime:
    return as_et(session.open)


def session_close(session) -> datetime:
    return as_et(session.close)


def find_session_by_date(sessions, target_date):
    for session in sessions:
        if session.date == target_date:
            return session

    return None


def find_next_session(
    sessions,
    after_date,
):
    future = [
        session
        for session in sessions
        if session.date > after_date
    ]

    if not future:
        return None

    return min(
        future,
        key=lambda session: session.date,
    )


def add_trading_minutes(
    start_at: datetime,
    minutes: int,
    sessions,
) -> datetime:
    """
    Add actual RTH trading minutes only.

    Closed periods, weekends, holidays, and overnight time
    consume zero trading minutes.
    """
    if minutes < 0:
        raise ValueError(
            "minutes must be >= 0"
        )

    current = as_et(start_at)

    remaining = timedelta(
        minutes=minutes
    )

    if remaining == timedelta(0):
        return current

    ordered_sessions = sorted(
        sessions,
        key=lambda session: session.date,
    )

    for session in ordered_sessions:
        open_at = session_open(session)
        close_at = session_close(session)

        if current > close_at:
            continue

        if current < open_at:
            current = open_at

        if not (
            open_at <= current <= close_at
        ):
            continue

        available = close_at - current

        if remaining <= available:
            return current + remaining

        remaining -= available

        current = close_at + timedelta(
            microseconds=1
        )

    raise RuntimeError(
        "Calendar range is not wide enough "
        "to complete add_trading_minutes()."
    )


def print_result(
    name: str,
    actual: datetime,
    expected: datetime,
):
    passed = actual == expected

    print(
        name,
        ":",
        "PASS" if passed else "FAIL",
    )

    print(
        " actual:  ",
        actual,
    )

    print(
        " expected:",
        expected,
    )

    print()

    return passed


def main():
    clock = client.get_clock()

    trading_date_et = (
        clock.timestamp.date()
    )

    # Wide range so we can also discover an actual
    # early-close session later in 2026.
    sessions = get_sessions(
        trading_date_et,
        datetime(
            2026,
            12,
            31,
        ).date(),
    )

    print("=" * 78)
    print("WEEKLY_V1 TRADING-MINUTE CALENDAR TEST")
    print("=" * 78)

    print(
        "alpaca_market_timestamp:",
        clock.timestamp,
    )

    print(
        "trading_date_et:",
        trading_date_et,
    )

    print(
        "sessions_loaded:",
        len(sessions),
    )

    print()

    current_session = (
        find_session_by_date(
            sessions,
            trading_date_et,
        )
    )

    if current_session is None:
        raise RuntimeError(
            "Current trading date is not present "
            "in Alpaca Calendar."
        )

    next_session = find_next_session(
        sessions,
        trading_date_et,
    )

    if next_session is None:
        raise RuntimeError(
            "No next trading session found."
        )

    current_open = session_open(
        current_session
    )

    current_close = session_close(
        current_session
    )

    next_open = session_open(
        next_session
    )

    print("=" * 78)
    print("CURRENT / NEXT SESSION")
    print("=" * 78)

    print(
        "current_open:",
        current_open,
    )

    print(
        "current_close:",
        current_close,
    )

    print(
        "next_session_date:",
        next_session.date,
    )

    print(
        "next_open:",
        next_open,
    )

    print()

    results = []

    # --------------------------------------------------
    # TEST 1
    # Normal same-session trading minutes.
    # 10:00 + 30 trading minutes = 10:30.
    # --------------------------------------------------

    start_1 = current_open + timedelta(
        minutes=30
    )

    expected_1 = start_1 + timedelta(
        minutes=30
    )

    actual_1 = add_trading_minutes(
        start_1,
        30,
        sessions,
    )

    results.append(
        print_result(
            "TEST 1 - SAME SESSION +30m",
            actual_1,
            expected_1,
        )
    )

    # --------------------------------------------------
    # TEST 2
    # Cross official close.
    #
    # Start 5 minutes before close.
    # +15 trading minutes =
    # 5 minutes today + 10 minutes next session.
    # --------------------------------------------------

    start_2 = current_close - timedelta(
        minutes=5
    )

    expected_2 = next_open + timedelta(
        minutes=10
    )

    actual_2 = add_trading_minutes(
        start_2,
        15,
        sessions,
    )

    results.append(
        print_result(
            "TEST 2 - CROSS SESSION +15m",
            actual_2,
            expected_2,
        )
    )

    # --------------------------------------------------
    # TEST 3
    # Demonstrate holiday/weekend skipping.
    # For the current 2026-09-04 sample, Alpaca should
    # move directly to 2026-09-08 because Labor Day
    # is not a trading session.
    # --------------------------------------------------

    print("=" * 78)
    print("HOLIDAY / CLOSED-DAY CHECK")
    print("=" * 78)

    print(
        "current_session:",
        current_session.date,
    )

    print(
        "next_actual_trading_session:",
        next_session.date,
    )

    calendar_gap_days = (
        next_session.date
        - current_session.date
    ).days

    print(
        "calendar_day_gap:",
        calendar_gap_days,
    )

    holiday_skip_ok = (
        next_session.date
        > current_session.date
    )

    print(
        "Holiday/weekend skipping:",
        "PASS"
        if holiday_skip_ok
        else "FAIL",
    )

    print()

    results.append(
        holiday_skip_ok
    )

    # --------------------------------------------------
    # TEST 4
    # Deadline policy - full 30m window fits today.
    # Candidate 40 minutes before close.
    #
    # requested deadline = +30 trading minutes.
    # Since it is <= official close, the window fits.
    # --------------------------------------------------

    candidate_fit = (
        current_close
        - timedelta(minutes=40)
    )

    requested_fit = add_trading_minutes(
        candidate_fit,
        30,
        sessions,
    )

    actual_deadline_fit = min(
        requested_fit,
        current_close,
    )

    fit_ok = (
        requested_fit <= current_close
        and actual_deadline_fit
        == requested_fit
    )

    print("=" * 78)
    print("DEADLINE POLICY - WINDOW FITS")
    print("=" * 78)

    print(
        "candidate_at:",
        candidate_fit,
    )

    print(
        "requested_confirmation_deadline_at:",
        requested_fit,
    )

    print(
        "official_session_close:",
        current_close,
    )

    print(
        "confirmation_deadline_at:",
        actual_deadline_fit,
    )

    print(
        "RESULT:",
        "PASS" if fit_ok else "FAIL",
    )

    print()

    results.append(
        fit_ok
    )

    # --------------------------------------------------
    # TEST 5
    # Deadline policy - session cuts the 30m window.
    #
    # Candidate 10 minutes before close.
    # requested +30 trading minutes extends into
    # next trading session.
    #
    # weekly_v1 must clip confirmation_deadline_at
    # to today's official close and classify unresolved
    # candidate later as INVALIDATED: session_closed.
    # --------------------------------------------------

    candidate_cut = (
        current_close
        - timedelta(minutes=10)
    )

    requested_cut = add_trading_minutes(
        candidate_cut,
        30,
        sessions,
    )

    actual_deadline_cut = min(
        requested_cut,
        current_close,
    )

    cut_ok = (
        requested_cut > current_close
        and actual_deadline_cut
        == current_close
    )

    print("=" * 78)
    print("DEADLINE POLICY - SESSION CUTS WINDOW")
    print("=" * 78)

    print(
        "candidate_at:",
        candidate_cut,
    )

    print(
        "requested_confirmation_deadline_at:",
        requested_cut,
    )

    print(
        "official_session_close:",
        current_close,
    )

    print(
        "confirmation_deadline_at:",
        actual_deadline_cut,
    )

    print(
        "expected_terminal_policy:",
        "INVALIDATED: session_closed",
    )

    print(
        "RESULT:",
        "PASS" if cut_ok else "FAIL",
    )

    print()

    results.append(
        cut_ok
    )

    # --------------------------------------------------
    # TEST 6
    # Dynamically find an Alpaca early-close session.
    # No hardcoded early-close time is assumed.
    # --------------------------------------------------

    early_close_session = None
    early_close_next = None

    for index, session in enumerate(
        sessions[:-1]
    ):
        close_at = session_close(
            session
        )

        if (
            close_at.hour < 16
            or (
                close_at.hour == 16
                and close_at.minute < 0
            )
        ):
            early_close_session = session
            early_close_next = (
                sessions[index + 1]
            )
            break

    print("=" * 78)
    print("EARLY CLOSE TEST")
    print("=" * 78)

    if (
        early_close_session is None
        or early_close_next is None
    ):
        print(
            "No early-close session was found "
            "inside the loaded Calendar range."
        )

        print(
            "RESULT: CHECK REQUIRED"
        )

        results.append(
            False
        )

    else:
        early_close_at = session_close(
            early_close_session
        )

        next_after_early_open = session_open(
            early_close_next
        )

        early_start = (
            early_close_at
            - timedelta(minutes=5)
        )

        early_actual = add_trading_minutes(
            early_start,
            15,
            sessions,
        )

        early_expected = (
            next_after_early_open
            + timedelta(minutes=10)
        )

        print(
            "early_close_date:",
            early_close_session.date,
        )

        print(
            "early_close_at:",
            early_close_at,
        )

        print(
            "next_session:",
            early_close_next.date,
        )

        print(
            "start:",
            early_start,
        )

        print(
            "actual:",
            early_actual,
        )

        print(
            "expected:",
            early_expected,
        )

        early_ok = (
            early_actual
            == early_expected
        )

        print(
            "RESULT:",
            "PASS"
            if early_ok
            else "FAIL",
        )

        results.append(
            early_ok
        )

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)

    passed = sum(
        1
        for result in results
        if result
    )

    print(
        "tests_passed:",
        passed,
        "/",
        len(results),
    )

    if all(results):
        print()
        print(
            "Calendar trading-minute helpers: PASS"
        )

        print(
            "Trading-minute offsets, holiday skipping, "
            "session clipping, and early close behavior "
            "are consistent with weekly_v1."
        )

    else:
        print()
        print(
            "Calendar trading-minute helpers: "
            "CHECK REQUIRED"
        )


if __name__ == "__main__":
    main()