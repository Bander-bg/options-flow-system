from __future__ import annotations

import hashlib
import shutil
import sqlite3
import tempfile
import uuid

from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path


import weekly.db.outcome_repository as outcome_module
import weekly.db.position_repository as position_module
import weekly.db.trade_repository as trade_module
import weekly.db.data_health_repository as health_module

from weekly.db.outcome_repository import OutcomeRepository
from weekly.db.position_repository import PositionRepository
from weekly.db.trade_repository import TradeRepository
from weekly.db.data_health_repository import DataHealthRepository

from weekly.domain.models import (
    Outcome,
    Position,
    Trade,
    DataHealth,
)

from weekly.domain.enums import (
    OutcomeScope,
    OutcomeStatus,
    ExecutionMode,
    OptionRight,
    PositionStatus,
    TradeIntent,
    TradeSide,
    TradeStatus,
    DataHealthStatus,
)


PROJECT_ROOT = Path(__file__).resolve().parent
PRODUCTION_DB = PROJECT_ROOT / "weekly_trading.db"


def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            hasher.update(chunk)

    return hasher.hexdigest()


def copy_database_safely(
    source_path: Path,
    destination_path: Path,
) -> None:
    source = sqlite3.connect(
        f"file:{source_path.as_posix()}?mode=ro",
        uri=True,
    )

    destination = sqlite3.connect(
        destination_path
    )

    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def main() -> None:
    if not PRODUCTION_DB.exists():
        raise RuntimeError(
            f"Production database not found: "
            f"{PRODUCTION_DB}"
        )

    production_hash_before = file_hash(
        PRODUCTION_DB
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db = (
            Path(temp_dir)
            / "weekly_recovery_test.db"
        )

        copy_database_safely(
            PRODUCTION_DB,
            temp_db,
        )

        @contextmanager
        def temp_database_connection():
            connection = sqlite3.connect(
                temp_db,
                timeout=5.0,
            )

            connection.row_factory = sqlite3.Row

            # Foreign keys are intentionally disabled only
            # inside this disposable recovery test.
            #
            # We are testing the recovered domain-model /
            # repository round-trip, not FK behavior.
            connection.execute(
                "PRAGMA foreign_keys = OFF;"
            )

            try:
                yield connection
            finally:
                connection.close()

        @contextmanager
        def temp_database_transaction():
            connection = sqlite3.connect(
                temp_db,
                timeout=5.0,
            )

            connection.row_factory = sqlite3.Row

            connection.execute(
                "PRAGMA foreign_keys = OFF;"
            )

            try:
                connection.execute("BEGIN;")

                yield connection

                connection.commit()

            except Exception:
                connection.rollback()
                raise

            finally:
                connection.close()

        # ----------------------------------------------
        # Redirect repositories to TEMP database only
        # ----------------------------------------------

        repository_modules = (
            outcome_module,
            position_module,
            trade_module,
            health_module,
        )

        for module in repository_modules:
            module.database_connection = (
                temp_database_connection
            )

            module.database_transaction = (
                temp_database_transaction
            )

        # Use an isolated synthetic signal id.
        test_signal_id = 987654321

        test_id = uuid.uuid4().hex

        now = datetime(
            2026,
            9,
            11,
            15,
            0,
            tzinfo=timezone.utc,
        )

        # ==============================================
        # OUTCOME
        # ==============================================

        outcome_repository = OutcomeRepository()

        outcome = Outcome(
            signal_id=test_signal_id,
            outcome_scope=OutcomeScope(
                "CANDIDATE"
            ),
            checkpoint_name=(
                f"recovery_{test_id}"
            ),
            outcome_status=OutcomeStatus(
                "OBSERVED"
            ),
            scheduled_at=now,
            observed_at=now,
            baseline_at=now,
            baseline_underlying_price=100.0,
            observed_underlying_price=101.0,
            underlying_raw_return=0.01,
            underlying_directional_return=0.01,
            contract_symbol="TEST260911C00100000",
            baseline_option_bid=1.00,
            baseline_option_ask=1.20,
            baseline_option_mark=1.10,
            observed_option_bid=1.30,
            observed_option_ask=1.50,
            observed_option_mark=1.40,
            option_executable_return=(
                (1.30 - 1.20) / 1.20
            ),
            option_mark_return=(
                (1.40 - 1.10) / 1.10
            ),
            settlement_value=None,
            stock_data_provider="TEST",
            stock_data_feed="TEST",
            options_data_provider="TEST",
            options_data_feed="TEST",
        )

        created_outcome = (
            outcome_repository.create(
                outcome
            )
        )

        assert created_outcome.id is not None

        loaded_outcome = (
            outcome_repository.get_by_id(
                created_outcome.id
            )
        )

        assert loaded_outcome is not None

        assert (
            loaded_outcome.outcome_scope
            == OutcomeScope("CANDIDATE")
        )

        keyed_outcome = (
            outcome_repository.get_by_key(
                signal_id=test_signal_id,
                outcome_scope=OutcomeScope(
                    "CANDIDATE"
                ),
                checkpoint_name=(
                    f"recovery_{test_id}"
                ),
            )
        )

        assert keyed_outcome is not None

        assert any(
            item.id == created_outcome.id
            for item
            in outcome_repository.list_for_signal(
                test_signal_id
            )
        )

        print(
            "OutcomeRepository round-trip: PASS"
        )

        # ==============================================
        # POSITION
        # ==============================================

        position_repository = (
            PositionRepository()
        )

        position = Position(
            signal_id=test_signal_id,
            execution_mode=ExecutionMode(
                "PAPER"
            ),
            contract_symbol=(
                "TEST260911C00100000"
            ),
            option_right=OptionRight(
                "call"
            ),
            strike=100.0,
            expiry=date(
                2026,
                9,
                11,
            ),
            quantity=1,
            status=PositionStatus(
                "OPEN"
            ),
            opened_at=now,
            entry_price=1.20,
            entry_bid=1.00,
            entry_ask=1.20,
            entry_mark=1.10,
        )

        created_position = (
            position_repository.create(
                position
            )
        )

        assert created_position.id is not None

        loaded_position = (
            position_repository.get_by_id(
                created_position.id
            )
        )

        assert loaded_position is not None

        assert (
            loaded_position.option_right
            == OptionRight("call")
        )

        open_position = (
            position_repository
            .get_open_for_signal(
                test_signal_id
            )
        )

        assert open_position is not None

        assert (
            open_position.id
            == created_position.id
        )

        assert any(
            item.id == created_position.id
            for item
            in position_repository.list_for_signal(
                test_signal_id
            )
        )

        assert any(
            item.id == created_position.id
            for item
            in position_repository.list_open()
        )

        print(
            "PositionRepository round-trip: PASS"
        )

        # ==============================================
        # TRADE
        # ==============================================

        trade_repository = TradeRepository()

        trade = Trade(
            position_id=created_position.id,
            signal_id=test_signal_id,
            execution_mode=ExecutionMode(
                "PAPER"
            ),
            intent=TradeIntent(
                "OPEN"
            ),
            side=TradeSide(
                "BUY"
            ),
            quantity=1,
            requested_at=now,
            filled_at=now,
            fill_price=1.20,
            bid_at_action=1.00,
            ask_at_action=1.20,
            mark_at_action=1.10,
            options_data_provider="TEST",
            options_data_feed="TEST",
            broker_order_id=(
                f"RECOVERY-{test_id}"
            ),
            status=TradeStatus(
                "FILLED"
            ),
        )

        created_trade = (
            trade_repository.create(
                trade
            )
        )

        assert created_trade.id is not None

        loaded_trade = (
            trade_repository.get_by_id(
                created_trade.id
            )
        )

        assert loaded_trade is not None

        assert (
            loaded_trade.status
            == TradeStatus("FILLED")
        )

        broker_trade = (
            trade_repository
            .get_by_broker_order_id(
                f"RECOVERY-{test_id}"
            )
        )

        assert broker_trade is not None

        assert any(
            item.id == created_trade.id
            for item
            in trade_repository.list_for_position(
                created_position.id
            )
        )

        assert any(
            item.id == created_trade.id
            for item
            in trade_repository.list_for_signal(
                test_signal_id
            )
        )

        print(
            "TradeRepository round-trip: PASS"
        )

        # ==============================================
        # DATA HEALTH
        # ==============================================

        health_repository = (
            DataHealthRepository()
        )

        component_name = (
            f"RECOVERY_TEST_{test_id}"
        )

        health = DataHealth(
            captured_at=now,
            trading_date_et=date(
                2026,
                9,
                11,
            ),
            ticker="TEST",
            component=component_name,
            status=DataHealthStatus(
                "PASS"
            ),
            provider="TEST",
            feed="TEST",
            message=(
                "Temporary domain recovery test."
            ),
        )

        created_health = (
            health_repository.create(
                health
            )
        )

        assert created_health.id is not None

        loaded_health = (
            health_repository.get_by_id(
                created_health.id
            )
        )

        assert loaded_health is not None

        assert (
            loaded_health.status
            == DataHealthStatus("PASS")
        )

        latest_health = (
            health_repository
            .get_latest_for_component(
                component=component_name,
                ticker="TEST",
            )
        )

        assert latest_health is not None

        assert (
            latest_health.id
            == created_health.id
        )

        assert any(
            item.id == created_health.id
            for item
            in health_repository.list_latest(
                limit=100
            )
        )

        print(
            "DataHealthRepository round-trip: PASS"
        )

    # ==============================================
    # PRODUCTION SAFETY CHECK
    # ==============================================

    production_hash_after = file_hash(
        PRODUCTION_DB
    )

    assert (
        production_hash_before
        == production_hash_after
    ), (
        "Production weekly_trading.db changed "
        "during temporary recovery test."
    )

    print(
        "Production weekly_trading.db modified: NO"
    )

    print()
    print("=" * 70)
    print(
        "RECOVERED DOMAIN REPOSITORIES: PASS"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()