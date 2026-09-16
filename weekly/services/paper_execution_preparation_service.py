from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math

from weekly.db.position_repository import PositionRepository
from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import (
    ExecutionMode,
    GateStatus,
    PositionStatus,
    SignalState,
    TradeIntent,
    TradeSide,
    TradeStatus,
)
from weekly.domain.models import Position, Trade


@dataclass(frozen=True)
class PaperExecutionPreparationResult:
    position: Position
    trade: Trade


class PaperExecutionPreparationService:
    """
    Prepare PAPER execution records only.

    This service does NOT:
    - choose position size
    - choose Market vs Limit
    - construct an Alpaca OrderRequest
    - submit an order
    - transition CONFIRMED -> ACTIVE

    The caller must provide quantity explicitly.
    """

    def __init__(
        self,
        *,
        signal_repository: SignalRepository,
        signal_feature_repository: SignalFeatureRepository,
        position_repository: PositionRepository,
        trade_repository: TradeRepository,
        options_provider=None,
    ):
        self.signal_repository = signal_repository
        self.signal_feature_repository = (
            signal_feature_repository
        )
        self.position_repository = position_repository
        self.trade_repository = trade_repository
        self.options_provider = options_provider

    def prepare(
        self,
        *,
        signal_id: int,
        quantity: int,
        requested_at: datetime,
    ) -> PaperExecutionPreparationResult:
        if signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        if quantity <= 0:
            raise ValueError(
                "quantity must be > 0"
            )

        if requested_at.tzinfo is None:
            raise ValueError(
                "requested_at must be timezone-aware"
            )

        signal = self.signal_repository.get_by_id(
            signal_id
        )

        if signal is None:
            raise RuntimeError(
                "Signal not found."
            )

        if signal.state is not SignalState.CONFIRMED:
            raise RuntimeError(
                "Only CONFIRMED signals may be "
                "prepared for PAPER execution."
            )

        existing_position = (
            self.position_repository
            .get_open_for_signal(signal_id)
        )

        if existing_position is not None:
            raise RuntimeError(
                "Signal already has an OPEN position."
            )

        feature = (
            self.signal_feature_repository
            .get_latest_for_signal(signal_id)
        )

        if feature is None:
            raise RuntimeError(
                "Latest SignalFeature not found."
            )

        if (
            feature.eligible_contract_status
            is not GateStatus.PASS
        ):
            raise RuntimeError(
                "Latest eligible contract evaluation "
                "is not PASS."
            )

        if feature.selected_contract_symbol is None:
            raise RuntimeError(
                "Selected contract symbol is unavailable."
            )

        if feature.selected_contract_right is None:
            raise RuntimeError(
                "Selected contract right is unavailable."
            )

        if feature.selected_contract_strike is None:
            raise RuntimeError(
                "Selected contract strike is unavailable."
            )

        position = self.position_repository.create(
            Position(
                signal_id=signal_id,
                contract_symbol=(
                    feature.selected_contract_symbol
                ),
                option_right=(
                    feature.selected_contract_right
                ),
                strike=(
                    feature.selected_contract_strike
                ),
                expiry=signal.target_expiry,
                quantity=quantity,
                status=PositionStatus.OPEN,
                execution_mode=ExecutionMode.PAPER,
                opened_at=None,
                entry_price=None,
                entry_bid=None,
                entry_ask=None,
                entry_mark=None,
            )
        )

        if position.id is None:
            raise RuntimeError(
                "Prepared Position id is missing."
            )

        trade = self.trade_repository.create(
            Trade(
                position_id=position.id,
                signal_id=signal_id,
                intent=TradeIntent.OPEN,
                side=TradeSide.BUY,
                quantity=quantity,
                requested_at=requested_at,
                status=TradeStatus.REQUESTED,
                execution_mode=ExecutionMode.PAPER,
                filled_at=None,
                fill_price=None,
                bid_at_action=(
                    feature.selected_contract_bid
                ),
                ask_at_action=(
                    feature.selected_contract_ask
                ),
                mark_at_action=(
                    feature.selected_contract_mark
                ),
                options_data_provider=(
                    signal.options_data_provider
                ),
                options_data_feed=(
                    signal.options_data_feed
                ),
                broker_order_id=None,
            )
        )

        return PaperExecutionPreparationResult(
            position=position,
            trade=trade,
        )


    def prepare_close(
        self,
        *,
        position_id: int,
        requested_at: datetime,
    ) -> PaperExecutionPreparationResult:
        """
        Prepare a PAPER CLOSE/SELL trade for the full
        quantity of an already-open Position.

        This method does NOT:
        - choose when to exit
        - choose Market vs Limit
        - submit an order
        - partially close a Position
        - transition Signal state
        """
        if position_id < 1:
            raise ValueError(
                "position_id must be >= 1"
            )

        if requested_at.tzinfo is None:
            raise ValueError(
                "requested_at must be timezone-aware"
            )

        position = self.position_repository.get_by_id(
            position_id
        )

        if position is None:
            raise RuntimeError(
                "Position not found."
            )

        if position.status is not PositionStatus.OPEN:
            raise RuntimeError(
                "Only OPEN positions may be prepared "
                "for PAPER close execution."
            )

        if position.opened_at is None:
            raise RuntimeError(
                "Position entry must be recorded before "
                "a close trade can be prepared."
            )

        signal = self.signal_repository.get_by_id(
            position.signal_id
        )

        if signal is None:
            raise RuntimeError(
                "Signal not found."
            )

        existing_trades = (
            self.trade_repository
            .list_for_position(position.id)
        )

        has_unfinished_or_filled_close = any(
            trade.intent is TradeIntent.CLOSE
            and trade.status in (
                TradeStatus.REQUESTED,
                TradeStatus.PARTIALLY_FILLED,
                TradeStatus.FILLED,
            )
            for trade in existing_trades
        )

        if has_unfinished_or_filled_close:
            raise RuntimeError(
                "Position already has an active or "
                "filled CLOSE execution."
            )

        if self.options_provider is None:
            raise RuntimeError(
                "Options provider is required to "
                "prepare a PAPER close trade."
            )

        quote_result = (
            self.options_provider
            .get_contract_candidates(
                ticker=signal.ticker,
                target_expiry=position.expiry,
            )
        )

        contract = next(
            (
                candidate
                for candidate in quote_result.candidates
                if candidate.symbol
                == position.contract_symbol
            ),
            None,
        )

        if contract is None:
            raise RuntimeError(
                "Open position contract was not found "
                "in the current option chain."
            )

        if (
            contract.bid is None
            or contract.ask is None
        ):
            raise RuntimeError(
                "Current option quote is unavailable "
                "for the open position contract."
            )

        bid = float(contract.bid)
        ask = float(contract.ask)

        if (
            not math.isfinite(bid)
            or not math.isfinite(ask)
            or bid < 0
            or ask < 0
            or ask < bid
        ):
            raise RuntimeError(
                "Current option quote is invalid."
            )

        mark = (bid + ask) / 2.0

        if not math.isfinite(mark) or mark < 0:
            raise RuntimeError(
                "Current option mark is invalid."
            )

        trade = self.trade_repository.create(
            Trade(
                position_id=position.id,
                signal_id=position.signal_id,
                intent=TradeIntent.CLOSE,
                side=TradeSide.SELL,
                quantity=position.quantity,
                requested_at=requested_at,
                status=TradeStatus.REQUESTED,
                execution_mode=ExecutionMode.PAPER,
                filled_at=None,
                fill_price=None,
                bid_at_action=bid,
                ask_at_action=ask,
                mark_at_action=mark,
                options_data_provider=(
                    quote_result.provider
                ),
                options_data_feed=(
                    quote_result.feed
                ),
                broker_order_id=None,
            )
        )

        return PaperExecutionPreparationResult(
            position=position,
            trade=trade,
        )
