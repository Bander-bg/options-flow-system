from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.data_health_repository as health_repo_module

from weekly.db.database import get_database_path
from weekly.db.data_health_repository import DataHealthRepository
from weekly.domain.enums import DataHealthStatus
from weekly.domain.models import DataHealth


ET = ZoneInfo("America/New_York")

TEMP_DB = Path(
    "weekly_data_health_repository_test.db"
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
    health_repo_module.database_connection = (
        temp_database_connection
    )

    health_repo_module.database_transaction = (
        temp_database_transaction
    )


def make_health(
    *,
    minute: int,
    component: str,
    status: DataHealthStatus,
    ticker: str | None,
    provider: str | None,
    feed: str | None,
    message: str,
) -> DataHealth:

    return DataHealth(
        captured_at=datetime(
            2026,
            9,
            4,
            10,
            minute,
            tzinfo=ET,
        ),

        trading_date_et=date(
            2026,
            9,
            4,
        ),

        ticker=ticker,

        component=component,

        status=status,

        provider=provider,

        feed=feed,

        message=message,
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


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 DATA HEALTH REPOSITORY TEST"
    )
    print("=" * 78)
    print()

    create_temp_database()

    try:
        patch_repository()

        repository = DataHealthRepository()

        # --------------------------------------------------
        # TEST 1 - create first health record
        # --------------------------------------------------

        first = repository.create(
            make_health(
                minute=0,
                component="stock_feed",
                status=DataHealthStatus.DEGRADED,
                ticker="AAPL",
                provider="ALPACA",
                feed="IEX",
                message="SIP unavailable; IEX fallback active.",
            )
        )

        if first.id is None:
            raise AssertionError(
                "DataHealth id missing."
            )

        print(
            "PASS - create data-health record"
        )

        # --------------------------------------------------
        # TEST 2 - round-trip mapping
        # --------------------------------------------------

        loaded = repository.get_by_id(
            first.id
        )

        if loaded is None:
            raise AssertionError(
                "DataHealth could not be read."
            )

        assert_equal(
            loaded.component,
            "stock_feed",
            "component",
        )

        assert_equal(
            loaded.status,
            DataHealthStatus.DEGRADED,
            "status",
        )

        assert_equal(
            loaded.provider,
            "ALPACA",
            "provider",
        )

        assert_equal(
            loaded.feed,
            "IEX",
            "feed",
        )

        assert_equal(
            loaded.ticker,
            "AAPL",
            "ticker",
        )

        print(
            "PASS - data-health round-trip"
        )

        # --------------------------------------------------
        # TEST 3 - add newer stock-feed record
        # --------------------------------------------------

        second = repository.create(
            make_health(
                minute=3,
                component="stock_feed",
                status=DataHealthStatus.PASS,
                ticker="AAPL",
                provider="ALPACA",
                feed="IEX",
                message="Stock feed healthy.",
            )
        )

        if second.id is None:
            raise AssertionError(
                "Second DataHealth id missing."
            )

        latest = (
            repository.get_latest_for_component(
                component="stock_feed",
                ticker="AAPL",
            )
        )

        if latest is None:
            raise AssertionError(
                "Latest component record missing."
            )

        assert_equal(
            latest.id,
            second.id,
            "latest record id",
        )

        assert_equal(
            latest.status,
            DataHealthStatus.PASS,
            "latest status",
        )

        print(
            "PASS - get_latest_for_component"
        )

        # --------------------------------------------------
        # TEST 4 - ticker scopes remain separate
        # --------------------------------------------------

        nvda = repository.create(
            make_health(
                minute=4,
                component="stock_feed",
                status=DataHealthStatus.UNKNOWN,
                ticker="NVDA",
                provider="ALPACA",
                feed="IEX",
                message="Temporary uncertainty.",
            )
        )

        latest_aapl = (
            repository.get_latest_for_component(
                component="stock_feed",
                ticker="AAPL",
            )
        )

        latest_nvda = (
            repository.get_latest_for_component(
                component="stock_feed",
                ticker="NVDA",
            )
        )

        assert_equal(
            latest_aapl.id,
            second.id,
            "AAPL isolation",
        )

        assert_equal(
            latest_nvda.id,
            nvda.id,
            "NVDA isolation",
        )

        print(
            "PASS - ticker health scopes independent"
        )

        # --------------------------------------------------
        # TEST 5 - system-wide component with ticker=None
        # --------------------------------------------------

        options_health = repository.create(
            make_health(
                minute=5,
                component="options_feed",
                status=DataHealthStatus.DEGRADED,
                ticker=None,
                provider="ALPACA",
                feed="INDICATIVE",
                message="OPRA unavailable; Indicative fallback active.",
            )
        )

        latest_options = (
            repository.get_latest_for_component(
                component="options_feed",
                ticker=None,
            )
        )

        if latest_options is None:
            raise AssertionError(
                "System-wide component record missing."
            )

        assert_equal(
            latest_options.id,
            options_health.id,
            "system-wide latest",
        )

        assert_equal(
            latest_options.status,
            DataHealthStatus.DEGRADED,
            "options health status",
        )

        print(
            "PASS - system-wide component health"
        )

        # --------------------------------------------------
        # TEST 6 - list_latest ordering
        # --------------------------------------------------

        latest_rows = repository.list_latest(
            limit=3
        )

        assert_equal(
            len(latest_rows),
            3,
            "latest row count",
        )

        assert_equal(
            latest_rows[0].id,
            options_health.id,
            "latest ordering first",
        )

        assert_equal(
            latest_rows[1].id,
            nvda.id,
            "latest ordering second",
        )

        assert_equal(
            latest_rows[2].id,
            second.id,
            "latest ordering third",
        )

        print(
            "PASS - list_latest ordering"
        )

        # --------------------------------------------------
        # TEST 7 - invalid limit rejected
        # --------------------------------------------------

        invalid_limit_blocked = False

        try:
            repository.list_latest(
                limit=0
            )

        except ValueError:
            invalid_limit_blocked = True

        if not invalid_limit_blocked:
            raise AssertionError(
                "Invalid list limit was not blocked."
            )

        print(
            "PASS - invalid list limit blocked"
        )

        # --------------------------------------------------
        # TEST 8 - database status constraint
        # --------------------------------------------------

        invalid_status_blocked = False

        with temp_database_connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO data_health (
                        captured_at,
                        component,
                        status
                    )
                    VALUES (
                        '2026-09-04T10:10:00-04:00',
                        'bad_component',
                        'INVALID_STATUS'
                    );
                    """
                )

                connection.commit()

            except sqlite3.IntegrityError:
                connection.rollback()
                invalid_status_blocked = True

        if not invalid_status_blocked:
            raise AssertionError(
                "Invalid data-health status "
                "was not blocked."
            )

        print(
            "PASS - database status constraint enforced"
        )

        print()
        print("=" * 78)
        print("FINAL RESULT")
        print("=" * 78)
        print()

        print(
            "DataHealthRepository: PASS"
        )

        print(
            "Health status round-trip: PASS"
        )

        print(
            "Component/ticker isolation: PASS"
        )

        print(
            "Latest-health queries: PASS"
        )

        print(
            "Database status constraint: PASS"
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