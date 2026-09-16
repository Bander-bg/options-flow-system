from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import fsum
from typing import Sequence

from config import load_weekly_config
from weekly.providers.alpaca_stock_provider import StockMinuteBar
from weekly.services.calendar_service import as_et, session_close, session_open
from weekly.services.efficiency_ratio_service import (
    EfficiencyRatioService,
    RegimeHourBar,
)


class ATRError(ValueError):
    """Raised when ATR inputs/configuration are invalid."""


@dataclass(frozen=True)
class ATRSettings:
    atr_1h_period: int
    atr_15m_period: int

    def __post_init__(self) -> None:
        if self.atr_1h_period < 1:
            raise ATRError("atr_1h_period must be >= 1.")
        if self.atr_15m_period < 1:
            raise ATRError("atr_15m_period must be >= 1.")

    @classmethod
    def from_config(
        cls,
        path: str = "weekly_config.yaml",
    ) -> "ATRSettings":
        config = load_weekly_config(
            path=path,
            require_runtime_ready=True,
        )
        regime = config["regime"]
        return cls(
            atr_1h_period=int(regime["atr_1h_period"]),
            atr_15m_period=int(regime["atr_15m_period"]),
        )


@dataclass(frozen=True)
class ATR15MinuteBar:
    start_at: datetime
    end_at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source_minute_bar_count: int

    def __post_init__(self) -> None:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ATRError("ATR15MinuteBar timestamps must be timezone-aware.")
        if self.end_at - self.start_at != timedelta(minutes=15):
            raise ATRError("ATR15MinuteBar must represent exactly 15 minutes.")
        if self.source_minute_bar_count < 1:
            raise ATRError("source_minute_bar_count must be >= 1.")
        for name, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
            ("volume", self.volume),
        ):
            if value < 0:
                raise ATRError(f"ATR15MinuteBar.{name} cannot be negative.")
        if self.high < self.low:
            raise ATRError("ATR15MinuteBar.high cannot be below low.")
        if not self.low <= self.open <= self.high:
            raise ATRError("ATR15MinuteBar.open must be within high/low.")
        if not self.low <= self.close <= self.high:
            raise ATRError("ATR15MinuteBar.close must be within high/low.")


@dataclass(frozen=True)
class ATRResult:
    atr_1h: float | None
    atr_15m: float | None
    atr_1h_period: int
    atr_15m_period: int
    completed_1h_bar_count: int
    completed_15m_bar_count: int
    atr_1h_reason: str
    atr_15m_reason: str
    as_of: datetime
    hourly_bars: tuple[RegimeHourBar, ...]
    fifteen_minute_bars: tuple[ATR15MinuteBar, ...]


class ATRService:
    """
    Rolling weekly_v1 ATR calculator.

    Rules:
    - source is completed 1m RTH bars
    - 15m windows are anchored to each actual session open
    - 1H windows reuse the ER service resampling implementation
    - only time-completed windows are eligible
    - ATR does not reset at week boundaries
    - ATR(N) is the arithmetic mean of the last N True Ranges
    - N+1 completed bars are required to observe the previous close
    """

    def __init__(self, settings: ATRSettings) -> None:
        self.settings = settings

    @classmethod
    def from_config(
        cls,
        path: str = "weekly_config.yaml",
    ) -> "ATRService":
        return cls(ATRSettings.from_config(path=path))

    def evaluate(
        self,
        *,
        as_of: datetime,
        trading_date_et: date,
        calendar,
        minute_bars: Sequence[StockMinuteBar],
    ) -> ATRResult:
        if as_of.tzinfo is None:
            raise ATRError("as_of must be timezone-aware.")

        as_of_et = as_et(as_of)
        if as_of_et.date() != trading_date_et:
            raise ATRError("as_of ET date must match trading_date_et.")

        ordered_sessions = sorted(calendar, key=lambda session: session.date)
        current_session = next(
            (
                session
                for session in ordered_sessions
                if session.date == trading_date_et
            ),
            None,
        )

        if current_session is None:
            return ATRResult(
                atr_1h=None,
                atr_15m=None,
                atr_1h_period=self.settings.atr_1h_period,
                atr_15m_period=self.settings.atr_15m_period,
                completed_1h_bar_count=0,
                completed_15m_bar_count=0,
                atr_1h_reason="CURRENT_SESSION_NOT_FOUND",
                atr_15m_reason="CURRENT_SESSION_NOT_FOUND",
                as_of=as_of_et,
                hourly_bars=(),
                fifteen_minute_bars=(),
            )

        eligible_sessions = tuple(
            session
            for session in ordered_sessions
            if session.date <= trading_date_et
        )

        hourly_bars = EfficiencyRatioService._resample_completed_hour_bars(
            as_of_et=as_of_et,
            week_sessions=eligible_sessions,
            minute_bars=minute_bars,
        )
        fifteen_minute_bars = self._resample_completed_15m_bars(
            as_of_et=as_of_et,
            sessions=eligible_sessions,
            minute_bars=minute_bars,
        )

        atr_1h, atr_1h_reason = self._calculate_atr(
            bars=hourly_bars,
            period=self.settings.atr_1h_period,
            insufficient_reason="INSUFFICIENT_COMPLETED_1H_BARS",
        )
        atr_15m, atr_15m_reason = self._calculate_atr(
            bars=fifteen_minute_bars,
            period=self.settings.atr_15m_period,
            insufficient_reason="INSUFFICIENT_COMPLETED_15M_BARS",
        )

        return ATRResult(
            atr_1h=atr_1h,
            atr_15m=atr_15m,
            atr_1h_period=self.settings.atr_1h_period,
            atr_15m_period=self.settings.atr_15m_period,
            completed_1h_bar_count=len(hourly_bars),
            completed_15m_bar_count=len(fifteen_minute_bars),
            atr_1h_reason=atr_1h_reason,
            atr_15m_reason=atr_15m_reason,
            as_of=as_of_et,
            hourly_bars=hourly_bars,
            fifteen_minute_bars=fifteen_minute_bars,
        )

    @staticmethod
    def _calculate_atr(
        *,
        bars,
        period: int,
        insufficient_reason: str,
    ) -> tuple[float | None, str]:
        ordered = sorted(bars, key=lambda bar: bar.start_at)
        required = period + 1
        if len(ordered) < required:
            return None, insufficient_reason

        working = ordered[-required:]
        true_ranges: list[float] = []

        for index in range(1, len(working)):
            current = working[index]
            previous = working[index - 1]
            true_ranges.append(
                max(
                    current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close),
                )
            )

        if len(true_ranges) != period:
            raise ATRError("ATR internal period calculation mismatch.")

        return float(fsum(true_ranges) / period), "ATR_AVAILABLE"

    @staticmethod
    def _resample_completed_15m_bars(
        *,
        as_of_et: datetime,
        sessions,
        minute_bars: Sequence[StockMinuteBar],
    ) -> tuple[ATR15MinuteBar, ...]:
        sorted_minute_bars = sorted(
            minute_bars,
            key=lambda bar: bar.start_at,
        )
        output: list[ATR15MinuteBar] = []

        for session in sessions:
            open_at = session_open(session)
            close_at = session_close(session)
            window_start = open_at

            while True:
                window_end = window_start + timedelta(minutes=15)
                if window_end > close_at or window_end > as_of_et:
                    break

                window_minutes = [
                    bar
                    for bar in sorted_minute_bars
                    if (
                        window_start <= as_et(bar.start_at)
                        and as_et(bar.end_at) <= window_end
                        and as_et(bar.end_at) <= as_of_et
                    )
                ]

                if window_minutes:
                    window_minutes.sort(key=lambda bar: bar.start_at)
                    output.append(
                        ATR15MinuteBar(
                            start_at=window_start,
                            end_at=window_end,
                            open=window_minutes[0].open,
                            high=max(bar.high for bar in window_minutes),
                            low=min(bar.low for bar in window_minutes),
                            close=window_minutes[-1].close,
                            volume=fsum(bar.volume for bar in window_minutes),
                            source_minute_bar_count=len(window_minutes),
                        )
                    )

                window_start = window_end

        output.sort(key=lambda bar: bar.start_at)
        return tuple(output)
