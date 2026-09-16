from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.position_repository as position_repo_module
import weekly.db.signal_repository as signal_repo_module
import weekly.db.trade_repository as trade_repo_module

from weekly.db.database import get_database_path
from weekly.db.position_repository import PositionRepository
from weekly.db.signal_repository import SignalRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import (
    Direction,
    ExecutionMode,
    OptionRight,
    PositionStatus,
    SignalState,
    TradeIntent,
    TradeSide,
    TradeStatus,
)
from weekly.domain.models import (
    Position,
    Signal,
    Trade,
)


ET = ZoneInfo("America/New_York")

TEMP_DB = Path(
    "weekly_trade_repository_test.db"
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

    trade_repo_module.database_connection = (
        temp_database_connection
    )

    trade_repo_module.database_transaction = (
        temp_database_transaction
    )


def make_signal() -> Signal:
    return Signal(
        strategy_version="weekly_v1",
        config_hash="trade_repo_test_hash",

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
    signal_id: int,
) -> Position:
    return Position(
        signal_id=signal_id,

        execution_mode=ExecutionMode.PAPER,

        contract_symbol="AAPL260911C00320000",

        option_right=OptionRight.CALL,

        strike=320.0,

        expiry=date(
            2026,
            9,
            11,
        ),

        quantity=1,

        status=PositionStatus.OPEN,

        opened_at=datetime(
            2026,
            9,
            4,
            10,
            20,
            tzinfo=ET,
        ),

        entry_price=5.00,

        entry_bid=4.80,
        entry_ask=5.00,
        entry_mark=4.90,
    )


def make_trade(
    *,
    position_id: int,
    signal_id: int,
    intent: TradeIntent,
    side: TradeSide,
    broker_order_id: str,
    minute: int,
) -> Trade:
    return Trade(
        position_id=position_id,
        signal_id=signal_id,

        execution_mode=ExecutionMode.PAPER,

        intent=intent,
        side=side,

        quantity=1,

        requested_at=datetime(
            2026,
            9,
            4,
            10,
            minute,
            tzinfo=ET,
        ),

        filled_at=datetime(
            2026,
            9,
            4,
            10,
            minute,
            30,
            tzinfo=ET,
        ),

        fill_price=5.00,

        bid_at_action=4.80,
        ask_at_action=5.00,
        mark_at_action=4.90,

        options_data_provider="ALPACA",
        options_data_feed="INDICATIVE",

        broker_order_id=broker_order_id,

        status=TradeStatus.FILLED,
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
        "WEEKLY_V1 TRADE REPOSITORY TEST"
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

        trade_repository = (
            TradeRepository()
        )

        # --------------------------------------------------
        # TEST 1 - create parent signal
        # --------------------------------------------------

        signal = signal_repository.create(
            make_signal()
        )

        if signal.id is None:
            raise AssertionError(
                "Signal id missing."
            )

        print(
            "PASS - parent signal created"
        )

        # --------------------------------------------------
        # TEST 2 - create parent position
        # --------------------------------------------------

        position = (
            position_repository.create(
                make_position(
                    signal.id
                )
            )
        )

        if position.id is None:
            raise AssertionError(
                "Position id missing."
            )

        print(
            "PASS - parent position created"
        )

        # --------------------------------------------------
        # TEST 3 - create OPEN / BUY trade
        # --------------------------------------------------

        open_trade = (
            trade_repository.create(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id=(
                        "paper-open-001"
                    ),
                    minute=21,
                )
            )
        )

        if open_trade.id is None:
            raise AssertionError(
                "Open trade id missing."
            )

        print(
            "PASS - create OPEN / BUY trade"
        )

        # --------------------------------------------------
        # TEST 4 - round-trip mapping
        # --------------------------------------------------

        loaded = (
            trade_repository.get_by_id(
                open_trade.id
            )
        )

        if loaded is None:
            raise AssertionError(
                "Trade could not be read."
            )

        assert_equal(
            loaded.execution_mode,
            ExecutionMode.PAPER,
            "execution mode",
        )

        assert_equal(
            loaded.intent,
            TradeIntent.OPEN,
            "intent",
        )

        assert_equal(
            loaded.side,
            TradeSide.BUY,
            "side",
        )

        assert_equal(
            loaded.status,
            TradeStatus.FILLED,
            "status",
        )

        assert_close(
            loaded.bid_at_action,
            4.80,
            "bid",
        )

        assert_close(
            loaded.ask_at_action,
            5.00,
            "ask",
        )

        assert_close(
            loaded.mark_at_action,
            4.90,
            "mark",
        )

        assert_equal(
            loaded.options_data_feed,
            "INDICATIVE",
            "options feed",
        )

        print(
            "PASS - trade round-trip mapping"
        )

        # --------------------------------------------------
        # TEST 5 - get by broker order id
        # --------------------------------------------------

        by_order = (
            trade_repository
            .get_by_broker_order_id(
                "paper-open-001"
            )
        )

        if by_order is None:
            raise AssertionError(
                "Trade not found by "
                "broker_order_id."
            )

        assert_equal(
            by_order.id,
            open_trade.id,
            "broker order lookup",
        )

        print(
            "PASS - get_by_broker_order_id"
        )

        # --------------------------------------------------
        # TEST 6 - duplicate broker_order_id blocked
        # --------------------------------------------------

        duplicate_blocked = False

        try:
            trade_repository.create(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id=(
                        "paper-open-001"
                    ),
                    minute=22,
                )
            )

        except sqlite3.IntegrityError:
            duplicate_blocked = True

        if not duplicate_blocked:
            raise AssertionError(
                "Duplicate broker_order_id "
                "was not blocked."
            )

        print(
            "PASS - duplicate broker_order_id blocked"
        )

        # --------------------------------------------------
        # TEST 7 - create CLOSE / SELL trade
        # --------------------------------------------------

        close_trade = (
            trade_repository.create(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.CLOSE,
                    side=TradeSide.SELL,
                    broker_order_id=(
                        "paper-close-001"
                    ),
                    minute=45,
                )
            )
        )

        if close_trade.id is None:
            raise AssertionError(
                "Close trade id missing."
            )

        print(
            "PASS - create CLOSE / SELL trade"
        )

        # --------------------------------------------------
        # TEST 8 - list_for_position
        # --------------------------------------------------

        position_trades = (
            trade_repository
            .list_for_position(
                position.id
            )
        )

        assert_equal(
            len(position_trades),
            2,
            "position trade count",
        )

        assert_equal(
            position_trades[0].intent,
            TradeIntent.OPEN,
            "first trade intent",
        )

        assert_equal(
            position_trades[1].intent,
            TradeIntent.CLOSE,
            "second trade intent",
        )

        print(
            "PASS - list_for_position ordering"
        )

        # --------------------------------------------------
        # TEST 9 - list_for_signal
        # --------------------------------------------------

        signal_trades = (
            trade_repository.list_for_signal(
                signal.id
            )
        )

        assert_equal(
            len(signal_trades),
            2,
            "signal trade count",
        )

        print(
            "PASS - list_for_signal"
        )

        # --------------------------------------------------
        # TEST 10 - invalid position FK blocked
        # --------------------------------------------------

        position_fk_blocked = False

        try:
            trade_repository.create(
                make_trade(
                    position_id=999999,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id=(
                        "bad-position-fk"
                    ),
                    minute=50,
                )
            )

        except sqlite3.IntegrityError:
            position_fk_blocked = True

        if not position_fk_blocked:
            raise AssertionError(
                "Invalid position_id "
                "was not blocked."
            )

        print(
            "PASS - position_id foreign key enforced"
        )

        # --------------------------------------------------
        # TEST 11 - invalid signal FK blocked
        # --------------------------------------------------

        signal_fk_blocked = False

        try:
            trade_repository.create(
                make_trade(
                    position_id=position.id,
                    signal_id=999999,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id=(
                        "bad-signal-fk"
                    ),
                    minute=51,
                )
            )

        except sqlite3.IntegrityError:
            signal_fk_blocked = True

        if not signal_fk_blocked:
            raise AssertionError(
                "Invalid signal_id "
                "was not blocked."
            )

        print(
            "PASS - signal_id foreign key enforced"
        )

        # --------------------------------------------------
        # TEST 12 - DB enforces PAPER-only
        # --------------------------------------------------

        paper_only_blocked = False

        with temp_database_connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO trades (
                        position_id,
                        signal_id,
                        execution_mode,
                        intent,
                        side,
                        quantity,
                        requested_at,
                        status
                    )
                    VALUES (
                        ?,
                        ?,
                        'LIVE',
                        'OPEN',
                        'BUY',
                        1,
                        '2026-09-04T10:55:00-04:00',
                        'REQUESTED'
                    );
                    """,
                    (
                        position.id,
                        signal.id,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError:
                connection.rollback()
                paper_only_blocked = True

        if not paper_only_blocked:
            raise AssertionError(
                "Database allowed LIVE "
                "trade execution_mode."
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
            "TradeRepository: PASS"
        )

        print(
            "OPEN/BUY + CLOSE/SELL: PASS"
        )

        print(
            "Bid/Ask/Mark round-trip: PASS"
        )

        print(
            "broker_order_id uniqueness: PASS"
        )

        print(
            "Position/Signal FK protection: PASS"
        )

        print(
            "PAPER-only database enforcement: PASS"
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