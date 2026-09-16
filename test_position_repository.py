from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.position_repository as position_repo_module
import weekly.db.signal_repository as signal_repo_module

from weekly.db.database import get_database_path
from weekly.db.position_repository import PositionRepository
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import (
    Direction,
    ExecutionMode,
    OptionRight,
    PositionStatus,
    SignalState,
)
from weekly.domain.models import (
    Position,
    Signal,
)


ET = ZoneInfo("America/New_York")

TEMP_DB = Path(
    "weekly_position_repository_test.db"
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


def patch_repositories() -> None:
    signal_repo_module.database_connection = (
        temp_database_connection
    )

    signal_repo_module.database_transaction = (
        temp_database_transaction
    )

    position_repo_module.database_connection = (
        temp_database_connection
    )

    position_repo_module.database_transaction = (
        temp_database_transaction
    )


def make_signal() -> Signal:
    return Signal(
        strategy_version="weekly_v1",
        config_hash="position_repo_test_hash",

        ticker="AAPL",

        trading_date_et=date(
            2026,
            9,
            4,
        ),

        target_expiry=date(
            2026,
            9,
            11,
        ),

        direction=Direction.BULLISH,

        candidate_sequence=1,

        state=SignalState.CONFIRMED,

        candidate_at=datetime(
            2026,
            9,
            4,
            10,
            0,
            tzinfo=ET,
        ),

        confirmed_at=datetime(
            2026,
            9,
            4,
            10,
            15,
            tzinfo=ET,
        ),

        net_flow_at_candidate=600_000,
        net_flow_at_confirmation=800_000,

        flow_dedup_level="alert_composite",

        stock_data_provider="ALPACA",
        stock_data_feed="IEX",

        options_data_provider="ALPACA",
        options_data_feed="INDICATIVE",

        theta_convention_status="UNRESOLVED",
        scenario_return_enabled=False,
    )


def make_position(
    *,
    signal_id: int,
    status: PositionStatus,
) -> Position:

    return Position(
        signal_id=signal_id,

        execution_mode=ExecutionMode.PAPER,

        contract_symbol=(
            "AAPL260911C00320000"
        ),

        option_right=OptionRight.CALL,

        strike=320.0,

        expiry=date(
            2026,
            9,
            11,
        ),

        quantity=1,

        status=status,

        opened_at=datetime(
            2026,
            9,
            4,
            10,
            20,
            tzinfo=ET,
        ),

        closed_at=(
            datetime(
                2026,
                9,
                4,
                11,
                0,
                tzinfo=ET,
            )
            if status == PositionStatus.CLOSED
            else None
        ),

        entry_price=5.00,

        exit_price=(
            5.50
            if status == PositionStatus.CLOSED
            else None
        ),

        entry_bid=4.80,
        entry_ask=5.00,
        entry_mark=4.90,

        exit_bid=(
            5.50
            if status == PositionStatus.CLOSED
            else None
        ),

        exit_ask=(
            5.70
            if status == PositionStatus.CLOSED
            else None
        ),

        exit_mark=(
            5.60
            if status == PositionStatus.CLOSED
            else None
        ),
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
        "WEEKLY_V1 POSITION REPOSITORY TEST"
    )
    print("=" * 78)
    print()

    create_temp_database()

    try:
        patch_repositories()

        signal_repository = (
            SignalRepository()
        )

        position_repository = (
            PositionRepository()
        )

        # --------------------------------------------------
        # TEST 1 - parent signal
        # --------------------------------------------------

        signal = signal_repository.create(
            make_signal()
        )

        if signal.id is None:
            raise AssertionError(
                "Parent signal id missing."
            )

        print(
            "PASS - parent signal created"
        )

        # --------------------------------------------------
        # TEST 2 - create open PAPER position
        # --------------------------------------------------

        position = position_repository.create(
            make_position(
                signal_id=signal.id,
                status=PositionStatus.OPEN,
            )
        )

        if position.id is None:
            raise AssertionError(
                "Position id missing."
            )

        print(
            "PASS - create PAPER position"
        )

        # --------------------------------------------------
        # TEST 3 - round-trip mapping
        # --------------------------------------------------

        loaded = (
            position_repository.get_by_id(
                position.id
            )
        )

        if loaded is None:
            raise AssertionError(
                "Position could not be read."
            )

        assert_equal(
            loaded.execution_mode,
            ExecutionMode.PAPER,
            "execution mode",
        )

        assert_equal(
            loaded.option_right,
            OptionRight.CALL,
            "option right",
        )

        assert_equal(
            loaded.status,
            PositionStatus.OPEN,
            "position status",
        )

        assert_equal(
            loaded.quantity,
            1,
            "quantity",
        )

        assert_close(
            loaded.entry_ask,
            5.00,
            "entry ask",
        )

        assert_close(
            loaded.entry_bid,
            4.80,
            "entry bid",
        )

        print(
            "PASS - position round-trip mapping"
        )

        # --------------------------------------------------
        # TEST 4 - get_open_for_signal
        # --------------------------------------------------

        open_position = (
            position_repository
            .get_open_for_signal(
                signal.id
            )
        )

        if open_position is None:
            raise AssertionError(
                "Open position not found."
            )

        assert_equal(
            open_position.id,
            position.id,
            "open position id",
        )

        print(
            "PASS - get_open_for_signal"
        )

        # --------------------------------------------------
        # TEST 5 - list_open
        # --------------------------------------------------

        open_positions = (
            position_repository.list_open()
        )

        assert_equal(
            len(open_positions),
            1,
            "open position count",
        )

        assert_equal(
            open_positions[0].id,
            position.id,
            "list_open position id",
        )

        print(
            "PASS - list_open"
        )

        # --------------------------------------------------
        # TEST 6 - closed position does not appear as open
        # --------------------------------------------------

        closed_position = (
            position_repository.create(
                make_position(
                    signal_id=signal.id,
                    status=PositionStatus.CLOSED,
                )
            )
        )

        if closed_position.id is None:
            raise AssertionError(
                "Closed position id missing."
            )

        open_positions = (
            position_repository.list_open()
        )

        assert_equal(
            len(open_positions),
            1,
            "open count after closed insert",
        )

        print(
            "PASS - closed position excluded from list_open"
        )

        # --------------------------------------------------
        # TEST 7 - list_for_signal
        # --------------------------------------------------

        positions = (
            position_repository
            .list_for_signal(
                signal.id
            )
        )

        assert_equal(
            len(positions),
            2,
            "positions for signal",
        )

        print(
            "PASS - list_for_signal"
        )

        # --------------------------------------------------
        # TEST 8 - invalid signal FK blocked
        # --------------------------------------------------

        foreign_key_blocked = False

        try:
            position_repository.create(
                make_position(
                    signal_id=999999,
                    status=PositionStatus.OPEN,
                )
            )

        except sqlite3.IntegrityError:
            foreign_key_blocked = True

        if not foreign_key_blocked:
            raise AssertionError(
                "Invalid signal_id "
                "was not blocked."
            )

        print(
            "PASS - signal_id foreign key enforced"
        )

        # --------------------------------------------------
        # TEST 9 - DB enforces PAPER-only
        # --------------------------------------------------

        paper_only_blocked = False

        with temp_database_connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO positions (
                        signal_id,
                        execution_mode,
                        contract_symbol,
                        option_right,
                        strike,
                        expiry,
                        quantity,
                        status
                    )
                    VALUES (
                        ?,
                        'LIVE',
                        ?,
                        'call',
                        320,
                        '2026-09-11',
                        1,
                        'OPEN'
                    );
                    """,
                    (
                        signal.id,
                        "AAPL260911C00320000",
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError:
                connection.rollback()
                paper_only_blocked = True

        if not paper_only_blocked:
            raise AssertionError(
                "Database allowed LIVE execution_mode."
            )

        print(
            "PASS - database enforces PAPER-only"
        )

        print()
        print("=" * 78)
        print("FINAL RESULT")
        print("=" * 78)
        print()

        print(
            "PositionRepository: PASS"
        )

        print(
            "Position round-trip: PASS"
        )

        print(
            "Open-position queries: PASS"
        )

        print(
            "PAPER-only database enforcement: PASS"
        )

        print(
            "foreign-key protection: PASS"
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