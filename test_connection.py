from __future__ import annotations

import os

from dotenv import load_dotenv

from alpaca.common.exceptions import APIError
from alpaca.data.enums import DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest


load_dotenv()


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


client = StockHistoricalDataClient(
    API_KEY,
    SECRET_KEY,
)


def test_feed(feed: DataFeed) -> bool:
    print("=" * 60)
    print(f"Testing stock feed: {feed.value.upper()}")
    print("=" * 60)

    request = StockLatestQuoteRequest(
        symbol_or_symbols="AAPL",
        feed=feed,
    )

    try:
        quotes = client.get_stock_latest_quote(request)

        quote = quotes.get("AAPL")

        if quote is None:
            print(
                f"{feed.value.upper()} RESULT: "
                "REQUEST SUCCEEDED BUT NO QUOTE RETURNED"
            )
            return False

        print(
            f"{feed.value.upper()} RESULT: ACCESS OK"
        )

        print("symbol: AAPL")
        print("bid:", quote.bid_price)
        print("ask:", quote.ask_price)
        print("timestamp:", quote.timestamp)

        return True

    except APIError as exc:
        print(
            f"{feed.value.upper()} RESULT: ACCESS FAILED"
        )
        print("HTTP status:", exc.status_code)
        print("message:", exc.message)

        return False

    except Exception as exc:
        print(
            f"{feed.value.upper()} RESULT: ERROR"
        )
        print(
            f"{type(exc).__name__}: {exc}"
        )

        return False


def main() -> None:
    sip_ok = test_feed(DataFeed.SIP)

    print()

    iex_ok = test_feed(DataFeed.IEX)

    print()
    print("=" * 60)
    print("FINAL STOCK FEED RESULT")
    print("=" * 60)

    if sip_ok:
        print("Preferred operational stock feed: SIP")
        print("stock_data_provider = ALPACA")
        print("stock_data_feed = SIP")

    elif iex_ok:
        print(
            "SIP unavailable. "
            "IEX Paper/technical fallback available."
        )
        print("stock_data_provider = ALPACA")
        print("stock_data_feed = IEX")

    else:
        print(
            "Neither SIP nor IEX returned "
            "a usable stock quote."
        )


if __name__ == "__main__":
    main()