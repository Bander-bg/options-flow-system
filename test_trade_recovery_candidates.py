from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from weekly.db.position_repository import PositionRepository
from weekly.db.signal_repository import SignalRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import (
    PositionStatus,
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


ET = ZoneInfo("America/New_York")


def ids(rows):
    return tuple(row.id for row in rows)


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
            replace(
                make_position(signal.id),
                opened_at=None,
                entry_price=None,
                entry_bid=None,
                entry_ask=None,
                entry_mark=None,
            )
        )
        assert position.id is not None

        # ------------------------------------------
        # OPEN recovery candidates
        # ------------------------------------------

        open_requested = trade_repository.create(
            replace(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id="recover-open-requested",
                    minute=20,
                ),
                status=TradeStatus.REQUESTED,
                filled_at=None,
                fill_price=None,
            )
        )

        open_partial = trade_repository.create(
            replace(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id="recover-open-partial",
                    minute=21,
                ),
                status=TradeStatus.PARTIALLY_FILLED,
                filled_at=None,
                fill_price=None,
            )
        )

        open_filled = trade_repository.create(
            make_trade(
                position_id=position.id,
                signal_id=signal.id,
                intent=TradeIntent.OPEN,
                side=TradeSide.BUY,
                broker_order_id="recover-open-filled",
                minute=22,
            )
        )

        no_broker = trade_repository.create(
            replace(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id=None,
                    minute=23,
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

        assert ids(candidates) == (
            open_requested.id,
            open_partial.id,
            open_filled.id,
        )

        assert no_broker.id not in ids(candidates)

        print(
            "1. OPEN recovery candidates: PASS"
        )

        # Record the Position entry.
        position_repository.update_entry(
            position_id=position.id,
            opened_at=datetime(
                2026, 9, 4, 10, 30,
                tzinfo=ET,
            ),
            entry_price=5.00,
            entry_bid=4.80,
            entry_ask=5.00,
            entry_mark=4.90,
        )

        candidates = (
            trade_repository
            .list_execution_recovery_candidates()
        )

        assert open_filled.id not in ids(candidates)

        print(
            "2. applied OPEN fill excluded: PASS"
        )

        # ------------------------------------------
        # CLOSE recovery candidates
        # ------------------------------------------

        close_requested = trade_repository.create(
            replace(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.CLOSE,
                    side=TradeSide.SELL,
                    broker_order_id="recover-close-requested",
                    minute=40,
                ),
                status=TradeStatus.REQUESTED,
                filled_at=None,
                fill_price=None,
            )
        )

        close_partial = trade_repository.create(
            replace(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.CLOSE,
                    side=TradeSide.SELL,
                    broker_order_id="recover-close-partial",
                    minute=41,
                ),
                status=TradeStatus.PARTIALLY_FILLED,
                filled_at=None,
                fill_price=None,
            )
        )

        close_filled = trade_repository.create(
            make_trade(
                position_id=position.id,
                signal_id=signal.id,
                intent=TradeIntent.CLOSE,
                side=TradeSide.SELL,
                broker_order_id="recover-close-filled",
                minute=42,
            )
        )

        cancelled = trade_repository.create(
            replace(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.CLOSE,
                    side=TradeSide.SELL,
                    broker_order_id="recover-close-cancelled",
                    minute=43,
                ),
                status=TradeStatus.CANCELLED,
                filled_at=None,
                fill_price=None,
            )
        )

        candidates = (
            trade_repository
            .list_execution_recovery_candidates()
        )

        candidate_ids = ids(candidates)

        assert open_requested.id in candidate_ids
        assert open_partial.id in candidate_ids

        assert close_requested.id in candidate_ids
        assert close_partial.id in candidate_ids
        assert close_filled.id in candidate_ids

        assert cancelled.id not in candidate_ids
        assert no_broker.id not in candidate_ids

        print(
            "3. CLOSE recovery candidates: PASS"
        )

        # Record the Position exit.
        position_repository.update_status(
            position_id=position.id,
            new_status=PositionStatus.CLOSED,
            expected_status=PositionStatus.OPEN,
            closed_at=close_filled.filled_at,
            exit_price=close_filled.fill_price,
            exit_bid=close_filled.bid_at_action,
            exit_ask=close_filled.ask_at_action,
            exit_mark=close_filled.mark_at_action,
        )

        candidates = (
            trade_repository
            .list_execution_recovery_candidates()
        )

        assert close_filled.id not in ids(candidates)

        print(
            "4. applied CLOSE fill excluded: PASS"
        )
        print(
            "5. broker/status guards preserved: PASS"
        )
        print()
        print(
            "TRADE RECOVERY CANDIDATES: PASS 5/5"
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
