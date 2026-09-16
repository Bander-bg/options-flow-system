from __future__ import annotations

import os
from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from weekly.services.flow_service import (
    clean_flow_alerts,
)


load_dotenv()


ET = ZoneInfo("America/New_York")

UW_API_KEY = os.getenv("UW_API_KEY")

if not UW_API_KEY:
    raise RuntimeError(
        "UW_API_KEY was not found in .env"
    )


UW_URL = (
    "https://api.unusualwhales.com"
    "/api/option-trades/flow-alerts"
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


TRADING_DATE = date(
    2026,
    9,
    4,
)

TARGET_EXPIRY = date(
    2026,
    9,
    11,
)

SESSION_OPEN = datetime(
    2026,
    9,
    4,
    9,
    30,
    tzinfo=ET,
)

SESSION_CLOSE = datetime(
    2026,
    9,
    4,
    16,
    0,
    tzinfo=ET,
)


def fetch_alerts(
    ticker: str,
) -> list[dict]:

    response = requests.get(
        UW_URL,
        headers=UW_HEADERS,
        params={
            "ticker_symbol": ticker,
            "limit": 500,
        },
        timeout=30,
    )

    print(
        ticker,
        "HTTP:",
        response.status_code,
    )

    if response.status_code != 200:
        raise RuntimeError(
            response.text[:1000]
        )

    payload = response.json()

    rows = payload.get(
        "data",
        [],
    )

    if not isinstance(
        rows,
        list,
    ):
        raise RuntimeError(
            "UW data is not a list."
        )

    return rows


def composite_key(
    alert: dict,
):
    return (
        alert.get("created_at"),
        alert.get("option_chain"),
        alert.get("alert_rule"),
    )


def main():
    print("=" * 78)
    print(
        "REAL UW FLOW DEDUP / UUID VALIDATION"
    )
    print("=" * 78)
    print()

    total_clean = 0
    total_with_id = 0
    total_with_trade_ids = 0

    for ticker in TICKERS:

        print("-" * 78)
        print("Ticker:", ticker)
        print("-" * 78)

        raw = fetch_alerts(
            ticker
        )

        (
            clean,
            deduped,
            dedup_level,
            overlap,
        ) = clean_flow_alerts(
            alerts=raw,
            trading_date_et=TRADING_DATE,
            target_expiry=TARGET_EXPIRY,
            session_open_et=SESSION_OPEN,
            session_close_et=SESSION_CLOSE,
        )

        ids = [
            str(
                row.get(
                    "id",
                    "",
                )
            ).strip()
            for row in clean
        ]

        nonempty_ids = [
            value
            for value in ids
            if value
        ]

        trade_id_rows = [
            row
            for row in clean
            if row.get(
                "trade_ids"
            )
        ]

        duplicate_ids = [
            value
            for value, count
            in Counter(
                nonempty_ids
            ).items()
            if count > 1
        ]

        composites = [
            composite_key(row)
            for row in clean
        ]

        duplicate_composites = [
            value
            for value, count
            in Counter(
                composites
            ).items()
            if count > 1
        ]

        print(
            "raw:",
            len(raw),
        )

        print(
            "clean_before_dedup:",
            len(clean),
        )

        print(
            "deduped:",
            len(deduped),
        )

        print(
            "selected_dedup_level:",
            dedup_level,
        )

        print(
            "clean_rows_with_id:",
            len(nonempty_ids),
            "/",
            len(clean),
        )

        print(
            "duplicate_nonempty_ids:",
            len(duplicate_ids),
        )

        print(
            "clean_rows_with_trade_ids:",
            len(trade_id_rows),
        )

        print(
            "trade_overlap_detected:",
            overlap,
        )

        print(
            "duplicate_composite_keys:",
            len(duplicate_composites),
        )

        if nonempty_ids:
            print(
                "sample_id:",
                nonempty_ids[0],
            )

        total_clean += len(
            clean
        )

        total_with_id += len(
            nonempty_ids
        )

        total_with_trade_ids += len(
            trade_id_rows
        )

        print()

    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)

    print(
        "total_clean_rows:",
        total_clean,
    )

    print(
        "total_clean_rows_with_id:",
        total_with_id,
    )

    print(
        "total_clean_rows_with_trade_ids:",
        total_with_trade_ids,
    )

    print()

    if (
        total_clean > 0
        and total_with_id == total_clean
        and total_with_trade_ids == 0
    ):
        print(
            "Current real UW Clean Universe "
            "supports alert_uuid dedup."
        )

        print(
            "Trade-level dedup is currently "
            "not available from these rows."
        )

    elif (
        total_with_trade_ids > 0
    ):
        print(
            "Trade IDs are now present."
        )

        print(
            "Trade-level / overlap path "
            "requires review before provider lock."
        )

    else:
        print(
            "UUID coverage is incomplete."
        )

        print(
            "Composite fallback remains required."
        )


if __name__ == "__main__":
    main()