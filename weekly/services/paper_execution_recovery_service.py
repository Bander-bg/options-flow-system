from __future__ import annotations

from dataclasses import dataclass

from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import TradeIntent, TradeStatus
from weekly.services.paper_execution_fill_service import (
    PaperExecutionFillResult,
    PaperExecutionFillService,
)
from weekly.services.paper_execution_lifecycle_service import (
    PaperExecutionLifecycleResult,
    PaperExecutionLifecycleService,
)


@dataclass(frozen=True)
class PaperExecutionRecoveryItem:
    trade_id: int
    original_status: TradeStatus
    lifecycle_result: PaperExecutionLifecycleResult | None
    fill_result: PaperExecutionFillResult | None
    reason: str


@dataclass(frozen=True)
class PaperExecutionRecoveryResult:
    items: tuple[PaperExecutionRecoveryItem, ...]


class PaperExecutionRecoveryService:
    """
    Reconcile unfinished PAPER OPEN/CLOSE executions.

    REQUESTED / PARTIALLY_FILLED:
        synchronize with Alpaca through lifecycle service.

    FILLED with unapplied Position entry:
        apply the locally persisted fill directly.

    This service does NOT:
    - submit new orders
    - choose quantity or order policy
    - transition Signal state
    """

    def __init__(
        self,
        *,
        trade_repository: TradeRepository,
        lifecycle_service: PaperExecutionLifecycleService,
        fill_service: PaperExecutionFillService,
    ):
        self.trade_repository = trade_repository
        self.lifecycle_service = lifecycle_service
        self.fill_service = fill_service

    def recover(
        self,
    ) -> PaperExecutionRecoveryResult:
        candidates = (
            self.trade_repository
            .list_execution_recovery_candidates()
        )

        items: list[PaperExecutionRecoveryItem] = []

        for trade in candidates:
            if trade.id is None:
                raise RuntimeError(
                    "Recovery candidate trade id is missing."
                )

            if trade.status is TradeStatus.FILLED:
                if trade.intent is TradeIntent.OPEN:
                    fill_result = (
                        self.fill_service.apply_open_fill(
                            trade_id=trade.id,
                        )
                    )

                    reason = (
                        "LOCAL_FILLED_POSITION_ENTRY_RECOVERED"
                    )

                elif trade.intent is TradeIntent.CLOSE:
                    fill_result = (
                        self.fill_service.apply_close_fill(
                            trade_id=trade.id,
                        )
                    )

                    reason = (
                        "LOCAL_FILLED_POSITION_EXIT_RECOVERED"
                    )

                else:
                    raise RuntimeError(
                        "Unexpected execution recovery intent: "
                        f"{trade.intent.value}"
                    )

                items.append(
                    PaperExecutionRecoveryItem(
                        trade_id=trade.id,
                        original_status=trade.status,
                        lifecycle_result=None,
                        fill_result=fill_result,
                        reason=reason,
                    )
                )

                continue

            if trade.status in (
                TradeStatus.REQUESTED,
                TradeStatus.PARTIALLY_FILLED,
            ):
                lifecycle_result = (
                    self.lifecycle_service.sync(
                        trade_id=trade.id,
                    )
                )

                items.append(
                    PaperExecutionRecoveryItem(
                        trade_id=trade.id,
                        original_status=trade.status,
                        lifecycle_result=lifecycle_result,
                        fill_result=None,
                        reason="BROKER_ORDER_RECONCILED",
                    )
                )

                continue

            raise RuntimeError(
                "Unexpected execution recovery status: "
                f"{trade.status.value}"
            )

        return PaperExecutionRecoveryResult(
            items=tuple(items),
        )
