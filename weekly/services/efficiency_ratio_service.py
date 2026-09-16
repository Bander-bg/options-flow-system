from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence

from config import load_weekly_config
from weekly.domain.enums import GateStatus
from weekly.providers.alpaca_stock_provider import (
    StockMinuteBar,
)
from weekly.services.calendar_service import (
    as_et,
    session_close,
    session_open,
)


class EfficiencyRatioError(ValueError):
    """Raised when weekly ER inputs/configuration are invalid."""


@dataclass(frozen=True)
class RegimeHourBar:
    """
    One completed 1-hour RTH bar anchored to the
    actual session open (normally 09:30 ET).
    """

    start_at: datetime
    end_at: datetime

    open: float
    high: float
    low: float
    close: float
    volume: float

    source_minute_bar_count: int

    def __post_init__(self) -> None:
        if self.start_at.tzinfo is None:
            raise EfficiencyRatioError(
                "RegimeHourBar.start_at must be timezone-aware."
            )

        if self.end_at.tzinfo is None:
            raise EfficiencyRatioError(
                "RegimeHourBar.end_at must be timezone-aware."
            )

        if (
            self.end_at - self.start_at
            != timedelta(hours=1)
        ):
            raise EfficiencyRatioError(
                "RegimeHourBar must represent exactly 1 hour."
            )

        if self.source_minute_bar_count < 1:
            raise EfficiencyRatioError(
                "source_minute_bar_count must be >= 1."
            )

        for name, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
            ("volume", self.volume),
        ):
            if value < 0:
                raise EfficiencyRatioError(
                    f"RegimeHourBar.{name} cannot be negative."
                )

        if self.high < self.low:
            raise EfficiencyRatioError(
                "RegimeHourBar.high cannot be below low."
            )

        if not (
            self.low <= self.open <= self.high
        ):
            raise EfficiencyRatioError(
                "RegimeHourBar.open must be within high/low."
            )

        if not (
            self.low <= self.close <= self.high
        ):
            raise EfficiencyRatioError(
                "RegimeHourBar.close must be within high/low."
            )


@dataclass(frozen=True)
class EfficiencyRatioSettings:
    minimum_er: float
    min_er_bars: int

    def __post_init__(self) -> None:
        if not (
            0.0 <= self.minimum_er <= 1.0
        ):
            raise EfficiencyRatioError(
                "minimum_er must be between 0 and 1."
            )

        if self.min_er_bars < 2:
            raise EfficiencyRatioError(
                "min_er_bars must be >= 2."
            )

    @classmethod
    def from_config(
        cls,
    ) -> "EfficiencyRatioSettings":
        config = load_weekly_config(
            require_runtime_ready=True
        )

        regime = config["regime"]

        return cls(
            minimum_er=float(
                regime[
                    "efficiency_ratio_min"
                ]
            ),
            min_er_bars=int(
                regime[
                    "min_er_bars"
                ]
            ),
        )


@dataclass(frozen=True)
class EfficiencyRatioResult:
    efficiency_ratio: float | None
    status: GateStatus

    minimum_er: float
    min_er_bars: int

    anchor_at: datetime | None
    as_of: datetime

    hourly_bars: tuple[
        RegimeHourBar,
        ...
    ]

    reason: str


class EfficiencyRatioService:
    """
    weekly_v1 weekly Efficiency Ratio.

    Frozen behavior:
    - source = completed 1m RTH bars
    - manually resample into 1H bars
    - every 1H window is anchored to actual session open
    - weekly history starts at first actual trading session
      of the week
    - only completed 1H windows are eligible
    - at least config.regime.min_er_bars completed bars
      are required
    - ER = abs(last_close - first_close) /
           sum(abs(close[i] - close[i-1]))
    - zero denominator -> ER = 0
    - ER >= config.regime.efficiency_ratio_min -> PASS
      otherwise FAIL
    - insufficient usable data -> UNKNOWN

    No API calls and no DB writes.
    """

    def __init__(
        self,
        settings: EfficiencyRatioSettings | None = None,
    ) -> None:
        self.settings = (
            settings
            or EfficiencyRatioSettings.from_config()
        )

    def evaluate(
        self,
        *,
        as_of: datetime,
        trading_date_et: date,
        calendar,
        minute_bars: Sequence[StockMinuteBar],
    ) -> EfficiencyRatioResult:

        if as_of.tzinfo is None:
            raise EfficiencyRatioError(
                "as_of must be timezone-aware."
            )

        as_of_et = as_et(
            as_of
        )

        if (
            as_of_et.date()
            != trading_date_et
        ):
            raise EfficiencyRatioError(
                "as_of ET date must match trading_date_et."
            )

        ordered_sessions = sorted(
            calendar,
            key=lambda session: session.date,
        )

        current_session = next(
            (
                session
                for session in ordered_sessions
                if session.date
                == trading_date_et
            ),
            None,
        )

        if current_session is None:
            return EfficiencyRatioResult(
                efficiency_ratio=None,
                status=GateStatus.UNKNOWN,
                minimum_er=(
                    self.settings.minimum_er
                ),
                min_er_bars=(
                    self.settings.min_er_bars
                ),
                anchor_at=None,
                as_of=as_of_et,
                hourly_bars=(),
                reason="CURRENT_SESSION_NOT_FOUND",
            )

        week_start = (
            trading_date_et
            - timedelta(
                days=trading_date_et.weekday()
            )
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
            return EfficiencyRatioResult(
                efficiency_ratio=None,
                status=GateStatus.UNKNOWN,
                minimum_er=(
                    self.settings.minimum_er
                ),
                min_er_bars=(
                    self.settings.min_er_bars
                ),
                anchor_at=None,
                as_of=as_of_et,
                hourly_bars=(),
                reason="WEEK_SESSIONS_NOT_FOUND",
            )

        anchor_at = session_open(
            week_sessions[0]
        )

        hourly_bars = (
            self._resample_completed_hour_bars(
                as_of_et=as_of_et,
                week_sessions=week_sessions,
                minute_bars=minute_bars,
            )
        )

        if (
            len(hourly_bars)
            < self.settings.min_er_bars
        ):
            return EfficiencyRatioResult(
                efficiency_ratio=None,
                status=GateStatus.UNKNOWN,
                minimum_er=(
                    self.settings.minimum_er
                ),
                min_er_bars=(
                    self.settings.min_er_bars
                ),
                anchor_at=anchor_at,
                as_of=as_of_et,
                hourly_bars=hourly_bars,
                reason="INSUFFICIENT_COMPLETED_1H_BARS",
            )

        closes = [
            bar.close
            for bar in hourly_bars
        ]

        net_move = abs(
            closes[-1]
            - closes[0]
        )

        total_move = sum(
            abs(
                closes[index]
                - closes[index - 1]
            )
            for index in range(
                1,
                len(closes),
            )
        )

        if total_move == 0:
            efficiency_ratio = 0.0

        else:
            efficiency_ratio = (
                net_move
                / total_move
            )

        if (
            efficiency_ratio
            >= self.settings.minimum_er
        ):
            status = GateStatus.PASS
            reason = (
                "EFFICIENCY_RATIO_AT_OR_ABOVE_MINIMUM"
            )

        else:
            status = GateStatus.FAIL
            reason = (
                "EFFICIENCY_RATIO_BELOW_MINIMUM"
            )

        return EfficiencyRatioResult(
            efficiency_ratio=(
                efficiency_ratio
            ),
            status=status,
            minimum_er=(
                self.settings.minimum_er
            ),
            min_er_bars=(
                self.settings.min_er_bars
            ),
            anchor_at=anchor_at,
            as_of=as_of_et,
            hourly_bars=hourly_bars,
            reason=reason,
        )

    @staticmethod
    def _resample_completed_hour_bars(
        *,
        as_of_et: datetime,
        week_sessions,
        minute_bars: Sequence[StockMinuteBar],
    ) -> tuple[
        RegimeHourBar,
        ...
    ]:

        sorted_minute_bars = sorted(
            minute_bars,
            key=lambda bar: bar.start_at,
        )

        hourly_bars: list[
            RegimeHourBar
        ] = []

        for session in week_sessions:
            open_at = session_open(
                session
            )

            close_at = session_close(
                session
            )

            window_start = open_at

            while True:
                window_end = (
                    window_start
                    + timedelta(hours=1)
                )

                if window_end > close_at:
                    break

                if window_end > as_of_et:
                    break

                window_minutes = [
                    bar
                    for bar in sorted_minute_bars
                    if (
                        window_start
                        <= as_et(bar.start_at)
                        and as_et(bar.end_at)
                        <= window_end
                        and as_et(bar.end_at)
                        <= as_of_et
                    )
                ]

                if window_minutes:
                    window_minutes.sort(
                        key=lambda bar: bar.start_at
                    )

                    hourly_bars.append(
                        RegimeHourBar(
                            start_at=window_start,
                            end_at=window_end,
                            open=window_minutes[0].open,
                            high=max(bar.high for bar in window_minutes),
                            low=min(bar.low for bar in window_minutes),
                            close=window_minutes[-1].close,
                            volume=sum(bar.volume for bar in window_minutes),
                            source_minute_bar_count=len(window_minutes),
                        )
                    )

                window_start = window_end

        hourly_bars.sort(
            key=lambda bar: bar.start_at
        )

        return tuple(hourly_bars)
