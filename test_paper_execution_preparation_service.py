from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.signal_feature_repository as signal_feature_repo_module

from weekly.db.position_repository import PositionRepository
from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import (
    PositionStatus,
    SignalState,
    TradeIntent,
    TradeSide,
    TradeStatus,
)
from weekly.services.paper_execution_preparation_service import (
    PaperExecutionPreparationService,
)

from test_signal_feature_repository import make_feature
from test_trade_repository import (
    TEMP_DB,
    create_temp_database,
    make_signal,
    patch_repositories,
    temp_database_connection,
    temp_database_transaction,
)


ET = ZoneInfo("America/New_York")


def main() -> None:
    create_temp_database()
    patch_repositories()

    signal_feature_repo_module.database_connection = (
        temp_database_connection
    )
    signal_feature_repo_module.database_transaction = (
        temp_database_transaction
    )

    try:
        signal_repository = SignalRepository()
        signal_feature_repository = SignalFeatureRepository()
        position_repository = PositionRepository()
        trade_repository = TradeRepository()

        signal = signal_repository.create(
            make_signal()
        )

        assert signal.id is not None
        assert signal.state is SignalState.CONFIRMED

        feature = signal_feature_repository.create(
            make_feature(
                signal_id=signal.id,
                sequence=1,
            )
        )

        assert feature.id is not None

        service = PaperExecutionPreparationService(
            signal_repository=signal_repository,
            signal_feature_repository=signal_feature_repository,
            position_repository=position_repository,
            trade_repository=trade_repository,
        )

        requested_at = datetime(
            2026,
            9,
            4,
            10,
            25,
            tzinfo=ET,
        )

        result = service.prepare(
            signal_id=signal.id,
            quantity=1,
            requested_at=requested_at,
        )

        position = result.position
        trade = result.trade

        assert position.id is not None
        assert position.signal_id == signal.id
        assert position.contract_symbol == (
            "AAPL260911C00320000"
        )
        assert position.strike == 320.0
        assert position.expiry == signal.target_expiry
        assert position.quantity == 1
        assert position.status is PositionStatus.OPEN

        assert position.opened_at is None
        assert position.entry_price is None

        assert trade.id is not None
        assert trade.position_id == position.id
        assert trade.signal_id == signal.id
        assert trade.intent is TradeIntent.OPEN
        assert trade.side is TradeSide.BUY
        assert trade.quantity == 1
        assert trade.status is TradeStatus.REQUESTED
        assert trade.requested_at == requested_at

        assert trade.bid_at_action == 4.80
        assert trade.ask_at_action == 5.00
        assert trade.mark_at_action == 4.90
        assert trade.broker_order_id is None

        persisted_signal = signal_repository.get_by_id(
            signal.id
        )

        assert persisted_signal is not None
        assert (
            persisted_signal.state
            is SignalState.CONFIRMED
        )

        try:
            service.prepare(
                signal_id=signal.id,
                quantity=1,
                requested_at=requested_at,
            )
        except RuntimeError as exc:
            assert (
                "already has an OPEN position"
                in str(exc)
            )
        else:
            raise AssertionError(
                "Duplicate OPEN position guard failed."
            )

        print(
            "PAPER EXECUTION PREPARATION SERVICE: PASS"
        )

    finally:
        for path in (
            TEMP_DB,
            Path(str(TEMP_DB) + "-wal"),
            Path(str(TEMP_DB) + "-shm"),
        ):
            try:
                if path.exists():
                    path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
