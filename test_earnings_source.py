from __future__ import annotations

import os
from datetime import date, datetime

import requests
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient


load_dotenv()


def get_env_value(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


ALPACA_API_KEY = get_env_value(
    "ALPACA_API_KEY",
    "ALPACA_KEY",
    "APCA_API_KEY_ID",
)

ALPACA_SECRET_KEY = get_env_value(
    "ALPACA_SECRET_KEY",
    "ALPACA_SECRET",
    "APCA_API_SECRET_KEY",
)

UW_API_KEY = os.getenv("UW_API_KEY")


if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
    raise RuntimeError(
        "Alpaca API credentials were not found in .env"
    )

if not UW_API_KEY:
    raise RuntimeError(
        "UW_API_KEY was not found in .env"
    )


alpaca = TradingClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    paper=True,
)


UW_HEADERS = {
    "Authorization": f"Bearer {UW_API_KEY}",
    "Accept": "application/json",
}


TICKERS = [
    "AAPL",
    "TSLA",
    "NVDA",
    "GOOGL",
    "META",
]


def parse_date(value) -> date | None:
    if not value:
        return None

    text = str(value).strip()

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        ).date()
    except ValueError:
        return None


def fetch_earnings(ticker: str):
    url = (
        "https://api.unusualwhales.com"
        f"/api/earnings/{ticker}"
    )

    response = requests.get(
        url,
        headers=UW_HEADERS,
        timeout=30,
    )

    print(
        f"{ticker} HTTP:",
        response.status_code,
    )

    if response.status_code != 200:
        print(response.text[:500])
        return []

    payload = response.json()

    data = payload.get("data", [])

    if not isinstance(data, list):
        print(
            "Unexpected data type:",
            type(data).__name__,
        )
        return []

    return data


def extract_event_date(row: dict) -> date | None:
    candidate_fields = [
        "next_earnings_date",
        "report_date",
        "earnings_date",
        "trading_day",
        "date",
    ]

    for field in candidate_fields:
        parsed = parse_date(
            row.get(field)
        )

        if parsed is not None:
            return parsed

    return None


def main():
    clock = alpaca.get_clock()

    trading_date_et = (
        clock.timestamp.date()
    )

    print("=" * 78)
    print("UW EARNINGS SOURCE DIAGNOSTIC")
    print("=" * 78)

    print(
        "trading_date_et:",
        trading_date_et,
    )

    print()

    future_found_count = 0

    for ticker in TICKERS:
        print("-" * 78)
        print("Ticker:", ticker)
        print("-" * 78)

        rows = fetch_earnings(
            ticker
        )

        print(
            "rows_returned:",
            len(rows),
        )

        if not rows:
            print(
                "No earnings rows returned."
            )
            print()
            continue

        print(
            "fields_in_first_row:",
            sorted(rows[0].keys()),
        )

        dated_rows = []

        for row in rows:
            event_date = extract_event_date(
                row
            )

            if event_date is not None:
                dated_rows.append(
                    (event_date, row)
                )

        dated_rows.sort(
            key=lambda item: item[0]
        )

        historical = [
            item
            for item in dated_rows
            if item[0] < trading_date_et
        ]

        current_or_future = [
            item
            for item in dated_rows
            if item[0] >= trading_date_et
        ]

        print(
            "dated_rows:",
            len(dated_rows),
        )

        print(
            "historical_rows:",
            len(historical),
        )

        print(
            "current_or_future_rows:",
            len(current_or_future),
        )

        if historical:
            print(
                "latest_historical_date:",
                historical[-1][0],
            )

        if current_or_future:
            future_found_count += 1

            next_event_date, next_row = (
                current_or_future[0]
            )

            print(
                "NEXT CURRENT/FUTURE EVENT:",
                next_event_date,
            )

            print(
                "event_type:",
                next_row.get("type"),
            )

            print(
                "event_time:",
                next_row.get("report_time"),
            )

            print(
                "source:",
                next_row.get("source"),
            )

            print(
                "row:",
                next_row,
            )

        else:
            print(
                "NO CURRENT/FUTURE EARNINGS "
                "FOUND IN THIS REST RESPONSE"
            )

        print()

    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)

    print(
        "tickers_with_future_event:",
        future_found_count,
        "/",
        len(TICKERS),
    )

    if future_found_count == len(TICKERS):
        print(
            "REST appears capable of supplying "
            "a future earnings event for all tickers."
        )

        print(
            "Next step: validate that the chosen row "
            "is explicitly the NEXT UPCOMING earnings."
        )

    else:
        print(
            "This REST endpoint cannot yet be accepted "
            "as the weekly_v1 next-upcoming earnings source."
        )

        print(
            "Do NOT substitute the latest historical "
            "earnings date."
        )


if __name__ == "__main__":
    main()