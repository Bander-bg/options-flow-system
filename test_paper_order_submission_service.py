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
from weekly.services.paper_order_submission_service import (
    PaperOrderSubmissionService,
)

from test_trade_repository import (
    ET,
    TEMP_DB,
    create_temp_database,
    make_position,
    make_signal,
    patch_repositories,
)


class FakePaperTradingClient:
    _sandbox = True

    def __init__(self) -> None:
        self.submitted = []

    def submit_order(
        self,
        order_request,
    ):
        self.submitted.append(
            order_request
        )

        return {
            "id": "paper-order-002",
            "status": OrderStatus.ACCEPTED,
            "filled_at": None,
            "filled_avg_price": None,
        }


class FakeLiveTradingClient:
    _sandbox = False


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
                status=TradeStatus.REQUESTED,
            )
        )

        assert trade.id is not None

        client = FakePaperTradingClient()

        service = PaperOrderSubmissionService(
            trading_client=client,
            trade_repository=trade_repository,
        )

        prepared_order_request = object()

        result = service.submit(
            trade_id=trade.id,
            order_request=prepared_order_request,
        )

        assert (
            client.submitted
            == [prepared_order_request]
        )

        assert (
            result.broker_order_id
            == "paper-order-002"
        )

        assert (
            result.trade.status
            == TradeStatus.REQUESTED
        )

        assert (
            result.trade.broker_order_id
            == "paper-order-002"
        )

        persisted = trade_repository.get_by_id(
            trade.id
        )

        assert persisted is not None
        assert (
            persisted.status
            == TradeStatus.REQUESTED
        )
        assert (
            persisted.broker_order_id
            == "paper-order-002"
        )

        try:
            PaperOrderSubmissionService(
                trading_client=(
                    FakeLiveTradingClient()
                ),
                trade_repository=trade_repository,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Live trading client guard failed."
            )

        print(
            "PAPER ORDER SUBMISSION SERVICE: PASS"
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
