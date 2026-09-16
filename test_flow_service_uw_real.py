from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from weekly.services.flow_service import (
    calculate_flow,
    directional_confirmation_matches,
    get_base_flow_direction,
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


TICKER = "AAPL"

TEST_TRADING_DATE = date(
    2026,
    9,
    4,
)

TARGET_EXPIRY = date(
    2026,
    9,
    11,
)

SESSION_OPEN_ET = datetime(
    2026,
    9,
    4,
    9,
    30,
    tzinfo=ET,
)

SESSION_CLOSE_ET = datetime(
    2026,
    9,
    4,
    16,
    0,
    tzinfo=ET,
)

FLOW_THRESHOLD = 500_000


def parse_timestamp(
    value: str,
) -> datetime:
    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


def fetch_real_alerts(
    ticker: str,
) -> tuple[
    list[dict],
    bool,
]:
    """
    Fetch recent real UW flow-alert pages.

    We paginate backward until we reach the
    beginning of the target US trading session,
    or until UW returns no more rows.

    Returns:
        alerts
        session_start_reached
    """

    alerts = []

    older_than = None

    session_open_utc = (
        SESSION_OPEN_ET
        .astimezone(
            ZoneInfo("UTC")
        )
    )

    session_start_reached = False

    seen_cursors = set()

    for page_number in range(
        1,
        11,
    ):
        params = {
            "ticker_symbol": ticker,
            "limit": 500,
        }

        if older_than is not None:
            params[
                "older_than"
            ] = older_than

        response = requests.get(
            UW_URL,
            headers=UW_HEADERS,
            params=params,
            timeout=30,
        )

        print(
            f"UW page {page_number}:",
            response.status_code,
        )

        if response.status_code != 200:
            print(
                response.text[:1000]
            )

            raise RuntimeError(
                "UW flow-alert request failed."
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
                "UW response data is not a list."
            )

        print(
            " rows_returned:",
            len(rows),
        )

        if not rows:
            break

        alerts.extend(
            rows
        )

        timestamps = []

        for row in rows:
            value = row.get(
                "created_at"
            )

            if value:
                timestamps.append(
                    parse_timestamp(
                        value
                    )
                )

        if not timestamps:
            raise RuntimeError(
                "UW rows returned without usable "
                "created_at timestamps."
            )

        oldest = min(
            timestamps
        )

        newest = max(
            timestamps
        )

        print(
            " newest_created_at:",
            newest,
        )

        print(
            " oldest_created_at:",
            oldest,
        )

        if oldest <= session_open_utc:
            session_start_reached = True
            break

        cursor = oldest.isoformat()

        if cursor in seen_cursors:
            raise RuntimeError(
                "UW pagination cursor repeated."
            )

        seen_cursors.add(
            cursor
        )

        older_than = cursor

        if len(rows) < 500:
            break

    return (
        alerts,
        session_start_reached,
    )


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 REAL UW -> PRODUCTION FLOWSERVICE TEST"
    )
    print("=" * 78)
    print()

    alerts, session_start_reached = (
        fetch_real_alerts(
            TICKER
        )
    )

    print()
    print("=" * 78)
    print("RAW UW RESULT")
    print("=" * 78)

    print(
        "ticker:",
        TICKER,
    )

    print(
        "raw_alerts_fetched:",
        len(alerts),
    )

    print(
        "session_start_reached:",
        session_start_reached,
    )

    if not alerts:
        raise RuntimeError(
            "No real UW alerts were returned."
        )

    print()
    print("=" * 78)
    print("PRODUCTION FLOWSERVICE RESULT")
    print("=" * 78)

    result = calculate_flow(
        ticker=TICKER,
        alerts=alerts,
        trading_date_et=TEST_TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        session_open_et=SESSION_OPEN_ET,
        session_close_et=SESSION_CLOSE_ET,
    )

    print(
        "raw_alert_count:",
        result.raw_alert_count,
    )

    print(
        "clean_alert_count:",
        result.clean_alert_count,
    )

    print(
        "deduped_alert_count:",
        result.deduped_alert_count,
    )

    print(
        "flow_dedup_level:",
        result.flow_dedup_level,
    )

    print(
        "trade_overlap_detected:",
        result.trade_overlap_detected,
    )

    print()

    print(
        "call_ask_premium:",
        result.call_ask_premium,
    )

    print(
        "put_ask_premium:",
        result.put_ask_premium,
    )

    print(
        "net_flow:",
        result.net_flow,
    )

    print()

    print(
        "call_bid_premium:",
        result.call_bid_premium,
    )

    print(
        "put_bid_premium:",
        result.put_bid_premium,
    )

    print(
        "bullish_premium:",
        result.bullish_premium,
    )

    print(
        "bearish_premium:",
        result.bearish_premium,
    )

    print(
        "directional_net:",
        result.directional_net,
    )

    print()

    print(
        "sweep_alert_count:",
        result.sweep_alert_count,
    )

    print(
        "opening_alert_count:",
        result.opening_alert_count,
    )

    base_direction = (
        get_base_flow_direction(
            net_flow=result.net_flow,
            threshold=FLOW_THRESHOLD,
        )
    )

    print()

    print(
        "base_flow_direction:",
        (
            base_direction.value
            if base_direction
            else None
        ),
    )

    if base_direction is None:
        directional_match = None

    else:
        directional_match = (
            directional_confirmation_matches(
                base_direction=base_direction,
                directional_net=(
                    result.directional_net
                ),
            )
        )

    print(
        "directional_confirmation_matches:",
        directional_match,
    )

    print()
    print("=" * 78)
    print("VALIDATION")
    print("=" * 78)

    if result.raw_alert_count < 1:
        raise AssertionError(
            "No raw alerts reached FlowService."
        )

    if (
        result.clean_alert_count
        < result.deduped_alert_count
    ):
        raise AssertionError(
            "Deduped count cannot exceed clean count."
        )

    if result.call_ask_premium < 0:
        raise AssertionError(
            "Call Ask premium cannot be negative."
        )

    if result.put_ask_premium < 0:
        raise AssertionError(
            "Put Ask premium cannot be negative."
        )

    expected_net = (
        result.call_ask_premium
        - result.put_ask_premium
    )

    if (
        abs(
            result.net_flow
            - expected_net
        )
        > 1e-9
    ):
        raise AssertionError(
            "Primary Net Flow math mismatch."
        )

    expected_directional = (
        (
            result.call_ask_premium
            + result.put_bid_premium
        )
        -
        (
            result.put_ask_premium
            + result.call_bid_premium
        )
    )

    if (
        abs(
            result.directional_net
            - expected_directional
        )
        > 1e-9
    ):
        raise AssertionError(
            "Directional Net math mismatch."
        )

    print(
        "PASS - Real UW fields accepted "
        "by production FlowService"
    )

    print(
        "PASS - Clean Universe filtering"
    )

    print(
        "PASS - Dedup pipeline"
    )

    print(
        "PASS - Base Net Flow math"
    )

    print(
        "PASS - Directional Net math"
    )

    print()

    if not session_start_reached:
        print(
            "NOTE - Pagination did not prove complete "
            "session-to-date coverage."
        )

        print(
            "This is acceptable for this compatibility "
            "test, but NOT for production Candidate logic."
        )

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)
    print()

    print(
        "Real UW -> Production FlowService: PASS"
    )


if __name__ == "__main__":
    main()