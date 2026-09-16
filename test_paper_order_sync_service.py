from __future__ import annotations

from datetime import datetime
from pathlib import Path

from alpaca.trading.enums import OrderStatus

from weekly.db.position_repository import (
    PositionRepository,
)
from weekly.db.signal_repository import (
    SignalRepository,
)
from weekly.db.trade_repository import (
    TradeRepository,
)
from weekly.domain.enums import (
    ExecutionMode,
    TradeIntent,
    TradeSide,
    TradeStatus,
)
from weekly.domain.models import Trade
from weekly.services.paper_order_sync_service import (
    PaperOrderSyncService,
)

from test_trade_repository import (
    ET,
    TEMP_DB,
    create_temp_database,
    make_position,
    make_signal,
    patch_repositories,
)


class FakeTradingClient:
    def __init__(self) -> None:
        self.requested_order_ids = []

    def get_order_by_id(
        self,
        order_id,
        filter=None,
    ):
        self.requested_order_ids.append(
            str(order_id)
        )

        return {
            "id": str(order_id),
            "status": OrderStatus.FILLED,
            "filled_at": (
                "2026-09-04T14:21:30Z"
            ),
            "filled_avg_price": "5.15",
        }


def main() -> None:
    create_temp_database()
    patch_repositories()

    try:
        signal_repository = SignalRepository()
        position_repository = PositionRepository()
        trade_repository = TradeRepository()

        signal = signal_repository.create(
            make_signal()
        )

        assert signal.id is not None

        position = position_repository.create(
            make_position(signal.id)
        )

        assert position.id is not None

        trade = trade_repository.create(
            Trade(
                position_id=position.id,
                signal_id=signal.id,
                execution_mode=ExecutionMode.PAPER,
                intent=TradeIntent.OPEN,
                side=TradeSide.BUY,
                quantity=1,
                requested_at=datetime(
                    2026,
                    9,
                    4,
                    10,
                    21,
                    tzinfo=ET,
                ),
                bid_at_action=4.80,
                ask_at_action=5.00,
                mark_at_action=4.90,
                options_data_provider="ALPACA",
                options_data_feed="INDICATIVE",
                broker_order_id="paper-order-001",
                status=TradeStatus.REQUESTED,
            )
        )

        assert trade.id is not None

        client = FakeTradingClient()

        service = PaperOrderSyncService(
            trading_client=client,
            trade_repository=trade_repository,
        )

        result = service.sync_trade(
            trade_id=trade.id,
        )

        assert (
            client.requested_order_ids
            == ["paper-order-001"]
        )

        assert (
            result.alpaca_order_status
            == OrderStatus.FILLED
        )

        assert (
            result.trade.status
            == TradeStatus.FILLED
        )

        assert result.trade.fill_price == 5.15
        assert result.trade.filled_at is not None

        persisted = trade_repository.get_by_id(
            trade.id
        )

        assert persisted is not None
        assert (
            persisted.status
            == TradeStatus.FILLED
        )
        assert persisted.fill_price == 5.15
        assert persisted.filled_at is not None

        print(
            "PAPER ORDER SYNC SERVICE: PASS"
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
