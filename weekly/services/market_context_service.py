from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetCalendarRequest

from weekly.services.calendar_service import as_et


class MarketContextError(RuntimeError):
    """Unable to build the weekly market context."""


@dataclass(frozen=True)
class MarketContext:
    market_timestamp: datetime
    trading_date_et: date
    market_is_open: bool
    is_trading_day: bool
    next_open: datetime
    next_close: datetime
    calendar: tuple


class MarketContextService:
    """
    Build weekly runtime market context from Alpaca.

    The Alpaca market clock is authoritative for the
    current ET trading date. Local computer/Riyadh time
    is not used to determine the trading date.
    """

    def __init__(
        self,
        *,
        trading_client: TradingClient,
    ) -> None:
        self.trading_client = trading_client

    def fetch(
        self,
        *,
        required_previous_sessions: int,
        history_calendar_days: int = 60,
        future_calendar_days: int = 30,
    ) -> MarketContext:
        if required_previous_sessions < 0:
            raise MarketContextError(
                "required_previous_sessions "
                "must be >= 0."
            )

        if history_calendar_days < 1:
            raise MarketContextError(
                "history_calendar_days must be >= 1."
            )

        if future_calendar_days < 1:
            raise MarketContextError(
                "future_calendar_days must be >= 1."
            )

        try:
            clock = self.trading_client.get_clock()
        except Exception as exc:
            raise MarketContextError(
                "Failed to fetch Alpaca market clock."
            ) from exc

        market_timestamp = as_et(
            clock.timestamp
        )

        trading_date_et = (
            market_timestamp.date()
        )

        start_date = (
            trading_date_et
            - timedelta(
                days=history_calendar_days
            )
        )

        end_date = (
            trading_date_et
            + timedelta(
                days=future_calendar_days
            )
        )

        try:
            calendar = tuple(
                self.trading_client.get_calendar(
                    GetCalendarRequest(
                        start=start_date,
                        end=end_date,
                    )
                )
            )
        except Exception as exc:
            raise MarketContextError(
                "Failed to fetch Alpaca trading calendar."
            ) from exc

        current_sessions = [
            session
            for session in calendar
            if session.date
            == trading_date_et
        ]

        if len(current_sessions) > 1:
            raise MarketContextError(
                "Current trading session was found "
                "more than once in calendar."
            )

        is_trading_day = (
            len(current_sessions) == 1
        )

        if (
            bool(clock.is_open)
            and not is_trading_day
        ):
            raise MarketContextError(
                "Alpaca clock reports market open "
                "but current trading session is missing."
            )

        previous_sessions = [
            session
            for session in calendar
            if session.date
            < trading_date_et
        ]

        if (
            len(previous_sessions)
            < required_previous_sessions
        ):
            raise MarketContextError(
                "Calendar history does not contain "
                f"{required_previous_sessions} previous "
                "trading sessions."
            )

        return MarketContext(
            market_timestamp=market_timestamp,
            trading_date_et=trading_date_et,
            market_is_open=bool(
                clock.is_open
            ),
            is_trading_day=is_trading_day,
            next_open=as_et(
                clock.next_open
            ),
            next_close=as_et(
                clock.next_close
            ),
            calendar=calendar,
        )
