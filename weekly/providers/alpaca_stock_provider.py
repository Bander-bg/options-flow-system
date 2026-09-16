from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from dotenv import load_dotenv

from alpaca.common.exceptions import APIError
from alpaca.data.enums import DataFeed
from alpaca.data.historical.stock import (
    StockHistoricalDataClient,
)
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from config import load_weekly_config


class AlpacaStockProviderError(RuntimeError):
    """Raised when Alpaca stock market data cannot be retrieved safely."""


@dataclass(frozen=True)
class StockMinuteBar:
    """
    One completed 1-minute stock bar.

    start_at is the Alpaca bar timestamp.
    end_at is exactly start_at + 1 minute.
    """

    start_at: datetime
    end_at: datetime

    open: float
    high: float
    low: float
    close: float
    volume: float

    trade_count: int | None = None
    vwap: float | None = None

    def __post_init__(self) -> None:
        if self.start_at.tzinfo is None:
            raise ValueError(
                "StockMinuteBar.start_at must be timezone-aware."
            )

        if self.end_at.tzinfo is None:
            raise ValueError(
                "StockMinuteBar.end_at must be timezone-aware."
            )

        if (
            self.end_at - self.start_at
            != timedelta(minutes=1)
        ):
            raise ValueError(
                "StockMinuteBar must represent exactly 1 minute."
            )

        for name, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
            ("volume", self.volume),
        ):
            if value < 0:
                raise ValueError(
                    f"StockMinuteBar.{name} cannot be negative."
                )

        if self.high < self.low:
            raise ValueError(
                "StockMinuteBar.high cannot be below low."
            )

        if not (
            self.low <= self.open <= self.high
        ):
            raise ValueError(
                "StockMinuteBar.open must be within high/low."
            )

        if not (
            self.low <= self.close <= self.high
        ):
            raise ValueError(
                "StockMinuteBar.close must be within high/low."
            )

        if (
            self.trade_count is not None
            and self.trade_count < 0
        ):
            raise ValueError(
                "StockMinuteBar.trade_count cannot be negative."
            )

        if (
            self.vwap is not None
            and self.vwap < 0
        ):
            raise ValueError(
                "StockMinuteBar.vwap cannot be negative."
            )


@dataclass(frozen=True)
class StockBarsResult:
    ticker: str
    provider: str
    feed: str
    requested_start: datetime
    requested_end: datetime
    bars: tuple[StockMinuteBar, ...]

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError(
                "StockBarsResult.ticker cannot be empty."
            )

        if self.requested_start.tzinfo is None:
            raise ValueError(
                "requested_start must be timezone-aware."
            )

        if self.requested_end.tzinfo is None:
            raise ValueError(
                "requested_end must be timezone-aware."
            )

        if self.requested_end <= self.requested_start:
            raise ValueError(
                "requested_end must be after requested_start."
            )

        if self.provider != "ALPACA":
            raise ValueError(
                "StockBarsResult.provider must be ALPACA."
            )

        if self.feed not in {
            DataFeed.SIP.value,
            DataFeed.IEX.value,
        }:
            raise ValueError(
                "StockBarsResult.feed must be sip or iex."
            )


def _get_env_value(
    *names: str,
) -> str | None:
    for name in names:
        value = os.getenv(name)

        if value:
            stripped = value.strip()

            if stripped:
                return stripped

    return None


def _normalize_feed(
    value: str | DataFeed,
) -> DataFeed:
    if isinstance(value, DataFeed):
        feed = value

    else:
        normalized = str(value).strip().lower()

        try:
            feed = DataFeed(normalized)
        except ValueError as exc:
            raise ValueError(
                "Stock feed must be 'sip' or 'iex'."
            ) from exc

    if feed not in {
        DataFeed.SIP,
        DataFeed.IEX,
    }:
        raise ValueError(
            "Stock feed must be 'sip' or 'iex'."
        )

    return feed


def _is_sip_entitlement_error(
    exc: APIError,
) -> bool:
    status_code = getattr(
        exc,
        "status_code",
        None,
    )

    if status_code == 403:
        return True

    text = str(exc).lower()

    entitlement_markers = (
        "403",
        "subscription",
        "not permitted",
        "not authorized",
        "forbidden",
    )

    return any(
        marker in text
        for marker in entitlement_markers
    )


class AlpacaStockProvider:
    """
    weekly_v1 stock historical-data provider.

    Responsibilities:
    - read Alpaca credentials from the established .env names
    - request completed 1-minute stock bars
    - use the configured preferred feed
    - fall back SIP -> IEX only for entitlement/403 failures
    - return the actual feed used as provenance

    Explicitly NOT responsible for:
    - trading-calendar logic
    - deciding RTH session boundaries
    - Weekly VWAP calculation
    - 1H resampling
    - Efficiency Ratio calculation
    - ATR calculation
    - Signal state transitions

    Callers must pass exact calendar-derived RTH start/end
    boundaries. This avoids hardcoding 09:30-16:00 and keeps
    early-close handling in CalendarService.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        secret_key: str | None = None,
        preferred_feed: str | DataFeed | None = None,
        client: StockHistoricalDataClient | None = None,
    ) -> None:
        load_dotenv()

        if preferred_feed is None:
            config = load_weekly_config(
                require_runtime_ready=True
            )

            preferred_feed = config[
                "market"
            ][
                "stock_data_feed_preferred"
            ]

        self.preferred_feed = _normalize_feed(
            preferred_feed
        )

        if client is not None:
            self.client = client
            return

        resolved_api_key = (
            api_key
            or _get_env_value(
                "ALPACA_API_KEY",
                "ALPACA_KEY",
                "APCA_API_KEY_ID",
            )
        )

        resolved_secret_key = (
            secret_key
            or _get_env_value(
                "ALPACA_SECRET_KEY",
                "ALPACA_SECRET",
                "APCA_API_SECRET_KEY",
            )
        )

        if (
            not resolved_api_key
            or not resolved_secret_key
        ):
            raise AlpacaStockProviderError(
                "Alpaca API credentials were not found in .env."
            )

        self.client = StockHistoricalDataClient(
            resolved_api_key,
            resolved_secret_key,
        )

    def get_minute_bars(
        self,
        *,
        ticker: str,
        start: datetime,
        end: datetime,
    ) -> StockBarsResult:
        """
        Fetch completed 1-minute bars in [start, end].

        Only bars whose full minute has completed by `end`
        are returned.

        RTH filtering itself is intentionally not hardcoded
        here. The caller must pass calendar-derived RTH
        boundaries.
        """

        normalized_ticker = ticker.strip().upper()

        if not normalized_ticker:
            raise ValueError(
                "ticker cannot be empty."
            )

        if start.tzinfo is None:
            raise ValueError(
                "start must be timezone-aware."
            )

        if end.tzinfo is None:
            raise ValueError(
                "end must be timezone-aware."
            )

        if end <= start:
            raise ValueError(
                "end must be after start."
            )

        feeds_to_try: list[DataFeed] = [
            self.preferred_feed
        ]

        if (
            self.preferred_feed
            is DataFeed.SIP
        ):
            feeds_to_try.append(
                DataFeed.IEX
            )

        last_error: Exception | None = None

        for index, feed in enumerate(
            feeds_to_try
        ):
            try:
                return self._fetch_minute_bars(
                    ticker=normalized_ticker,
                    start=start,
                    end=end,
                    feed=feed,
                )

            except APIError as exc:
                last_error = exc

                has_fallback = (
                    index
                    < len(feeds_to_try) - 1
                )

                should_fallback = (
                    feed is DataFeed.SIP
                    and has_fallback
                    and _is_sip_entitlement_error(
                        exc
                    )
                )

                if should_fallback:
                    continue

                raise AlpacaStockProviderError(
                    "Alpaca stock bars request failed "
                    f"for {normalized_ticker} "
                    f"using feed={feed.value}: {exc}"
                ) from exc

            except Exception as exc:
                last_error = exc

                raise AlpacaStockProviderError(
                    "Unexpected Alpaca stock bars error "
                    f"for {normalized_ticker} "
                    f"using feed={feed.value}: {exc}"
                ) from exc

        raise AlpacaStockProviderError(
            "Alpaca stock bars request failed "
            f"for {normalized_ticker}: {last_error}"
        )

    def _fetch_minute_bars(
        self,
        *,
        ticker: str,
        start: datetime,
        end: datetime,
        feed: DataFeed,
    ) -> StockBarsResult:

        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            feed=feed,
        )

        response = self.client.get_stock_bars(
            request
        )

        raw_bars = self._extract_symbol_bars(
            response=response,
            ticker=ticker,
        )

        completed_bars = tuple(
            self._convert_completed_bars(
                raw_bars=raw_bars,
                requested_start=start,
                requested_end=end,
            )
        )

        return StockBarsResult(
            ticker=ticker,
            provider="ALPACA",
            feed=feed.value,
            requested_start=start,
            requested_end=end,
            bars=completed_bars,
        )

    @staticmethod
    def _extract_symbol_bars(
        *,
        response,
        ticker: str,
    ) -> Iterable:
        data = getattr(
            response,
            "data",
            None,
        )

        if isinstance(data, dict):
            return data.get(
                ticker,
                [],
            )

        try:
            return response[
                ticker
            ]

        except (
            KeyError,
            TypeError,
        ):
            return []

    @staticmethod
    def _convert_completed_bars(
        *,
        raw_bars: Iterable,
        requested_start: datetime,
        requested_end: datetime,
    ) -> Iterable[StockMinuteBar]:

        normalized_start = (
            requested_start.astimezone(
                timezone.utc
            )
        )

        normalized_end = (
            requested_end.astimezone(
                timezone.utc
            )
        )

        converted: list[
            StockMinuteBar
        ] = []

        for raw in raw_bars:
            timestamp = getattr(
                raw,
                "timestamp",
                None,
            )

            if timestamp is None:
                raise AlpacaStockProviderError(
                    "Alpaca bar is missing timestamp."
                )

            if timestamp.tzinfo is None:
                raise AlpacaStockProviderError(
                    "Alpaca bar timestamp must be timezone-aware."
                )

            start_at = timestamp.astimezone(
                timezone.utc
            )

            end_at = (
                start_at
                + timedelta(minutes=1)
            )

            if start_at < normalized_start:
                continue

            # Completed-bars-only rule.
            if end_at > normalized_end:
                continue

            trade_count = getattr(
                raw,
                "trade_count",
                None,
            )

            raw_vwap = getattr(
                raw,
                "vwap",
                None,
            )

            converted.append(
                StockMinuteBar(
                    start_at=start_at,
                    end_at=end_at,
                    open=float(raw.open),
                    high=float(raw.high),
                    low=float(raw.low),
                    close=float(raw.close),
                    volume=float(raw.volume),
                    trade_count=(
                        int(trade_count)
                        if trade_count is not None
                        else None
                    ),
                    vwap=(
                        float(raw_vwap)
                        if raw_vwap is not None
                        else None
                    ),
                )
            )

        converted.sort(
            key=lambda bar: bar.start_at
        )

        previous_start: datetime | None = None

        for bar in converted:
            if (
                previous_start is not None
                and bar.start_at
                <= previous_start
            ):
                raise AlpacaStockProviderError(
                    "Alpaca minute bars contain "
                    "duplicate or out-of-order timestamps."
                )

            previous_start = bar.start_at

        return converted
