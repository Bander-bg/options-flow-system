from __future__ import annotations

from dataclasses import dataclass

from weekly.db.position_repository import PositionRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import (
    PositionStatus,
    TradeIntent,
    TradeStatus,
)
from weekly.domain.models import Position, Trade


@dataclass(frozen=True)
class PaperExecutionFillResult:
    trade: Trade
    position: Position
    persisted: bool
    reason: str


class PaperExecutionFillService:
    """
    Apply a FILLED PAPER OPEN trade to its Position.

    This service does NOT:
    - submit an order
    - choose execution policy
    - change Signal state
    """

    def __init__(
        self,
        *,
        trade_repository: TradeRepository,
        position_repository: PositionRepository,
    ):
        self.trade_repository = trade_repository
        self.position_repository = position_repository

    def apply_open_fill(
        self,
        *,
        trade_id: int,
    ) -> PaperExecutionFillResult:
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

        if trade.intent is not TradeIntent.OPEN:
            raise RuntimeError(
                "Only OPEN trades may apply "
                "a position entry fill."
            )

        if trade.status is not TradeStatus.FILLED:
            raise RuntimeError(
                "Trade must be FILLED before "
                "position entry can be recorded."
            )

        if trade.filled_at is None:
            raise RuntimeError(
                "FILLED trade is missing filled_at."
            )

        if trade.fill_price is None:
            raise RuntimeError(
                "FILLED trade is missing fill_price."
            )

        position = self.position_repository.get_by_id(
            trade.position_id
        )

        if position is None:
            raise RuntimeError(
                "Position not found."
            )

        if position.signal_id != trade.signal_id:
            raise RuntimeError(
                "Trade/Position signal mismatch."
            )

        if position.opened_at is not None:
            return PaperExecutionFillResult(
                trade=trade,
                position=position,
                persisted=False,
                reason="POSITION_ENTRY_ALREADY_RECORDED",
            )

        updated_position = (
            self.position_repository.update_entry(
                position_id=position.id,
                opened_at=trade.filled_at,
                entry_price=trade.fill_price,
                entry_bid=trade.bid_at_action,
                entry_ask=trade.ask_at_action,
                entry_mark=trade.mark_at_action,
            )
        )

        return PaperExecutionFillResult(
            trade=trade,
            position=updated_position,
            persisted=True,
            reason="OPEN_FILL_APPLIED",
        )


    def apply_close_fill(
        self,
        *,
        trade_id: int,
    ) -> PaperExecutionFillResult:
        """
        Apply a FILLED PAPER CLOSE trade to its Position.

        This records the position exit only.
        It does NOT:
        - choose when to exit
        - create the CLOSE trade
        - submit an order
        - transition Signal state
        """
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

        if trade.intent is not TradeIntent.CLOSE:
            raise RuntimeError(
                "Only CLOSE trades may apply "
                "a position exit fill."
            )

        if trade.status is not TradeStatus.FILLED:
            raise RuntimeError(
                "Trade must be FILLED before "
                "position exit can be recorded."
            )

        if trade.filled_at is None:
            raise RuntimeError(
                "FILLED trade is missing filled_at."
            )

        if trade.fill_price is None:
            raise RuntimeError(
                "FILLED trade is missing fill_price."
            )

        position = self.position_repository.get_by_id(
            trade.position_id
        )

        if position is None:
            raise RuntimeError(
                "Position not found."
            )

        if position.signal_id != trade.signal_id:
            raise RuntimeError(
                "Trade/Position signal mismatch."
            )

        if (
            position.status is PositionStatus.CLOSED
            and position.closed_at is not None
        ):
            return PaperExecutionFillResult(
                trade=trade,
                position=position,
                persisted=False,
                reason="POSITION_EXIT_ALREADY_RECORDED",
            )

        if position.status is not PositionStatus.OPEN:
            raise RuntimeError(
                "Position must be OPEN before "
                "an exit fill can be recorded."
            )

        if position.opened_at is None:
            raise RuntimeError(
                "Position entry must be recorded before "
                "an exit fill can be recorded."
            )

        updated_position = (
            self.position_repository.update_status(
                position_id=position.id,
                new_status=PositionStatus.CLOSED,
                expected_status=PositionStatus.OPEN,
                closed_at=trade.filled_at,
                exit_price=trade.fill_price,
                exit_bid=trade.bid_at_action,
                exit_ask=trade.ask_at_action,
                exit_mark=trade.mark_at_action,
            )
        )

        return PaperExecutionFillResult(
            trade=trade,
            position=updated_position,
            persisted=True,
            reason="CLOSE_FILL_APPLIED",
        )
