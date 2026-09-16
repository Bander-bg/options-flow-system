from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from weekly.db.position_repository import PositionRepository
from weekly.db.signal_repository import SignalRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import (
    TradeIntent,
    TradeSide,
    TradeStatus,
)

from test_trade_repository import (
    TEMP_DB,
    create_temp_database,
    make_position,
    make_signal,
    make_trade,
    patch_repositories,
)


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

        def pending_position():
            return position_repository.create(
                replace(
                    make_position(signal.id),
                    opened_at=None,
                    entry_price=None,
                    entry_bid=None,
                    entry_ask=None,
                    entry_mark=None,
                )
            )

        p_requested = pending_position()
        p_partial = pending_position()
        p_filled_unapplied = pending_position()

        p_filled_applied = (
            position_repository.create(
                make_position(signal.id)
            )
        )

        p_no_broker = pending_position()

        for position in (
            p_requested,
            p_partial,
            p_filled_unapplied,
            p_filled_applied,
            p_no_broker,
        ):
            assert position.id is not None

        requested = trade_repository.create(
            replace(
                make_trade(
                    position_id=p_requested.id,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id="recovery-requested",
                    minute=21,
                ),
                status=TradeStatus.REQUESTED,
                filled_at=None,
                fill_price=None,
            )
        )

        partial = trade_repository.create(
            replace(
                make_trade(
                    position_id=p_partial.id,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id="recovery-partial",
                    minute=22,
                ),
                status=TradeStatus.PARTIALLY_FILLED,
                filled_at=None,
                fill_price=None,
            )
        )

        filled_unapplied = trade_repository.create(
            make_trade(
                position_id=p_filled_unapplied.id,
                signal_id=signal.id,
                intent=TradeIntent.OPEN,
                side=TradeSide.BUY,
                broker_order_id="recovery-filled-unapplied",
                minute=23,
            )
        )

        trade_repository.create(
            make_trade(
                position_id=p_filled_applied.id,
                signal_id=signal.id,
                intent=TradeIntent.OPEN,
                side=TradeSide.BUY,
                broker_order_id="recovery-filled-applied",
                minute=24,
            )
        )

        trade_repository.create(
            replace(
                make_trade(
                    position_id=p_no_broker.id,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id=None,
                    minute=25,
                ),
                status=TradeStatus.REQUESTED,
                filled_at=None,
                fill_price=None,
            )
        )

        candidates = (
            trade_repository
            .list_execution_recovery_candidates()
        )

        assert tuple(
            trade.id
            for trade in candidates
        ) == (
            requested.id,
            partial.id,
            filled_unapplied.id,
        )

        assert tuple(
            trade.status
            for trade in candidates
        ) == (
            TradeStatus.REQUESTED,
            TradeStatus.PARTIALLY_FILLED,
            TradeStatus.FILLED,
        )

        print(
            "TRADE EXECUTION RECOVERY QUERY: PASS"
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
