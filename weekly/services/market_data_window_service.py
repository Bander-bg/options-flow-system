from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from weekly.services.calendar_service import (
    as_et,
    find_session,
    session_close,
    session_open,
)


class MarketDataWindowError(ValueError):
    """Invalid market-data history window."""


@dataclass(frozen=True)
class MarketDataWindow:
    trading_date_et: date
    sessions: tuple
    start_at: datetime
    end_at: datetime
    previous_session_count: int


class MarketDataWindowService:
    """
    Select the calendar/history window required by the
    weekly runtime.

    The requested lookback counts PREVIOUS sessions.
    The current trading session is included separately.

    Example:
        previous_sessions=20
        -> up to 20 prior sessions + current session.
    """

    def build(
        self,
        *,
        trading_date_et: date,
        as_of: datetime,
        calendar,
        previous_sessions: int,
    ) -> MarketDataWindow:
        if as_of.tzinfo is None:
            raise MarketDataWindowError(
                "as_of must be timezone-aware."
            )

        if previous_sessions < 0:
            raise MarketDataWindowError(
                "previous_sessions must be >= 0."
            )

        as_of_et = as_et(as_of)

        if as_of_et.date() != trading_date_et:
            raise MarketDataWindowError(
                "as_of ET date must match "
                "trading_date_et."
            )

        ordered = sorted(
            calendar,
            key=lambda session: session.date,
        )

        current_session = find_session(
            trading_date_et=trading_date_et,
            calendar=ordered,
        )

        if current_session is None:
            raise MarketDataWindowError(
                "Current trading session was not "
                "found in calendar."
            )

        prior = [
            session
            for session in ordered
            if session.date < trading_date_et
        ]

        selected_prior = prior[
            -previous_sessions:
        ] if previous_sessions else []

        selected_sessions = tuple(
            [
                *selected_prior,
                current_session,
            ]
        )

        start_at = session_open(
            selected_sessions[0]
        )

        current_close = session_close(
            current_session
        )

        end_at = min(
            as_of_et,
            current_close,
        )

        if end_at <= start_at:
            raise MarketDataWindowError(
                "Market-data window end must be "
                "after its start."
            )

        return MarketDataWindow(
            trading_date_et=trading_date_et,
            sessions=selected_sessions,
            start_at=start_at,
            end_at=end_at,
            previous_session_count=len(
                selected_prior
            ),
        )
