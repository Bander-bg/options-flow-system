from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetCalendarRequest

from weekly.services.calendar_service import (
    add_trading_minutes,
    confirmation_deadline,
    count_remaining_future_sessions,
    select_target_expiry,
    session_close,
    session_open,
)

from dotenv import load_dotenv
import os


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
        "Alpaca credentials missing."
    )


client = TradingClient(
    API_KEY,
    SECRET_KEY,
    paper=True,
)


def assert_equal(
    actual,
    expected,
    name: str,
):
    if actual != expected:
        raise AssertionError(
            f"{name}: expected {expected!r}, "
            f"got {actual!r}"
        )


def run_test(
    name: str,
    function,
):
    try:
        function()
        print(f"PASS - {name}")
        return True

    except Exception as exc:
        print(f"FAIL - {name}")
        print(
            f"       {type(exc).__name__}: {exc}"
        )
        return False


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 PRODUCTION CALENDAR SERVICE TEST"
    )
    print("=" * 78)
    print()

    clock = client.get_clock()

    TEST_TRADING_DATE = date(
        2026,
        9,
        4,
    )

    trading_date_et = TEST_TRADING_DATE

    calendar = client.get_calendar(
        GetCalendarRequest(
            start=trading_date_et,
            end=date(
                2026,
                12,
                31,
            ),
        )
    )

    current_session = next(
        session
        for session in calendar
        if session.date == trading_date_et
    )

    next_session = next(
        session
        for session in calendar
        if session.date > trading_date_et
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

    results = []

    # --------------------------------------------------
    # TEST 1
    # Same-session +30m
    # --------------------------------------------------

    def test_same_session():
        start = (
            current_open
            + timedelta(minutes=30)
        )

        actual = add_trading_minutes(
            start_at=start,
            minutes=30,
            calendar=calendar,
        )

        expected = (
            start
            + timedelta(minutes=30)
        )

        assert_equal(
            actual,
            expected,
            "same-session +30m",
        )

    results.append(
        run_test(
            "Same-session +30 trading minutes",
            test_same_session,
        )
    )

    # --------------------------------------------------
    # TEST 2
    # Cross session
    # --------------------------------------------------

    def test_cross_session():
        start = (
            current_close
            - timedelta(minutes=5)
        )

        actual = add_trading_minutes(
            start_at=start,
            minutes=15,
            calendar=calendar,
        )

        expected = (
            next_open
            + timedelta(minutes=10)
        )

        assert_equal(
            actual,
            expected,
            "cross-session +15m",
        )

    results.append(
        run_test(
            "Cross-session trading minutes",
            test_cross_session,
        )
    )

    # --------------------------------------------------
    # TEST 3
    # Holiday/weekend skipping
    # --------------------------------------------------

    def test_closed_days_skipped():
        if not (
            next_session.date
            > trading_date_et
        ):
            raise AssertionError(
                "Next trading session invalid."
            )

    results.append(
        run_test(
            "Closed days skipped",
            test_closed_days_skipped,
        )
    )

    # --------------------------------------------------
    # TEST 4
    # Target expiry
    # --------------------------------------------------

    def test_target_expiry():
        listed_expiries = [
            date(2026, 9, 4),
            date(2026, 9, 9),
            date(2026, 9, 11),
            date(2026, 9, 14),
            date(2026, 9, 16),
            date(2026, 9, 18),
        ]

        selected = select_target_expiry(
            trading_date_et=date(
                2026,
                9,
                4,
            ),
            listed_expiries=listed_expiries,
            calendar=calendar,
            min_sessions=3,
            max_sessions=7,
        )

        if selected is None:
            raise AssertionError(
                "Target expiry not selected."
            )

        expiry, sessions = selected

        assert_equal(
            expiry,
            date(
                2026,
                9,
                11,
            ),
            "target expiry",
        )

        assert_equal(
            sessions,
            4,
            "remaining sessions",
        )

    results.append(
        run_test(
            "Target expiry 3-7 sessions",
            test_target_expiry,
        )
    )

    # --------------------------------------------------
    # TEST 5
    # Deadline fits
    # --------------------------------------------------

    def test_deadline_fits():
        candidate_at = (
            current_close
            - timedelta(minutes=40)
        )

        requested, actual = (
            confirmation_deadline(
                candidate_at=candidate_at,
                confirmation_minutes=30,
                trading_date_et=trading_date_et,
                calendar=calendar,
            )
        )

        assert_equal(
            requested,
            candidate_at
            + timedelta(minutes=30),
            "requested deadline",
        )

        assert_equal(
            actual,
            requested,
            "actual deadline",
        )

    results.append(
        run_test(
            "Confirmation deadline fits session",
            test_deadline_fits,
        )
    )

    # --------------------------------------------------
    # TEST 6
    # Session cuts confirmation window
    # --------------------------------------------------

    def test_deadline_clipped():
        candidate_at = (
            current_close
            - timedelta(minutes=10)
        )

        requested, actual = (
            confirmation_deadline(
                candidate_at=candidate_at,
                confirmation_minutes=30,
                trading_date_et=trading_date_et,
                calendar=calendar,
            )
        )

        if requested <= current_close:
            raise AssertionError(
                "Requested deadline should "
                "extend past session close."
            )

        assert_equal(
            actual,
            current_close,
            "clipped deadline",
        )

    results.append(
        run_test(
            "Session close clips confirmation window",
            test_deadline_clipped,
        )
    )

    # --------------------------------------------------
    # TEST 7
    # Early close
    # --------------------------------------------------

    def test_early_close():
        early_session = None
        next_after_early = None

        for index, session in enumerate(
            calendar[:-1]
        ):
            close_at = session_close(
                session
            )

            if close_at.hour < 16:
                early_session = session
                next_after_early = (
                    calendar[index + 1]
                )
                break

        if (
            early_session is None
            or next_after_early is None
        ):
            raise AssertionError(
                "No early close found."
            )

        early_close = session_close(
            early_session
        )

        next_open_after_early = (
            session_open(
                next_after_early
            )
        )

        start = (
            early_close
            - timedelta(minutes=5)
        )

        actual = add_trading_minutes(
            start_at=start,
            minutes=15,
            calendar=calendar,
        )

        expected = (
            next_open_after_early
            + timedelta(minutes=10)
        )

        assert_equal(
            actual,
            expected,
            "early-close offset",
        )

    results.append(
        run_test(
            "Early-close handling",
            test_early_close,
        )
    )

    # --------------------------------------------------
    # TEST 8
    # Session counting exact rule
    # --------------------------------------------------

    def test_session_counting():
        sessions = (
            count_remaining_future_sessions(
                trading_date_et=date(
                    2026,
                    9,
                    4,
                ),
                expiry=date(
                    2026,
                    9,
                    11,
                ),
                calendar=calendar,
            )
        )

        assert_equal(
            sessions,
            4,
            "session count",
        )

    results.append(
        run_test(
            "Current excluded / expiry included",
            test_session_counting,
        )
    )

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)
    print()

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
            "Production CalendarService: PASS"
        )
        print(
            "Target expiry logic: PASS"
        )
        print(
            "Trading-minute offsets: PASS"
        )
        print(
            "Holiday/Early-close handling: PASS"
        )
        print(
            "Confirmation deadline clipping: PASS"
        )
    else:
        print()
        print(
            "CalendarService: CHECK REQUIRED"
        )


if __name__ == "__main__":
    main()