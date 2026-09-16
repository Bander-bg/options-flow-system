from __future__ import annotations

import os
from datetime import date

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

    try:
        return date.fromisoformat(
            str(value)[:10]
        )
    except ValueError:
        return None


def fetch_screener_rows() -> list[dict]:
    url = (
        "https://api.unusualwhales.com"
        "/api/screener/stocks"
    )

    response = requests.get(
        url,
        headers=UW_HEADERS,
        params={
            "ticker": ",".join(TICKERS),
        },
        timeout=30,
    )

    print(
        "Stock Screener HTTP:",
        response.status_code,
    )

    if response.status_code != 200:
        print(response.text[:1000])
        return []

    payload = response.json()

    data = payload.get("data", [])

    if not isinstance(data, list):
        return []

    return data


def fetch_earnings_history(
    ticker: str,
) -> list[dict]:
    url = (
        "https://api.unusualwhales.com"
        f"/api/earnings/{ticker}"
    )

    response = requests.get(
        url,
        headers=UW_HEADERS,
        timeout=30,
    )

    if response.status_code != 200:
        print(
            f"{ticker} earnings HTTP:",
            response.status_code,
        )
        return []

    payload = response.json()

    data = payload.get("data", [])

    if not isinstance(data, list):
        return []

    return data


def find_nearest_future_report(
    rows: list[dict],
    trading_date_et: date,
):
    candidates = []

    for row in rows:
        report_date = parse_date(
            row.get("report_date")
        )

        if (
            report_date is not None
            and report_date >= trading_date_et
        ):
            candidates.append(
                (report_date, row)
            )

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda item: item[0],
    )


def main():
    clock = alpaca.get_clock()

    trading_date_et = (
        clock.timestamp.date()
    )

    print("=" * 78)
    print(
        "UW NEXT UPCOMING EARNINGS VALIDATION"
    )
    print("=" * 78)

    print(
        "trading_date_et:",
        trading_date_et,
    )

    print()

    screener_rows = (
        fetch_screener_rows()
    )

    screener_by_ticker = {
        row.get("ticker"): row
        for row in screener_rows
        if row.get("ticker")
    }

    print(
        "screener_rows_returned:",
        len(screener_rows),
    )

    print()

    matched = 0
    mismatched = 0
    unavailable = 0

    for ticker in TICKERS:
        print("-" * 78)
        print("Ticker:", ticker)
        print("-" * 78)

        screener_row = (
            screener_by_ticker.get(
                ticker
            )
        )

        if screener_row is None:
            print(
                "Screener row: NOT FOUND"
            )
            unavailable += 1
            print()
            continue

        next_earnings_date = (
            parse_date(
                screener_row.get(
                    "next_earnings_date"
                )
            )
        )

        er_time = (
            screener_row.get(
                "er_time"
            )
        )

        print(
            "screener_next_earnings_date:",
            next_earnings_date,
        )

        print(
            "screener_er_time:",
            er_time,
        )

        history_rows = (
            fetch_earnings_history(
                ticker
            )
        )

        future = (
            find_nearest_future_report(
                history_rows,
                trading_date_et,
            )
        )

        if future is None:
            print(
                "nearest_future_report_date:",
                None,
            )

            print(
                "historical_endpoint_source:",
                None,
            )

        else:
            report_date, report_row = (
                future
            )

            print(
                "nearest_future_report_date:",
                report_date,
            )

            print(
                "historical_endpoint_source:",
                report_row.get(
                    "source"
                ),
            )

            print(
                "historical_report_time:",
                report_row.get(
                    "report_time"
                ),
            )

        if next_earnings_date is None:
            print(
                "RESULT: FAIL - "
                "next_earnings_date unavailable"
            )

            unavailable += 1

        elif future is None:
            print(
                "RESULT: PASS WITH "
                "SCREENER ONLY"
            )

            print(
                "Explicit next scheduled "
                "earnings date is available."
            )

            matched += 1

        else:
            report_date, _ = future

            if (
                next_earnings_date
                == report_date
            ):
                print(
                    "RESULT: PASS - "
                    "dates match"
                )

                matched += 1

            else:
                print(
                    "RESULT: MISMATCH"
                )

                print(
                    "Use screener "
                    "next_earnings_date as "
                    "authoritative weekly_v1 "
                    "field, not inferred "
                    "historical report_date."
                )

                mismatched += 1

        print()

    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)

    print(
        "matched_or_verified:",
        matched,
    )

    print(
        "mismatched:",
        mismatched,
    )

    print(
        "unavailable:",
        unavailable,
    )

    print()

    if (
        matched == len(TICKERS)
        and mismatched == 0
        and unavailable == 0
    ):
        print(
            "Next upcoming earnings source: PASS"
        )

        print(
            "Primary weekly_v1 source:"
        )

        print(
            "UW Stock Screener -> "
            "next_earnings_date"
        )

    else:
        print(
            "Next upcoming earnings source: "
            "CHECK REQUIRED"
        )


if __name__ == "__main__":
    main()