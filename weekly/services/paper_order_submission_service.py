from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from alpaca.trading.requests import OrderRequest

from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import TradeStatus
from weekly.domain.models import Trade
from weekly.services.alpaca_order_status_mapper import (
    map_alpaca_order_status,
)
from weekly.services.paper_order_sync_service import (
    PaperOrderSyncService,
)


@dataclass(frozen=True)
class PaperOrderSubmissionResult:
    trade: Trade
    broker_order_id: str


class PaperOrderSubmissionService:
    """
    Submit an already-prepared order request to Alpaca
    PAPER trading only.

    This service does NOT choose:
    - order type
    - quantity
    - limit price
    - execution policy
    """

    def __init__(
        self,
        *,
        trading_client,
        trade_repository: TradeRepository,
    ) -> None:
        if getattr(
            trading_client,
            "_sandbox",
            False,
        ) is not True:
            raise ValueError(
                "PaperOrderSubmissionService requires "
                "an Alpaca PAPER trading client."
            )

        self.trading_client = trading_client
        self.trade_repository = trade_repository

    @staticmethod
    def _field(
        order,
        name: str,
    ):
        if isinstance(order, dict):
            return order.get(name)

        return getattr(order, name, None)

    def submit(
        self,
        *,
        trade_id: int,
        order_request: OrderRequest,
    ) -> PaperOrderSubmissionResult:
        if trade_id < 1:
            raise ValueError(
                "trade_id must be >= 1"
            )

        trade = self.trade_repository.get_by_id(
            trade_id
        )

        if trade is None:
            raise RuntimeError(
                "Trade not found."
            )

        if trade.status != TradeStatus.REQUESTED:
            raise RuntimeError(
                "Only REQUESTED trades may be submitted."
            )

        if trade.broker_order_id is not None:
            raise RuntimeError(
                "Trade already has a broker_order_id."
            )

        order = self.trading_client.submit_order(
            order_request
        )

        raw_order_id = self._field(
            order,
            "id",
        )

        if raw_order_id is None:
            raise RuntimeError(
                "Alpaca submit_order response "
                "has no order id."
            )

        broker_order_id = str(
            raw_order_id
        )

        alpaca_status = (
            PaperOrderSyncService
            ._normalize_status(
                self._field(
                    order,
                    "status",
                )
            )
        )

        local_status = map_alpaca_order_status(
            alpaca_status
        )

        filled_at = (
            PaperOrderSyncService
            ._normalize_datetime(
                self._field(
                    order,
                    "filled_at",
                )
            )
        )

        raw_fill_price = self._field(
            order,
            "filled_avg_price",
        )

        fill_price = (
            float(raw_fill_price)
            if raw_fill_price is not None
            else None
        )

        updated_trade = (
            self.trade_repository.update_status(
                trade_id=trade.id,
                new_status=local_status,
                expected_status=TradeStatus.REQUESTED,
                broker_order_id=broker_order_id,
                filled_at=filled_at,
                fill_price=fill_price,
            )
        )

        return PaperOrderSubmissionResult(
            trade=updated_trade,
            broker_order_id=broker_order_id,
        )
