from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from alpaca.common.exceptions import APIError
from alpaca.data.enums import DataFeed

from weekly.providers.alpaca_stock_provider import (
    AlpacaStockProvider,
)


class FakeResponse:
    def __init__(self, ticker: str, bars):
        self.data = {
            ticker: bars,
        }


def make_bar(
    minute: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
):
    return SimpleNamespace(
        timestamp=datetime(
            2026,
            9,
            11,
            14,
            minute,
            tzinfo=timezone.utc,
        ),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        trade_count=10,
        vwap=close,
    )


class FakeIEXClient:
    def __init__(self):
        self.requests = []

    def get_stock_bars(self, request):
        self.requests.append(request)

        # Intentionally unsorted.
        bars = [
            make_bar(
                2,
                open_=102.0,
                high=103.0,
                low=101.5,
                close=102.5,
                volume=1200,
            ),
            make_bar(
                0,
                open_=100.0,
                high=101.0,
                low=99.5,
                close=100.5,
                volume=1000,
            ),
            make_bar(
                1,
                open_=100.5,
                high=102.0,
                low=100.0,
                close=101.5,
                volume=1100,
            ),
        ]

        return FakeResponse(
            "AAPL",
            bars,
        )


class FakeSipFallbackClient:
    def __init__(self):
        self.feeds = []

    def get_stock_bars(self, request):
        self.feeds.append(request.feed)

        if request.feed is DataFeed.SIP:
            raise APIError(
                {
                    "code": 403,
                    "message": (
                        "subscription not permitted"
                    ),
                }
            )

        bars = [
            make_bar(
                0,
                open_=100.0,
                high=101.0,
                low=99.5,
                close=100.5,
                volume=1000,
            ),
        ]

        return FakeResponse(
            "AAPL",
            bars,
        )


def main():
    # --------------------------------------------------
    # 1) IEX / completed-bar conversion
    # --------------------------------------------------

    iex_client = FakeIEXClient()

    provider = AlpacaStockProvider(
        preferred_feed="iex",
        client=iex_client,
    )

    start = datetime(
        2026,
        9,
        11,
        14,
        0,
        tzinfo=timezone.utc,
    )

    # 14:02:30 means:
    # - 14:00 bar completed at 14:01 -> keep
    # - 14:01 bar completed at 14:02 -> keep
    # - 14:02 bar completes at 14:03 -> exclude
    end = datetime(
        2026,
        9,
        11,
        14,
        2,
        30,
        tzinfo=timezone.utc,
    )

    result = provider.get_minute_bars(
        ticker="aapl",
        start=start,
        end=end,
    )

    assert result.ticker == "AAPL"
    assert result.provider == "ALPACA"
    assert result.feed == "iex"

    assert len(result.bars) == 2

    assert (
        result.bars[0].start_at
        < result.bars[1].start_at
    )

    assert (
        result.bars[0].start_at.minute
        == 0
    )

    assert (
        result.bars[1].start_at.minute
        == 1
    )

    assert (
        result.bars[0].end_at.minute
        == 1
    )

    assert (
        result.bars[1].end_at.minute
        == 2
    )

    assert (
        iex_client.requests[0].feed
        is DataFeed.IEX
    )

    # --------------------------------------------------
    # 2) SIP -> IEX fallback
    # --------------------------------------------------

    fallback_client = (
        FakeSipFallbackClient()
    )

    fallback_provider = (
        AlpacaStockProvider(
            preferred_feed="sip",
            client=fallback_client,
        )
    )

    fallback_result = (
        fallback_provider
        .get_minute_bars(
            ticker="AAPL",
            start=start,
            end=datetime(
                2026,
                9,
                11,
                14,
                1,
                tzinfo=timezone.utc,
            ),
        )
    )

    assert fallback_client.feeds == [
        DataFeed.SIP,
        DataFeed.IEX,
    ]

    assert (
        fallback_result.feed
        == "iex"
    )

    assert (
        len(fallback_result.bars)
        == 1
    )

    print(
        "1. IEX request feed: PASS"
    )

    print(
        "2. ticker normalization: PASS"
    )

    print(
        "3. 1-minute bar conversion: PASS"
    )

    print(
        "4. completed-bars-only filter: PASS"
    )

    print(
        "5. chronological sorting: PASS"
    )

    print(
        "6. SIP -> IEX entitlement fallback: PASS"
    )

    print(
        "7. actual feed provenance: PASS"
    )

    print()
    print("=" * 70)

    print(
        "ALPACA STOCK PROVIDER: PASS 7/7"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
