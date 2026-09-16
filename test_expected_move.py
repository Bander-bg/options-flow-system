from __future__ import annotations

import os
from datetime import date, timedelta

import requests
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


TICKERS = [
    "AAPL",
    "TSLA",
    "NVDA",
    "GOOGL",
    "META",
]

MIN_SESSIONS = 3
MAX_SESSIONS = 7


UW_HEADERS = {
    "Authorization": f"Bearer {UW_API_KEY}",
    "Accept": "application/json",
}


def fetch_calendar(start_date, end_date):
    request = GetCalendarRequest(
        start=start_date,
        end=end_date,
    )

    return alpaca.get_calendar(request)


def fetch_expiries(
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

        response = alpaca.get_option_contracts(
            request
        )

        for contract in (
            response.option_contracts or []
        ):
            expiries.add(
                contract.expiration_date
            )

        page_token = response.next_page_token

        if not page_token:
            break

    return sorted(expiries)


def count_future_sessions(
    trading_date_et,
    expiry,
    calendar,
):
    return sum(
        1
        for session in calendar
        if trading_date_et < session.date <= expiry
    )


def choose_target_expiry(
    trading_date_et,
    expiries,
    calendar,
):
    eligible = []

    for expiry in expiries:

        if expiry <= trading_date_et:
            continue

        sessions = count_future_sessions(
            trading_date_et,
            expiry,
            calendar,
        )

        if MIN_SESSIONS <= sessions <= MAX_SESSIONS:
            eligible.append(
                (expiry, sessions)
            )

    if not eligible:
        return None

    return min(
        eligible,
        key=lambda item: item[0],
    )


def fetch_uw_term_structure(
    ticker: str,
):
    url = (
        "https://api.unusualwhales.com"
        f"/api/stock/{ticker}"
        "/volatility/term-structure"
    )

    response = requests.get(
        url,
        headers=UW_HEADERS,
        timeout=30,
    )

    print(
        f"{ticker} UW HTTP:",
        response.status_code,
    )

    if response.status_code != 200:
        print(
            response.text[:500]
        )
        return []

    payload = response.json()

    data = payload.get("data", [])

    if not isinstance(data, list):
        return []

    return data


def find_exact_expiry_row(
    rows: list[dict],
    target_expiry: date,
):
    target_text = target_expiry.isoformat()

    for row in rows:
        if row.get("expiry") == target_text:
            return row

    return None


def main():
    clock = alpaca.get_clock()

    trading_date_et = (
        clock.timestamp.date()
    )

    search_end = (
        trading_date_et
        + timedelta(days=30)
    )

    calendar = fetch_calendar(
        trading_date_et,
        search_end,
    )

    print("=" * 78)
    print(
        "UW EXACT TARGET-EXPIRY EXPECTED MOVE TEST"
    )
    print("=" * 78)

    print(
        "trading_date_et:",
        trading_date_et,
    )

    print()

    passed = 0
    failed = 0

    for ticker in TICKERS:

        print("-" * 78)
        print("Ticker:", ticker)
        print("-" * 78)

        expiries = fetch_expiries(
            ticker,
            trading_date_et,
            search_end,
        )

        target = choose_target_expiry(
            trading_date_et,
            expiries,
            calendar,
        )

        if target is None:
            print(
                "Target expiry: NOT FOUND"
            )
            failed += 1
            print()
            continue

        target_expiry, sessions = target

        print(
            "target_expiry:",
            target_expiry,
        )

        print(
            "remaining_future_sessions:",
            sessions,
        )

        rows = fetch_uw_term_structure(
            ticker
        )

        print(
            "term_structure_rows:",
            len(rows),
        )

        row = find_exact_expiry_row(
            rows,
            target_expiry,
        )

        if row is None:

            print(
                "exact_target_expiry_row: NOT FOUND"
            )

            print(
                "Expected Move source: "
                "FALLBACK REQUIRED"
            )

            failed += 1
            print()
            continue

        print(
            "exact_target_expiry_row: FOUND"
        )

        print(
            "UW date:",
            row.get("date"),
        )

        print(
            "UW expiry:",
            row.get("expiry"),
        )

        print(
            "UW dte:",
            row.get("dte"),
        )

        print(
            "ATM volatility:",
            row.get("volatility"),
        )

        print(
            "implied_move:",
            row.get("implied_move"),
        )

        print(
            "implied_move_perc:",
            row.get("implied_move_perc"),
        )

        try:
            implied_move = float(
                row.get("implied_move")
            )

            volatility = float(
                row.get("volatility")
            )

            implied_move_perc = float(
                row.get("implied_move_perc")
            )

            numeric_valid = (
                implied_move > 0
                and volatility > 0
                and implied_move_perc > 0
            )

        except (
            TypeError,
            ValueError,
        ):
            numeric_valid = False

        if numeric_valid:

            print(
                "Expected Move exact-expiry: PASS"
            )

            passed += 1

        else:
            print(
                "Expected Move exact-expiry: FAIL "
                "(invalid numeric values)"
            )

            failed += 1

        print()

    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)

    print(
        "passed:",
        passed,
    )

    print(
        "failed:",
        failed,
    )

    if passed == len(TICKERS):
        print()
        print(
            "Exact target-expiry "
            "IvTermStructure.implied_move: PASS"
        )

        print(
            "Primary Expected Move source is "
            "available for all current tickers."
        )

    else:
        print()
        print(
            "At least one ticker requires "
            "the ATM-IV fallback path."
        )


if __name__ == "__main__":
    main()