from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from weekly.providers.unusual_whales_provider import (
    UnusualWhalesProvider,
)


load_dotenv()


ET = ZoneInfo("America/New_York")


TICKER = "AAPL"

SESSION_OPEN_ET = datetime(
    2026,
    9,
    4,
    9,
    30,
    tzinfo=ET,
)


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 UNUSUAL WHALES PROVIDER + METADATA TEST"
    )
    print("=" * 78)
    print()

    provider = (
        UnusualWhalesProvider()
    )

    batch = (
        provider
        .fetch_session_to_date_flow_alerts(
            ticker=TICKER,
            session_open_et=SESSION_OPEN_ET,
            max_pages=20,
            page_limit=500,
            require_complete=True,
        )
    )

    print(
        "ticker:",
        batch.ticker,
    )

    print(
        "provider:",
        batch.provider,
    )

    print(
        "feed:",
        batch.feed,
    )

    print()

    print(
        "pages_fetched:",
        batch.pages_fetched,
    )

    print(
        "rows_fetched:",
        batch.rows_fetched,
    )

    print()

    print(
        "session_coverage_complete:",
        batch.session_coverage_complete,
    )

    print(
        "session_start_reached:",
        batch.session_start_reached,
    )

    print(
        "history_exhausted:",
        batch.history_exhausted,
    )

    print()

    print(
        "newest_created_at:",
        batch.newest_created_at,
    )

    print(
        "oldest_created_at:",
        batch.oldest_created_at,
    )

    print(
        "source_timestamp:",
        batch.source_timestamp,
    )

    print(
        "fetched_at:",
        batch.fetched_at,
    )

    print(
        "freshness_status:",
        batch.freshness_status,
    )

    print()

    # --------------------------------------------------
    # CORE PROVIDER VALIDATION
    # --------------------------------------------------

    if batch.ticker != TICKER:
        raise AssertionError(
            "Ticker mismatch."
        )

    if batch.provider != (
        "UNUSUAL_WHALES"
    ):
        raise AssertionError(
            "Provider provenance mismatch."
        )

    if batch.feed != (
        "UNKNOWN"
    ):
        raise AssertionError(
            "UW feed must remain UNKNOWN "
            "until a specific feed identity "
            "is actually known."
        )

    if batch.rows_fetched < 1:
        raise AssertionError(
            "No UW rows fetched."
        )

    if batch.pages_fetched < 1:
        raise AssertionError(
            "No UW pages fetched."
        )

    # --------------------------------------------------
    # SESSION COVERAGE
    # --------------------------------------------------

    if not (
        batch.session_coverage_complete
    ):
        raise AssertionError(
            "Session-to-Date coverage "
            "was not proven."
        )

    if not (
        batch.session_start_reached
        or batch.history_exhausted
    ):
        raise AssertionError(
            "Coverage completeness "
            "has no valid proof."
        )

    # --------------------------------------------------
    # TIMESTAMP METADATA
    # --------------------------------------------------

    if (
        batch.newest_created_at
        is None
        or batch.oldest_created_at
        is None
    ):
        raise AssertionError(
            "Source timestamps missing."
        )

    if (
        batch.source_timestamp
        is None
    ):
        raise AssertionError(
            "source_timestamp missing."
        )

    if (
        batch.fetched_at
        is None
    ):
        raise AssertionError(
            "fetched_at missing."
        )

    if (
        batch.newest_created_at
        < batch.oldest_created_at
    ):
        raise AssertionError(
            "Newest timestamp is older "
            "than oldest timestamp."
        )

    if (
        batch.source_timestamp
        != batch.newest_created_at
    ):
        raise AssertionError(
            "source_timestamp must equal "
            "newest source alert timestamp."
        )

    if (
        batch.source_timestamp.tzinfo
        is None
    ):
        raise AssertionError(
            "source_timestamp must be "
            "timezone-aware."
        )

    if (
        batch.fetched_at.tzinfo
        is None
    ):
        raise AssertionError(
            "fetched_at must be "
            "timezone-aware."
        )

    if (
        batch.fetched_at
        < batch.source_timestamp
    ):
        raise AssertionError(
            "fetched_at cannot be earlier "
            "than source_timestamp."
        )

    # --------------------------------------------------
    # FRESHNESS STATUS
    # --------------------------------------------------

    if (
        batch.freshness_status
        != "UNKNOWN"
    ):
        raise AssertionError(
            "Provider must not invent "
            "freshness classification."
        )

    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)
    print()

    print(
        "UnusualWhalesProvider: PASS"
    )

    print(
        "Session-to-Date coverage: PASS"
    )

    print(
        "Provider provenance metadata: PASS"
    )

    print(
        "Source timestamp metadata: PASS"
    )

    print(
        "Fetched-at metadata: PASS"
    )

    print(
        "Freshness remains unresolved "
        "until service-level evaluation: PASS"
    )


if __name__ == "__main__":
    main()