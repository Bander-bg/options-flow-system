from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")


def as_et(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=ET
        )

    return value.astimezone(
        ET
    )


def session_open(
    session,
) -> datetime:
    return as_et(
        session.open
    )


def session_close(
    session,
) -> datetime:
    return as_et(
        session.close
    )


def count_remaining_future_sessions(
    *,
    trading_date_et: date,
    expiry: date,
    calendar,
) -> int:
    """
    Current trading session is excluded.
    Expiry session is included.
    """

    return sum(
        1
        for session in calendar
        if (
            trading_date_et
            < session.date
            <= expiry
        )
    )


def select_target_expiry(
    *,
    trading_date_et: date,
    listed_expiries: list[date],
    calendar,
    min_sessions: int,
    max_sessions: int,
) -> tuple[date, int] | None:
    """
    Choose the nearest ACTUAL listed expiration
    with remaining future trading sessions inside
    the configured eligibility window.
    """

    eligible = []

    for expiry in sorted(
        listed_expiries
    ):
        if expiry <= trading_date_et:
            continue

        remaining_sessions = (
            count_remaining_future_sessions(
                trading_date_et=trading_date_et,
                expiry=expiry,
                calendar=calendar,
            )
        )

        if (
            min_sessions
            <= remaining_sessions
            <= max_sessions
        ):
            eligible.append(
                (
                    expiry,
                    remaining_sessions,
                )
            )

    if not eligible:
        return None

    return eligible[0]


def add_trading_minutes(
    *,
    start_at: datetime,
    minutes: int,
    calendar,
) -> datetime:
    """
    Add actual RTH trading minutes only.

    Overnight hours, weekends, holidays,
    and closed-market periods consume zero
    trading minutes.
    """

    if minutes < 0:
        raise ValueError(
            "minutes must be >= 0"
        )

    current = as_et(
        start_at
    )

    if minutes == 0:
        return current

    remaining = timedelta(
        minutes=minutes
    )

    ordered_sessions = sorted(
        calendar,
        key=lambda session: (
            session.date
        ),
    )

    for session in ordered_sessions:
        open_at = session_open(
            session
        )

        close_at = session_close(
            session
        )

        if current > close_at:
            continue

        if current < open_at:
            current = open_at

        if not (
            open_at
            <= current
            <= close_at
        ):
            continue

        available = (
            close_at - current
        )

        if remaining <= available:
            return (
                current
                + remaining
            )

        remaining -= available

        current = (
            close_at
            + timedelta(
                microseconds=1
            )
        )

    raise RuntimeError(
        "Calendar range is not wide enough "
        "to complete trading-minute offset."
    )


def find_session(
    *,
    trading_date_et: date,
    calendar,
):
    for session in calendar:
        if (
            session.date
            == trading_date_et
        ):
            return session

    return None


def confirmation_deadline(
    *,
    candidate_at: datetime,
    confirmation_minutes: int,
    trading_date_et: date,
    calendar,
) -> tuple[datetime, datetime]:
    """
    Returns:

    requested_confirmation_deadline_at
    confirmation_deadline_at

    The requested deadline may extend into
    another trading session.

    The actual candidate deadline is clipped
    to the current official session close.
    """

    current_session = find_session(
        trading_date_et=trading_date_et,
        calendar=calendar,
    )

    if current_session is None:
        raise RuntimeError(
            "Current trading session "
            "not found in calendar."
        )

    official_close = session_close(
        current_session
    )

    requested = add_trading_minutes(
        start_at=candidate_at,
        minutes=confirmation_minutes,
        calendar=calendar,
    )

    actual = min(
        requested,
        official_close,
    )

    return (
        requested,
        actual,
    )