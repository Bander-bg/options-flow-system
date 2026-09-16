from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.flow_snapshot_repository as repo_module

from weekly.db.flow_snapshot_repository import (
    FlowSnapshotRepository,
)
from weekly.domain.models import (
    FlowSnapshot,
)


ROOT = Path(__file__).resolve().parent

PRODUCTION_DB = (
    ROOT
    / "weekly_trading.db"
)

TEST_DB = (
    ROOT
    / "weekly_flow_snapshot_repository_v2_test.db"
)

ET = ZoneInfo(
    "America/New_York"
)

UTC = ZoneInfo(
    "UTC"
)


def clone_database():
    if TEST_DB.exists():
        TEST_DB.unlink()

    source = sqlite3.connect(
        PRODUCTION_DB
    )

    target = sqlite3.connect(
        TEST_DB
    )

    source.backup(
        target
    )

    source.close()
    target.close()


def configure_connection(
    connection: sqlite3.Connection,
):
    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        "PRAGMA busy_timeout = 5000"
    )


@contextmanager
def test_database_connection():
    connection = sqlite3.connect(
        TEST_DB,
        timeout=5,
    )

    configure_connection(
        connection
    )

    try:
        yield connection

    finally:
        connection.close()


@contextmanager
def test_database_transaction():
    connection = sqlite3.connect(
        TEST_DB,
        timeout=5,
    )

    configure_connection(
        connection
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        yield connection

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def patch_repository_database():
    repo_module.database_connection = (
        test_database_connection
    )

    repo_module.database_transaction = (
        test_database_transaction
    )


def make_snapshot(
    *,
    captured_at: datetime,
    net_flow: float = 2_804_768.0,
) -> FlowSnapshot:
    return FlowSnapshot(
        ticker="AAPL",

        trading_date_et=date(
            2026,
            9,
            4,
        ),

        captured_at=captured_at,

        target_expiry=date(
            2026,
            9,
            11,
        ),

        call_ask_premium=(
            2_900_998.0
        ),

        put_ask_premium=(
            96_230.0
        ),

        net_flow=(
            net_flow
        ),

        call_bid_premium=(
            1_283_438.0
        ),

        put_bid_premium=(
            79_780.0
        ),

        bullish_premium=(
            2_980_778.0
        ),

        bearish_premium=(
            1_379_668.0
        ),

        directional_net=(
            1_601_110.0
        ),

        raw_alert_count=500,

        clean_alert_count=10,

        deduped_alert_count=10,

        flow_dedup_level=(
            "alert_uuid"
        ),

        trade_overlap_detected=False,

        sweep_alert_count=0,

        opening_alert_count=0,

        provider=(
            "UNUSUAL_WHALES"
        ),

        feed="UNKNOWN",

        source_timestamp=datetime(
            2026,
            9,
            4,
            19,
            59,
            41,
            tzinfo=UTC,
        ),

        fetched_at=datetime(
            2026,
            9,
            6,
            5,
            30,
            0,
            tzinfo=UTC,
        ),

        freshness_status="UNKNOWN",

        total_premium=4_000_000.0,
        sweep_premium=1_200_000.0,
    )


def assert_equal(
    actual,
    expected,
    name: str,
):
    if actual != expected:
        raise AssertionError(
            f"{name}: expected "
            f"{expected!r}, got {actual!r}"
        )


def test_create_and_roundtrip(
    repository: FlowSnapshotRepository,
):
    snapshot = make_snapshot(
        captured_at=datetime(
            2026,
            9,
            4,
            15,
            0,
            tzinfo=ET,
        )
    )

    created = repository.create(
        snapshot
    )

    if created.id is None:
        raise AssertionError(
            "Created snapshot has no id."
        )

    loaded = repository.get_by_id(
        created.id
    )

    if loaded is None:
        raise AssertionError(
            "Snapshot could not be read."
        )

    assert_equal(
        loaded.ticker,
        "AAPL",
        "ticker",
    )

    assert_equal(
        loaded.trading_date_et,
        date(
            2026,
            9,
            4,
        ),
        "trading_date_et",
    )

    assert_equal(
        loaded.target_expiry,
        date(
            2026,
            9,
            11,
        ),
        "target_expiry",
    )

    assert_equal(
        loaded.call_ask_premium,
        2_900_998.0,
        "call_ask_premium",
    )

    assert_equal(
        loaded.put_ask_premium,
        96_230.0,
        "put_ask_premium",
    )

    assert_equal(
        loaded.net_flow,
        2_804_768.0,
        "net_flow",
    )

    assert_equal(
        loaded.call_bid_premium,
        1_283_438.0,
        "call_bid_premium",
    )

    assert_equal(
        loaded.put_bid_premium,
        79_780.0,
        "put_bid_premium",
    )

    assert_equal(
        loaded.bullish_premium,
        2_980_778.0,
        "bullish_premium",
    )

    assert_equal(
        loaded.bearish_premium,
        1_379_668.0,
        "bearish_premium",
    )

    assert_equal(
        loaded.directional_net,
        1_601_110.0,
        "directional_net",
    )

    assert_equal(
        loaded.raw_alert_count,
        500,
        "raw_alert_count",
    )

    assert_equal(
        loaded.clean_alert_count,
        10,
        "clean_alert_count",
    )

    assert_equal(
        loaded.deduped_alert_count,
        10,
        "deduped_alert_count",
    )

    assert_equal(
        loaded.flow_dedup_level,
        "alert_uuid",
        "flow_dedup_level",
    )

    assert_equal(
        loaded.trade_overlap_detected,
        False,
        "trade_overlap_detected",
    )

    assert_equal(
        loaded.provider,
        "UNUSUAL_WHALES",
        "provider",
    )

    assert_equal(
        loaded.feed,
        "UNKNOWN",
        "feed",
    )

    assert_equal(
        loaded.freshness_status,
        "UNKNOWN",
        "freshness_status",
    )

    assert_equal(
        loaded.total_premium,
        4_000_000.0,
        "total_premium",
    )

    assert_equal(
        loaded.sweep_premium,
        1_200_000.0,
        "sweep_premium",
    )


def test_legacy_columns():
    connection = sqlite3.connect(
        TEST_DB
    )

    connection.row_factory = (
        sqlite3.Row
    )

    row = connection.execute(
        """
        SELECT
            alert_count,
            source_provider
        FROM flow_snapshots
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    connection.close()

    if row is None:
        raise AssertionError(
            "No row found for legacy check."
        )

    assert_equal(
        row["alert_count"],
        10,
        "legacy alert_count",
    )

    assert_equal(
        row["source_provider"],
        "UNUSUAL_WHALES",
        "legacy source_provider",
    )


def test_latest_and_session_list(
    repository: FlowSnapshotRepository,
):
    second = make_snapshot(
        captured_at=datetime(
            2026,
            9,
            4,
            15,
            3,
            tzinfo=ET,
        ),
        net_flow=3_100_000.0,
    )

    repository.create(
        second
    )

    latest = repository.get_latest(
        ticker="AAPL",
        trading_date_et=date(
            2026,
            9,
            4,
        ),
    )

    if latest is None:
        raise AssertionError(
            "Latest snapshot missing."
        )

    assert_equal(
        latest.net_flow,
        3_100_000.0,
        "latest net_flow",
    )

    rows = repository.list_for_session(
        ticker="AAPL",
        trading_date_et=date(
            2026,
            9,
            4,
        ),
    )

    if len(rows) != 2:
        raise AssertionError(
            f"Expected 2 snapshots, "
            f"got {len(rows)}"
        )

    if not (
        rows[0].captured_at
        < rows[1].captured_at
    ):
        raise AssertionError(
            "Session snapshots are "
            "not chronologically ordered."
        )


def test_unique_snapshot_key(
    repository: FlowSnapshotRepository,
):
    duplicate = make_snapshot(
        captured_at=datetime(
            2026,
            9,
            4,
            15,
            3,
            tzinfo=ET,
        )
    )

    error_raised = False

    try:
        repository.create(
            duplicate
        )

    except sqlite3.IntegrityError:
        error_raised = True

    if not error_raised:
        raise AssertionError(
            "Duplicate logical snapshot "
            "was not rejected."
        )


def cleanup():
    for suffix in (
        "",
        "-wal",
        "-shm",
    ):
        path = Path(
            str(TEST_DB) + suffix
        )

        if path.exists():
            path.unlink()


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 FLOWSNAPSHOT REPOSITORY V2 TEST"
    )
    print("=" * 78)
    print()

    production_size_before = (
        PRODUCTION_DB.stat().st_size
    )

    try:
        clone_database()

        patch_repository_database()

        repository = (
            FlowSnapshotRepository()
        )

        test_create_and_roundtrip(
            repository
        )

        print(
            "PASS - Full V2 field round-trip"
        )

        test_legacy_columns()

        print(
            "PASS - Legacy column compatibility"
        )

        test_latest_and_session_list(
            repository
        )

        print(
            "PASS - Latest/session queries"
        )

        test_unique_snapshot_key(
            repository
        )

        print(
            "PASS - Duplicate snapshot protection"
        )

        production_size_after = (
            PRODUCTION_DB.stat().st_size
        )

        assert_equal(
            production_size_after,
            production_size_before,
            "production DB size",
        )

        print()
        print("=" * 78)
        print("FINAL RESULT")
        print("=" * 78)
        print()

        print(
            "FlowSnapshotRepository V2: PASS"
        )

        print(
            "All new flow fields persisted: PASS"
        )

        print(
            "Legacy compatibility: PASS"
        )

        print(
            "Session ordering/latest: PASS"
        )

        print(
            "Logical uniqueness: PASS"
        )

        print(
            "Production weekly_trading.db "
            "modified: NO"
        )

    finally:
        cleanup()


if __name__ == "__main__":
    main()