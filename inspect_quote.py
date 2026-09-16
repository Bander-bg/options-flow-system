from __future__ import annotations

import os
from datetime import date, timedelta

from dotenv import load_dotenv

from alpaca.common.exceptions import APIError
from alpaca.data.enums import OptionsFeed
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest


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


trading_client = TradingClient(
    API_KEY,
    SECRET_KEY,
    paper=True,
)

option_data_client = OptionHistoricalDataClient(
    API_KEY,
    SECRET_KEY,
)


def find_test_contract() -> str:
    today = date.today()
    end_date = today + timedelta(days=45)

    request = GetOptionContractsRequest(
        underlying_symbols=["AAPL"],
        expiration_date_gte=today.isoformat(),
        expiration_date_lte=end_date.isoformat(),
        limit=100,
    )

    response = trading_client.get_option_contracts(request)

    contracts = response.option_contracts

    if not contracts:
        raise RuntimeError(
            "No active AAPL option contracts were returned."
        )

    contract = contracts[0]

    print("Test contract found:")
    print("symbol:", contract.symbol)
    print("expiration:", contract.expiration_date)
    print("tradable:", contract.tradable)
    print("size:", contract.size)
    print()

    return contract.symbol


def test_feed(
    contract_symbol: str,
    feed: OptionsFeed,
) -> bool:
    print("=" * 60)
    print(f"Testing feed: {feed.value.upper()}")
    print("=" * 60)

    request = OptionLatestQuoteRequest(
        symbol_or_symbols=contract_symbol,
        feed=feed,
    )

    try:
        quotes = option_data_client.get_option_latest_quote(
            request
        )

        quote = quotes.get(contract_symbol)

        if quote is None:
            print(
                f"{feed.value.upper()} RESULT: "
                "REQUEST SUCCEEDED BUT NO QUOTE RETURNED"
            )
            return False

        print(
            f"{feed.value.upper()} RESULT: ACCESS OK"
        )
        print("symbol:", contract_symbol)
        print("bid:", quote.bid_price)
        print("ask:", quote.ask_price)
        print("quote_timestamp:", quote.timestamp)

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
    contract_symbol = find_test_contract()

    opra_ok = test_feed(
        contract_symbol,
        OptionsFeed.OPRA,
    )

    print()

    indicative_ok = test_feed(
        contract_symbol,
        OptionsFeed.INDICATIVE,
    )

    print()
    print("=" * 60)
    print("FINAL OPTION FEED RESULT")
    print("=" * 60)

    if opra_ok:
        print("Preferred operational feed: OPRA")
        print(
            "options_feed = OPRA"
        )

    elif indicative_ok:
        print(
            "OPRA unavailable. "
            "Technical/Paper fallback available."
        )
        print(
            "options_feed = INDICATIVE"
        )

    else:
        print(
            "Neither OPRA nor INDICATIVE "
            "returned a usable quote."
        )


if __name__ == "__main__":
    main()