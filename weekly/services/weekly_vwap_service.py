from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence
from zoneinfo import ZoneInfo

from weekly.domain.enums import (
    Direction,
    GateStatus,
)
from weekly.providers.alpaca_stock_provider import (
    StockMinuteBar,
)
from weekly.services.calendar_service import (
    as_et,
    session_close,
    session_open,
)


ET = ZoneInfo("America/New_York")


class WeeklyVWAPError(ValueError):
    """Raised when Weekly VWAP inputs are invalid."""


@dataclass(frozen=True)
class WeeklyVWAPResult:
    weekly_vwap: float | None
    underlying_price: float | None
    status: GateStatus

    anchor_at: datetime | None
    as_of: datetime

    included_bar_count: int
    cumulative_volume: float

    reason: str


class WeeklyVWAPService:
    """
    weekly_v1 Weekly VWAP gate.

    Frozen behavior:
    - completed 1-minute bars only
    - regular trading hours only
    - anchor at the first actual trading session of the week
    - bullish requires underlying price > Weekly VWAP
    - bearish requires underlying price < Weekly VWAP
    - missing/insufficient usable data -> UNKNOWN

    This service performs no API calls and no DB writes.
    """

    def evaluate(
        self,
        *,
        direction: Direction,
        as_of: datetime,
        trading_date_et: date,
        calendar,
        minute_bars: Sequence[StockMinuteBar],
    ) -> WeeklyVWAPResult:

        if as_of.tzinfo is None:
            raise WeeklyVWAPError(
                "as_of must be timezone-aware."
            )

        as_of_et = as_et(as_of)

        if as_of_et.date() != trading_date_et:
            raise WeeklyVWAPError(
                "as_of ET date must match trading_date_et."
            )

        ordered_sessions = sorted(
            calendar,
            key=lambda session: session.date,
        )

        current_session = None

        for session in ordered_sessions:
            if session.date == trading_date_et:
                current_session = session
                break

        if current_session is None:
            return WeeklyVWAPResult(
                weekly_vwap=None,
                underlying_price=None,
                status=GateStatus.UNKNOWN,
                anchor_at=None,
                as_of=as_of_et,
                included_bar_count=0,
                cumulative_volume=0.0,
                reason="CURRENT_SESSION_NOT_FOUND",
            )

        week_start = (
            trading_date_et
            - date.resolution * trading_date_et.weekday()
        )

        week_sessions = [
            session
            for session in ordered_sessions
            if (
                week_start
                <= session.date
                <= trading_date_et
            )
        ]

        if not week_sessions:
            return WeeklyVWAPResult(
                weekly_vwap=None,
                underlying_price=None,
                status=GateStatus.UNKNOWN,
                anchor_at=None,
                as_of=as_of_et,
                included_bar_count=0,
                cumulative_volume=0.0,
                reason="WEEK_SESSIONS_NOT_FOUND",
            )

        first_session = week_sessions[0]
        anchor_at = session_open(
            first_session
        )

        usable_bars: list[
            StockMinuteBar
        ] = []

        for bar in minute_bars:
            bar_start_et = as_et(
                bar.start_at
            )
            bar_end_et = as_et(
                bar.end_at
            )

            if bar_end_et > as_of_et:
                continue

            matching_session = None

            for session in week_sessions:
                open_at = session_open(
                    session
                )
                close_at = session_close(
                    session
                )

                if (
                    open_at
                    <= bar_start_et
                    and bar_end_et
                    <= close_at
                ):
                    matching_session = session
                    break

            if matching_session is None:
                continue

            if bar_start_et < anchor_at:
                continue

            usable_bars.append(
                bar
            )

        usable_bars.sort(
            key=lambda bar: bar.start_at
        )

        if not usable_bars:
            return WeeklyVWAPResult(
                weekly_vwap=None,
                underlying_price=None,
                status=GateStatus.UNKNOWN,
                anchor_at=anchor_at,
                as_of=as_of_et,
                included_bar_count=0,
                cumulative_volume=0.0,
                reason="NO_COMPLETED_RTH_BARS",
            )

        cumulative_pv = 0.0
        cumulative_volume = 0.0

        for bar in usable_bars:
            if bar.volume <= 0:
                continue

            if (
                bar.vwap is not None
                and bar.vwap > 0
            ):
                bar_price = bar.vwap

            else:
                bar_price = (
                    bar.high
                    + bar.low
                    + bar.close
                ) / 3.0

            cumulative_pv += (
                bar_price
                * bar.volume
            )

            cumulative_volume += (
                bar.volume
            )

        if cumulative_volume <= 0:
            return WeeklyVWAPResult(
                weekly_vwap=None,
                underlying_price=None,
                status=GateStatus.UNKNOWN,
                anchor_at=anchor_at,
                as_of=as_of_et,
                included_bar_count=len(
                    usable_bars
                ),
                cumulative_volume=0.0,
                reason="ZERO_USABLE_VOLUME",
            )

        weekly_vwap = (
            cumulative_pv
            / cumulative_volume
        )

        underlying_price = (
            usable_bars[-1].close
        )

        if direction is Direction.BULLISH:
            if underlying_price > weekly_vwap:
                status = GateStatus.PASS
                reason = (
                    "BULLISH_PRICE_ABOVE_WEEKLY_VWAP"
                )

            elif underlying_price < weekly_vwap:
                status = GateStatus.FAIL
                reason = (
                    "BULLISH_PRICE_BELOW_WEEKLY_VWAP"
                )

            else:
                status = GateStatus.UNKNOWN
                reason = (
                    "PRICE_EQUALS_WEEKLY_VWAP"
                )

        elif direction is Direction.BEARISH:
            if underlying_price < weekly_vwap:
                status = GateStatus.PASS
                reason = (
                    "BEARISH_PRICE_BELOW_WEEKLY_VWAP"
                )

            elif underlying_price > weekly_vwap:
                status = GateStatus.FAIL
                reason = (
                    "BEARISH_PRICE_ABOVE_WEEKLY_VWAP"
                )

            else:
                status = GateStatus.UNKNOWN
                reason = (
                    "PRICE_EQUALS_WEEKLY_VWAP"
                )

        else:
            raise WeeklyVWAPError(
                f"Unsupported direction: {direction}"
            )

        return WeeklyVWAPResult(
            weekly_vwap=weekly_vwap,
            underlying_price=underlying_price,
            status=status,
            anchor_at=anchor_at,
            as_of=as_of_et,
            included_bar_count=len(
                usable_bars
            ),
            cumulative_volume=(
                cumulative_volume
            ),
            reason=reason,
        )
