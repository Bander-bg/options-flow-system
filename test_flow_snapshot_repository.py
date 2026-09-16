from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.flow_snapshot_repository as flow_repo_module

from weekly.db.database import get_database_path
from weekly.db.flow_snapshot_repository import FlowSnapshotRepository
from weekly.domain.models import FlowSnapshot


ET = ZoneInfo("America/New_York")

TEMP_DB = Path(
    "weekly_flow_snapshot_repository_test.db"
)


def create_temp_database() -> None:
    if TEMP_DB.exists():
        TEMP_DB.unlink()

    source_path = get_database_path()

    source = sqlite3.connect(
        source_path
    )

    destination = sqlite3.connect(
        TEMP_DB
    )

    try:
        source.backup(
            destination
        )

    finally:
        destination.close()
        source.close()


def connect_temp() -> sqlite3.Connection:
    connection = sqlite3.connect(
        TEMP_DB,
        timeout=5,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA journal_mode=WAL;"
    )

    connection.execute(
        "PRAGMA busy_timeout=5000;"
    )

    connection.execute(
        "PRAGMA foreign_keys=ON;"
    )

    return connection


@contextmanager
def temp_database_connection():
    connection = connect_temp()

    try:
        yield connection

    finally:
        connection.close()


@contextmanager
def temp_database_transaction():
    connection = connect_temp()

    try:
        connection.execute(
            "BEGIN IMMEDIATE;"
        )

        yield connection

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def patch_repository() -> None:
    flow_repo_module.database_connection = (
        temp_database_connection
    )

    flow_repo_module.database_transaction = (
        temp_database_transaction
    )


def make_snapshot(
    *,
    minute: int,
    call_ask_premium: float,
    put_ask_premium: float,
    alert_count: int,
) -> FlowSnapshot:

    return FlowSnapshot(
        ticker="AAPL",

        trading_date_et=date(
            2026,
            9,
            4,
        ),

        captured_at=datetime(
            2026,
            9,
            4,
            10,
            minute,
            tzinfo=ET,
        ),

        target_expiry=date(
            2026,
            9,
            11,
        ),

        call_ask_premium=call_ask_premium,

        put_ask_premium=put_ask_premium,

        net_flow=(
            call_ask_premium
            - put_ask_premium
        ),

        alert_count=alert_count,

        flow_dedup_level="alert_composite",

        source_provider="UNUSUAL_WHALES",
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


def assert_close(
    actual,
    expected,
    name: str,
    tolerance: float = 1e-12,
):
    if actual is None:
        raise AssertionError(
            f"{name}: got None"
        )

    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"{name}: expected "
            f"{expected!r}, got {actual!r}"
        )


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 FLOW SNAPSHOT REPOSITORY TEST"
    )
    print("=" * 78)
    print()

    create_temp_database()

    try:
        patch_repository()

        repository = (
            FlowSnapshotRepository()
        )

        # --------------------------------------------------
        # TEST 1 - create first snapshot
        # --------------------------------------------------

        snapshot_1 = repository.create(
            make_snapshot(
                minute=0,
                call_ask_premium=900_000,
                put_ask_premium=250_000,
                alert_count=14,
            )
        )

        if snapshot_1.id is None:
            raise AssertionError(
                "Snapshot id missing."
            )

        print(
            "PASS - create first snapshot"
        )

        # --------------------------------------------------
        # TEST 2 - net flow round-trip
        # --------------------------------------------------

        loaded = repository.get_by_id(
            snapshot_1.id
        )

        if loaded is None:
            raise AssertionError(
                "Snapshot could not be read."
            )

        assert_close(
            loaded.call_ask_premium,
            900_000,
            "call ask premium",
        )

        assert_close(
            loaded.put_ask_premium,
            250_000,
            "put ask premium",
        )

        assert_close(
            loaded.net_flow,
            650_000,
            "net flow",
        )

        assert_equal(
            loaded.alert_count,
            14,
            "alert count",
        )

        assert_equal(
            loaded.flow_dedup_level,
            "alert_composite",
            "flow_dedup_level",
        )

        assert_equal(
            loaded.source_provider,
            "UNUSUAL_WHALES",
            "source provider",
        )

        print(
            "PASS - snapshot round-trip mapping"
        )

        # --------------------------------------------------
        # TEST 3 - create later snapshots
        # --------------------------------------------------

        snapshot_2 = repository.create(
            make_snapshot(
                minute=3,
                call_ask_premium=1_050_000,
                put_ask_premium=300_000,
                alert_count=18,
            )
        )

        snapshot_3 = repository.create(
            make_snapshot(
                minute=6,
                call_ask_premium=1_200_000,
                put_ask_premium=350_000,
                alert_count=22,
            )
        )

        print(
            "PASS - create multiple session snapshots"
        )

        # --------------------------------------------------
        # TEST 4 - latest
        # --------------------------------------------------

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
            latest.id,
            snapshot_3.id,
            "latest snapshot id",
        )

        assert_close(
            latest.net_flow,
            850_000,
            "latest net flow",
        )

        print(
            "PASS - get_latest"
        )

        # --------------------------------------------------
        # TEST 5 - session ordering
        # --------------------------------------------------

        snapshots = (
            repository.list_for_session(
                ticker="AAPL",
                trading_date_et=date(
                    2026,
                    9,
                    4,
                ),
            )
        )

        assert_equal(
            len(snapshots),
            3,
            "snapshot count",
        )

        assert_equal(
            snapshots[0].id,
            snapshot_1.id,
            "first snapshot",
        )

        assert_equal(
            snapshots[1].id,
            snapshot_2.id,
            "second snapshot",
        )

        assert_equal(
            snapshots[2].id,
            snapshot_3.id,
            "third snapshot",
        )

        print(
            "PASS - session snapshots ordered ascending"
        )

        # --------------------------------------------------
        # TEST 6 - duplicate captured_at protection
        # --------------------------------------------------

        duplicate_blocked = False

        try:
            repository.create(
                make_snapshot(
                    minute=6,
                    call_ask_premium=2_000_000,
                    put_ask_premium=100_000,
                    alert_count=30,
                )
            )

        except sqlite3.IntegrityError:
            duplicate_blocked = True

        if not duplicate_blocked:
            raise AssertionError(
                "Duplicate ticker/date/captured_at "
                "was not blocked."
            )

        print(
            "PASS - duplicate snapshot blocked"
        )

        # --------------------------------------------------
        # TEST 7 - different session remains independent
        # --------------------------------------------------

        next_session_latest = (
            repository.get_latest(
                ticker="AAPL",
                trading_date_et=date(
                    2026,
                    9,
                    8,
                ),
            )
        )

        assert_equal(
            next_session_latest,
            None,
            "different session isolation",
        )

        print(
            "PASS - trading_date_et session isolation"
        )

        print()
        print("=" * 78)
        print("FINAL RESULT")
        print("=" * 78)
        print()

        print(
            "FlowSnapshotRepository: PASS"
        )

        print(
            "Call/Put premium round-trip: PASS"
        )

        print(
            "Net Flow round-trip: PASS"
        )

        print(
            "Session ordering: PASS"
        )

        print(
            "Latest snapshot selection: PASS"
        )

        print(
            "Duplicate snapshot protection: PASS"
        )

        print(
            "Production weekly_trading.db modified: NO"
        )

    finally:
        for path in [
            TEMP_DB,
            Path(
                str(TEMP_DB) + "-wal"
            ),
            Path(
                str(TEMP_DB) + "-shm"
            ),
        ]:
            try:
                if path.exists():
                    path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
    