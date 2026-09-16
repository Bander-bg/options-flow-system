from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import weekly.db.signal_feature_repository as signal_feature_repo_module

from weekly.db.position_repository import PositionRepository
from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import (
    PositionStatus,
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
    make_position,
    make_signal,
    patch_repositories,
    temp_database_connection,
    temp_database_transaction,
)


ET = ZoneInfo("America/New_York")


class FakeOptionsProvider:
    def __init__(self):
        self.calls = []

    def get_contract_candidates(
        self,
        *,
        ticker,
        target_expiry,
    ):
        self.calls.append(
            (ticker, target_expiry)
        )

        return SimpleNamespace(
            provider="ALPACA",
            feed="indicative",
            candidates=(
                SimpleNamespace(
                    symbol="AAPL260911C00320000",
                    bid=5.40,
                    ask=5.60,
                ),
            ),
        )


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
        options_provider = FakeOptionsProvider()

        signal = signal_repository.create(
            make_signal()
        )
        assert signal.id is not None

        signal_feature_repository.create(
            make_feature(
                signal_id=signal.id,
                sequence=1,
            )
        )

        position = position_repository.create(
            replace(
                make_position(signal.id),
                status=PositionStatus.OPEN,
                opened_at=datetime(
                    2026,
                    9,
                    4,
                    10,
                    22,
                    tzinfo=ET,
                ),
                entry_price=5.00,
                entry_bid=4.80,
                entry_ask=5.00,
                entry_mark=4.90,
            )
        )

        assert position.id is not None

        service = PaperExecutionPreparationService(
            signal_repository=signal_repository,
            signal_feature_repository=signal_feature_repository,
            position_repository=position_repository,
            trade_repository=trade_repository,
            options_provider=options_provider,
        )

        requested_at = datetime(
            2026,
            9,
            4,
            11,
            0,
            tzinfo=ET,
        )

        result = service.prepare_close(
            position_id=position.id,
            requested_at=requested_at,
        )

        assert result.position.id == position.id
        assert (
            result.position.status
            is PositionStatus.OPEN
        )

        trade = result.trade

        assert trade.id is not None
        assert trade.position_id == position.id
        assert trade.signal_id == signal.id
        assert trade.intent is TradeIntent.CLOSE
        assert trade.side is TradeSide.SELL
        assert trade.quantity == position.quantity
        assert trade.status is TradeStatus.REQUESTED
        assert trade.requested_at == requested_at

        assert trade.bid_at_action == 5.40
        assert trade.ask_at_action == 5.60
        assert trade.mark_at_action == 5.50

        assert trade.options_data_provider == "ALPACA"
        assert trade.options_data_feed == "indicative"
        assert trade.broker_order_id is None

        assert options_provider.calls == [
            (
                signal.ticker,
                position.expiry,
            )
        ]

        persisted_position = (
            position_repository.get_by_id(
                position.id
            )
        )

        assert persisted_position is not None
        assert (
            persisted_position.status
            is PositionStatus.OPEN
        )
        assert persisted_position.closed_at is None

        try:
            service.prepare_close(
                position_id=position.id,
                requested_at=requested_at,
            )
        except RuntimeError as exc:
            assert (
                "already has an active or filled CLOSE"
                in str(exc)
            )
        else:
            raise AssertionError(
                "Duplicate CLOSE guard failed."
            )

        print(
            "PAPER EXECUTION PREPARE CLOSE: PASS"
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
