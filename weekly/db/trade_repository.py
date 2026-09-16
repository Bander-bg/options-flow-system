from __future__ import annotations

from datetime import datetime

from weekly.db.database import (
    database_connection,
    database_transaction,
)
from weekly.domain.enums import (
    ExecutionMode,
    TradeIntent,
    TradeSide,
    TradeStatus,
)
from weekly.domain.models import Trade


def _datetime_to_db(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _datetime_from_db(
    value: str | None,
) -> datetime | None:
    if value is None:
        return None

    return datetime.fromisoformat(value)


def _row_to_trade(
    row,
) -> Trade:
    return Trade(
        id=row["id"],

        position_id=row[
            "position_id"
        ],

        signal_id=row[
            "signal_id"
        ],

        execution_mode=ExecutionMode(
            row["execution_mode"]
        ),

        intent=TradeIntent(
            row["intent"]
        ),

        side=TradeSide(
            row["side"]
        ),

        quantity=row[
            "quantity"
        ],

        requested_at=_datetime_from_db(
            row["requested_at"]
        ),

        filled_at=_datetime_from_db(
            row["filled_at"]
        ),

        fill_price=row[
            "fill_price"
        ],

        bid_at_action=row[
            "bid_at_action"
        ],

        ask_at_action=row[
            "ask_at_action"
        ],

        mark_at_action=row[
            "mark_at_action"
        ],

        options_data_provider=row[
            "options_data_provider"
        ],

        options_data_feed=row[
            "options_data_feed"
        ],

        broker_order_id=row[
            "broker_order_id"
        ],

        status=TradeStatus(
            row["status"]
        ),
    )


class TradeRepository:

    def create(
        self,
        trade: Trade,
    ) -> Trade:

        with database_transaction() as connection:

            cursor = connection.execute(
                """
                INSERT INTO trades (
                    position_id,
                    signal_id,

                    execution_mode,

                    intent,
                    side,

                    quantity,

                    requested_at,
                    filled_at,

                    fill_price,

                    bid_at_action,
                    ask_at_action,
                    mark_at_action,

                    options_data_provider,
                    options_data_feed,

                    broker_order_id,

                    status
                )
                VALUES (
                    ?, ?,
                    ?,
                    ?, ?,
                    ?,
                    ?, ?,
                    ?,
                    ?, ?, ?,
                    ?, ?,
                    ?,
                    ?
                );
                """,
                (
                    trade.position_id,
                    trade.signal_id,

                    trade.execution_mode.value,

                    trade.intent.value,
                    trade.side.value,

                    trade.quantity,

                    _datetime_to_db(
                        trade.requested_at
                    ),

                    _datetime_to_db(
                        trade.filled_at
                    ),

                    trade.fill_price,

                    trade.bid_at_action,
                    trade.ask_at_action,
                    trade.mark_at_action,

                    trade.options_data_provider,
                    trade.options_data_feed,

                    trade.broker_order_id,

                    trade.status.value,
                ),
            )

            trade_id = cursor.lastrowid

            row = connection.execute(
                """
                SELECT *
                FROM trades
                WHERE id = ?;
                """,
                (
                    trade_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Trade insert succeeded "
                "but row could not be read."
            )

        return _row_to_trade(row)

    def get_by_id(
        self,
        trade_id: int,
    ) -> Trade | None:

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM trades
                WHERE id = ?;
                """,
                (
                    trade_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_trade(row)

    def get_by_broker_order_id(
        self,
        broker_order_id: str,
    ) -> Trade | None:

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM trades
                WHERE broker_order_id = ?
                LIMIT 1;
                """,
                (
                    broker_order_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_trade(row)

    def list_for_position(
        self,
        position_id: int,
    ) -> list[Trade]:

        with database_connection() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM trades
                WHERE position_id = ?
                ORDER BY
                    requested_at ASC,
                    id ASC;
                """,
                (
                    position_id,
                ),
            ).fetchall()

        return [
            _row_to_trade(row)
            for row in rows
        ]

    def list_for_signal(
        self,
        signal_id: int,
    ) -> list[Trade]:

        with database_connection() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM trades
                WHERE signal_id = ?
                ORDER BY
                    requested_at ASC,
                    id ASC;
                """,
                (
                    signal_id,
                ),
            ).fetchall()

        return [
            _row_to_trade(row)
            for row in rows
        ]



    def list_execution_recovery_candidates(
        self,
    ) -> list[Trade]:
        """
        Return PAPER OPEN/CLOSE trades that still need
        execution lifecycle reconciliation.

        Includes:
        - REQUESTED orders with broker_order_id
        - PARTIALLY_FILLED orders with broker_order_id
        - FILLED OPEN orders whose Position entry has
          not yet been recorded (opened_at IS NULL)
        - FILLED CLOSE orders whose Position exit has
          not yet been recorded
        """

        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT t.*
                FROM trades AS t
                INNER JOIN positions AS p
                    ON p.id = t.position_id
                WHERE t.execution_mode = 'PAPER'
                  AND t.intent IN ('OPEN', 'CLOSE')
                  AND t.broker_order_id IS NOT NULL
                  AND TRIM(t.broker_order_id) <> ''
                  AND (
                        t.status IN (
                            'REQUESTED',
                            'PARTIALLY_FILLED'
                        )
                        OR (
                            t.status = 'FILLED'
                            AND t.intent = 'OPEN'
                            AND p.opened_at IS NULL
                        )
                        OR (
                            t.status = 'FILLED'
                            AND t.intent = 'CLOSE'
                            AND p.status = 'OPEN'
                            AND p.opened_at IS NOT NULL
                            AND p.closed_at IS NULL
                        )
                  )
                ORDER BY
                    t.requested_at ASC,
                    t.id ASC;
                """
            ).fetchall()

        return [
            _row_to_trade(row)
            for row in rows
        ]


    def update_status(
        self,
        *,
        trade_id: int,
        new_status: TradeStatus,
        expected_status: TradeStatus | None = None,
        broker_order_id: str | None = None,
        filled_at: datetime | None = None,
        fill_price: float | None = None,
    ) -> Trade:
        if trade_id < 1:
            raise ValueError(
                "trade_id must be >= 1"
            )

        if (
            broker_order_id is not None
            and not broker_order_id.strip()
        ):
            raise ValueError(
                "broker_order_id cannot be empty"
            )

        if (
            filled_at is not None
            and filled_at.tzinfo is None
        ):
            raise ValueError(
                "filled_at must be timezone-aware"
            )

        if (
            fill_price is not None
            and fill_price < 0
        ):
            raise ValueError(
                "fill_price cannot be negative"
            )

        params = {
            "trade_id": trade_id,
            "new_status": new_status.value,
            "expected_status": (
                expected_status.value
                if expected_status is not None
                else None
            ),
            "broker_order_id": broker_order_id,
            "filled_at": _datetime_to_db(
                filled_at
            ),
            "fill_price": fill_price,
        }

        with database_transaction() as connection:
            if expected_status is None:
                cursor = connection.execute(
                    """
                    UPDATE trades
                    SET
                        status = :new_status,
                        broker_order_id = COALESCE(
                            :broker_order_id,
                            broker_order_id
                        ),
                        filled_at = COALESCE(
                            :filled_at,
                            filled_at
                        ),
                        fill_price = COALESCE(
                            :fill_price,
                            fill_price
                        )
                    WHERE id = :trade_id;
                    """,
                    params,
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE trades
                    SET
                        status = :new_status,
                        broker_order_id = COALESCE(
                            :broker_order_id,
                            broker_order_id
                        ),
                        filled_at = COALESCE(
                            :filled_at,
                            filled_at
                        ),
                        fill_price = COALESCE(
                            :fill_price,
                            fill_price
                        )
                    WHERE id = :trade_id
                      AND status = :expected_status;
                    """,
                    params,
                )

            if cursor.rowcount != 1:
                if expected_status is None:
                    raise RuntimeError(
                        "Trade status update failed: "
                        "trade not found."
                    )

                raise RuntimeError(
                    "Trade status update failed: "
                    "trade not found or current status "
                    "does not match expected_status."
                )

            row = connection.execute(
                """
                SELECT *
                FROM trades
                WHERE id = ?;
                """,
                (
                    trade_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Trade status update succeeded "
                "but the updated row could not be read."
            )

        return _row_to_trade(row)
