from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from alpaca.trading.enums import OrderStatus

from weekly.db.trade_repository import TradeRepository
from weekly.domain.models import Trade
from weekly.services.alpaca_order_status_mapper import (
    map_alpaca_order_status,
)


@dataclass(frozen=True)
class PaperOrderSyncResult:
    trade: Trade
    alpaca_order_status: OrderStatus


class PaperOrderSyncService:
    """
    Synchronize an already-submitted Alpaca PAPER order
    with the local Trade record.

    This service does NOT submit orders.
    """

    def __init__(
        self,
        *,
        trading_client,
        trade_repository: TradeRepository,
    ) -> None:
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

    @staticmethod
    def _normalize_status(
        value,
    ) -> OrderStatus:
        if isinstance(value, OrderStatus):
            return value

        if value is None:
            raise ValueError(
                "Alpaca order status is missing."
            )

        return OrderStatus(str(value))

    @staticmethod
    def _normalize_datetime(
        value,
    ) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            result = value
        else:
            text = str(value)

            if text.endswith("Z"):
                text = (
                    text[:-1]
                    + "+00:00"
                )

            result = datetime.fromisoformat(
                text
            )

        if result.tzinfo is None:
            raise ValueError(
                "Alpaca filled_at must be "
                "timezone-aware."
            )

        return result

    def sync_trade(
        self,
        *,
        trade_id: int,
    ) -> PaperOrderSyncResult:
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

        if not trade.broker_order_id:
            raise RuntimeError(
                "Trade has no broker_order_id."
            )

        order = (
            self.trading_client.get_order_by_id(
                trade.broker_order_id
            )
        )

        alpaca_status = self._normalize_status(
            self._field(
                order,
                "status",
            )
        )

        local_status = map_alpaca_order_status(
            alpaca_status
        )

        filled_at = self._normalize_datetime(
            self._field(
                order,
                "filled_at",
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
                expected_status=trade.status,
                filled_at=filled_at,
                fill_price=fill_price,
            )
        )

        return PaperOrderSyncResult(
            trade=updated_trade,
            alpaca_order_status=alpaca_status,
        )
