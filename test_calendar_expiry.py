from __future__ import annotations

import os
from datetime import timedelta

from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetStatus
from alpaca.trading.requests import (
    GetCalendarRequest,
    GetOptionContractsRequest,
)


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


client = TradingClient(
    API_KEY,
    SECRET_KEY,
    paper=True,
)


TICKERS = [
    "AAPL",
    "TSLA",
    "NVDA",
    "GOOGL",
    "META",
]

MIN_SESSIONS = 3
MAX_SESSIONS = 7


def fetch_calendar(
    start_date,
    end_date,
):
    request = GetCalendarRequest(
        start=start_date,
        end=end_date,
    )

    return client.get_calendar(request)


def fetch_available_expiries(
    ticker: str,
    start_date,
    end_date,
):
    expiries = set()
    page_token = None

    while True:
        request = GetOptionContractsRequest(
            underlying_symbols=[ticker],
            status=AssetStatus.ACTIVE,
            expiration_date_gte=start_date,
            expiration_date_lte=end_date,
            limit=1000,
            page_token=page_token,
        )

        response = client.get_option_contracts(
            request
        )

        contracts = response.option_contracts or []

        for contract in contracts:
            expiries.add(
                contract.expiration_date
            )

        page_token = response.next_page_token

        if not page_token:
            break

    return sorted(expiries)


def count_remaining_future_sessions(
    trading_date_et,
    expiry,
    calendar,
) -> int:
    """
    Current trading_date_et is excluded.
    Expiry session itself is included.
    """
    return sum(
        1
        for session in calendar
        if trading_date_et < session.date <= expiry
    )


def select_target_expiry(
    trading_date_et,
    expiries,
    calendar,
):
    evaluations = []

    for expiry in expiries:

        # Methodology rule:
        # exclude expiry equal to current trading date.
        if expiry == trading_date_et:
            continue

        if expiry < trading_date_et:
            continue

        remaining_sessions = (
            count_remaining_future_sessions(
                trading_date_et,
                expiry,
                calendar,
            )
        )

        eligible = (
            MIN_SESSIONS
            <= remaining_sessions
            <= MAX_SESSIONS
        )

        evaluations.append(
            {
                "expiry": expiry,
                "remaining_sessions": (
                    remaining_sessions
                ),
                "eligible": eligible,
            }
        )

    eligible_expiries = [
        item
        for item in evaluations
        if item["eligible"]
    ]

    if not eligible_expiries:
        return None, evaluations

    # Expiries are real listed dates from Alpaca.
    # Choose nearest eligible expiry.
    target = min(
        eligible_expiries,
        key=lambda item: item["expiry"],
    )

    return target, evaluations


def main() -> None:

    print("=" * 78)
    print("ALPACA CALENDAR + TARGET EXPIRY TEST")
    print("=" * 78)

    # Important:
    # Use Alpaca market clock instead of local computer date.
    # This prevents Riyadh/ET date mismatch.
    clock = client.get_clock()

    market_timestamp = clock.timestamp
    trading_date_et = market_timestamp.date()

    print("alpaca_market_timestamp:", market_timestamp)
    print("trading_date_et:", trading_date_et)
    print("market_is_open:", clock.is_open)
    print("next_open:", clock.next_open)
    print("next_close:", clock.next_close)

    print()

    # Wide enough range for finding listed expiries
    # and counting 3-7 future sessions.
    search_end = trading_date_et + timedelta(
        days=30
    )

    calendar = fetch_calendar(
        trading_date_et,
        search_end,
    )

    print("=" * 78)
    print("CALENDAR SAMPLE")
    print("=" * 78)

    for session in calendar[:12]:
        print(
            session.date,
            "| open:",
            session.open,
            "| close:",
            session.close,
        )

    print()
    print(
        "calendar_sessions_returned:",
        len(calendar),
    )

    print()
    print("=" * 78)
    print("TARGET EXPIRY TEST BY TICKER")
    print("=" * 78)

    final_results = {}

    for ticker in TICKERS:

        expiries = fetch_available_expiries(
            ticker,
            trading_date_et,
            search_end,
        )

        target, evaluations = (
            select_target_expiry(
                trading_date_et,
                expiries,
                calendar,
            )
        )

        print()
        print("-" * 78)
        print("Ticker:", ticker)
        print("-" * 78)

        print(
            "listed_expiries:",
            [
                str(expiry)
                for expiry in expiries
            ],
        )

        print()

        for item in evaluations:
            label = (
                "ELIGIBLE"
                if item["eligible"]
                else "REJECT"
            )

            print(
                item["expiry"],
                "| remaining_future_trading_sessions =",
                item["remaining_sessions"],
                "|",
                label,
            )

        print()

        if target is None:
            print(
                "TARGET EXPIRY: NONE"
            )

            final_results[ticker] = None

        else:
            print(
                "TARGET EXPIRY:",
                target["expiry"],
            )

            print(
                "TARGET REMAINING SESSIONS:",
                target["remaining_sessions"],
            )

            final_results[ticker] = (
                target["expiry"]
            )

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)

    for ticker, target in final_results.items():
        print(
            f"{ticker}: {target}"
        )

    all_found = all(
        target is not None
        for target in final_results.values()
    )

    if all_found:
        print()
        print(
            "Target-expiry selection: PASS"
        )
        print(
            "All targets came from actual listed "
            "Alpaca contract expirations."
        )
        print(
            "Current trading date was excluded "
            "from session counting."
        )
        print(
            "Expiry session was included."
        )
    else:
        print()
        print(
            "Target-expiry selection: "
            "CHECK REQUIRED"
        )


if __name__ == "__main__":
    main()