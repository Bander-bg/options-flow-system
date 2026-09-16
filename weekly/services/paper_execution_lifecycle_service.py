from __future__ import annotations

from dataclasses import dataclass

from weekly.domain.enums import TradeIntent, TradeStatus
from weekly.domain.models import Position, Trade
from weekly.services.paper_execution_fill_service import (
    PaperExecutionFillService,
    PaperExecutionFillResult,
)
from weekly.services.paper_order_sync_service import (
    PaperOrderSyncResult,
    PaperOrderSyncService,
)


@dataclass(frozen=True)
class PaperExecutionLifecycleResult:
    trade: Trade
    position: Position | None
    order_sync: PaperOrderSyncResult
    fill_result: PaperExecutionFillResult | None
    reason: str


class PaperExecutionLifecycleService:
    """
    Synchronize a PAPER order and apply OPEN fills.

    This service does NOT:
    - submit orders
    - choose execution policy
    - choose quantity
    - transition Signal state
    """

    def __init__(
        self,
        *,
        order_sync_service: PaperOrderSyncService,
        fill_service: PaperExecutionFillService,
    ):
        self.order_sync_service = order_sync_service
        self.fill_service = fill_service

    def sync(
        self,
        *,
        trade_id: int,
    ) -> PaperExecutionLifecycleResult:
        if trade_id < 1:
            raise ValueError(
                "trade_id must be >= 1"
            )

        order_sync = (
            self.order_sync_service.sync_trade(
                trade_id=trade_id
            )
        )

        trade = order_sync.trade

        if (
            trade.intent is TradeIntent.OPEN
            and trade.status is TradeStatus.FILLED
        ):
            fill_result = (
                self.fill_service.apply_open_fill(
                    trade_id=trade_id
                )
            )

            return PaperExecutionLifecycleResult(
                trade=fill_result.trade,
                position=fill_result.position,
                order_sync=order_sync,
                fill_result=fill_result,
                reason="OPEN_FILL_APPLIED",
            )

        if (
            trade.intent is TradeIntent.CLOSE
            and trade.status is TradeStatus.FILLED
        ):
            fill_result = (
                self.fill_service.apply_close_fill(
                    trade_id=trade_id
                )
            )

            return PaperExecutionLifecycleResult(
                trade=fill_result.trade,
                position=fill_result.position,
                order_sync=order_sync,
                fill_result=fill_result,
                reason="CLOSE_FILL_APPLIED",
            )

        return PaperExecutionLifecycleResult(
            trade=trade,
            position=None,
            order_sync=order_sync,
            fill_result=None,
            reason=(
                "NO_OPEN_FILL_TO_APPLY"
                if trade.intent is TradeIntent.OPEN
                else "NO_CLOSE_FILL_TO_APPLY"
            ),
        )
