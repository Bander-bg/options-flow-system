from __future__ import annotations

from datetime import date, datetime

from weekly.db.database import (
    database_connection,
    database_transaction,
)
from weekly.domain.enums import (
    ExecutionMode,
    OptionRight,
    PositionStatus,
)
from weekly.domain.models import Position


def _date_to_db(
    value: date | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _datetime_to_db(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _date_from_db(
    value: str | None,
) -> date | None:
    if value is None:
        return None

    return date.fromisoformat(value)


def _datetime_from_db(
    value: str | None,
) -> datetime | None:
    if value is None:
        return None

    return datetime.fromisoformat(value)


def _row_to_position(
    row,
) -> Position:
    return Position(
        id=row["id"],

        signal_id=row["signal_id"],

        execution_mode=ExecutionMode(
            row["execution_mode"]
        ),

        contract_symbol=row[
            "contract_symbol"
        ],

        option_right=OptionRight(
            row["option_right"]
        ),

        strike=row["strike"],

        expiry=_date_from_db(
            row["expiry"]
        ),

        quantity=row["quantity"],

        status=PositionStatus(
            row["status"]
        ),

        opened_at=_datetime_from_db(
            row["opened_at"]
        ),

        closed_at=_datetime_from_db(
            row["closed_at"]
        ),

        entry_price=row[
            "entry_price"
        ],

        exit_price=row[
            "exit_price"
        ],

        entry_bid=row[
            "entry_bid"
        ],

        entry_ask=row[
            "entry_ask"
        ],

        entry_mark=row[
            "entry_mark"
        ],

        exit_bid=row[
            "exit_bid"
        ],

        exit_ask=row[
            "exit_ask"
        ],

        exit_mark=row[
            "exit_mark"
        ],
    )


class PositionRepository:

    def create(
        self,
        position: Position,
    ) -> Position:

        with database_transaction() as connection:

            cursor = connection.execute(
                """
                INSERT INTO positions (
                    signal_id,
                    execution_mode,

                    contract_symbol,
                    option_right,
                    strike,
                    expiry,

                    quantity,
                    status,

                    opened_at,
                    closed_at,

                    entry_price,
                    exit_price,

                    entry_bid,
                    entry_ask,
                    entry_mark,

                    exit_bid,
                    exit_ask,
                    exit_mark
                )
                VALUES (
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?
                );
                """,
                (
                    position.signal_id,
                    position.execution_mode.value,

                    position.contract_symbol,
                    position.option_right.value,
                    position.strike,
                    _date_to_db(
                        position.expiry
                    ),

                    position.quantity,
                    position.status.value,

                    _datetime_to_db(
                        position.opened_at
                    ),

                    _datetime_to_db(
                        position.closed_at
                    ),

                    position.entry_price,
                    position.exit_price,

                    position.entry_bid,
                    position.entry_ask,
                    position.entry_mark,

                    position.exit_bid,
                    position.exit_ask,
                    position.exit_mark,
                ),
            )

            position_id = cursor.lastrowid

            row = connection.execute(
                """
                SELECT *
                FROM positions
                WHERE id = ?;
                """,
                (
                    position_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Position insert succeeded "
                "but row could not be read."
            )

        return _row_to_position(row)

    def get_by_id(
        self,
        position_id: int,
    ) -> Position | None:

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM positions
                WHERE id = ?;
                """,
                (
                    position_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_position(row)

    def list_for_signal(
        self,
        signal_id: int,
    ) -> list[Position]:

        with database_connection() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM positions
                WHERE signal_id = ?
                ORDER BY id ASC;
                """,
                (
                    signal_id,
                ),
            ).fetchall()

        return [
            _row_to_position(row)
            for row in rows
        ]

    def list_open(
        self,
    ) -> list[Position]:

        with database_connection() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM positions
                WHERE status = 'OPEN'
                ORDER BY opened_at ASC, id ASC;
                """
            ).fetchall()

        return [
            _row_to_position(row)
            for row in rows
        ]

    def get_open_for_signal(
        self,
        signal_id: int,
    ) -> Position | None:

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM positions
                WHERE signal_id = ?
                  AND status = 'OPEN'
                ORDER BY id DESC
                LIMIT 1;
                """,
                (
                    signal_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_position(row)


    def update_status(
        self,
        *,
        position_id: int,
        new_status: PositionStatus,
        expected_status: PositionStatus | None = None,
        closed_at: datetime | None = None,
        exit_price: float | None = None,
        exit_bid: float | None = None,
        exit_ask: float | None = None,
        exit_mark: float | None = None,
    ) -> Position:
        if position_id < 1:
            raise ValueError(
                "position_id must be >= 1"
            )

        if (
            closed_at is not None
            and closed_at.tzinfo is None
        ):
            raise ValueError(
                "closed_at must be timezone-aware"
            )

        for name, value in (
            ("exit_price", exit_price),
            ("exit_bid", exit_bid),
            ("exit_ask", exit_ask),
            ("exit_mark", exit_mark),
        ):
            if (
                value is not None
                and value < 0
            ):
                raise ValueError(
                    f"{name} cannot be negative"
                )

        params = {
            "position_id": position_id,
            "new_status": new_status.value,
            "expected_status": (
                expected_status.value
                if expected_status is not None
                else None
            ),
            "closed_at": _datetime_to_db(
                closed_at
            ),
            "exit_price": exit_price,
            "exit_bid": exit_bid,
            "exit_ask": exit_ask,
            "exit_mark": exit_mark,
        }

        with database_transaction() as connection:
            if expected_status is None:
                cursor = connection.execute(
                    """
                    UPDATE positions
                    SET
                        status = :new_status,
                        closed_at = COALESCE(
                            :closed_at,
                            closed_at
                        ),
                        exit_price = COALESCE(
                            :exit_price,
                            exit_price
                        ),
                        exit_bid = COALESCE(
                            :exit_bid,
                            exit_bid
                        ),
                        exit_ask = COALESCE(
                            :exit_ask,
                            exit_ask
                        ),
                        exit_mark = COALESCE(
                            :exit_mark,
                            exit_mark
                        ),
                        updated_at = strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    WHERE id = :position_id;
                    """,
                    params,
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE positions
                    SET
                        status = :new_status,
                        closed_at = COALESCE(
                            :closed_at,
                            closed_at
                        ),
                        exit_price = COALESCE(
                            :exit_price,
                            exit_price
                        ),
                        exit_bid = COALESCE(
                            :exit_bid,
                            exit_bid
                        ),
                        exit_ask = COALESCE(
                            :exit_ask,
                            exit_ask
                        ),
                        exit_mark = COALESCE(
                            :exit_mark,
                            exit_mark
                        ),
                        updated_at = strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    WHERE id = :position_id
                      AND status = :expected_status;
                    """,
                    params,
                )

            if cursor.rowcount != 1:
                if expected_status is None:
                    raise RuntimeError(
                        "Position status update failed: "
                        "position not found."
                    )

                raise RuntimeError(
                    "Position status update failed: "
                    "position not found or current status "
                    "does not match expected_status."
                )

            row = connection.execute(
                """
                SELECT *
                FROM positions
                WHERE id = ?;
                """,
                (
                    position_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Position status update succeeded "
                "but the updated row could not be read."
            )

        return _row_to_position(row)


    def update_entry(
        self,
        *,
        position_id: int,
        opened_at: datetime,
        entry_price: float,
        entry_bid: float | None = None,
        entry_ask: float | None = None,
        entry_mark: float | None = None,
    ) -> Position:
        if position_id < 1:
            raise ValueError(
                "position_id must be >= 1"
            )

        if opened_at.tzinfo is None:
            raise ValueError(
                "opened_at must be timezone-aware"
            )

        for name, value in (
            ("entry_price", entry_price),
            ("entry_bid", entry_bid),
            ("entry_ask", entry_ask),
            ("entry_mark", entry_mark),
        ):
            if value is not None and value < 0:
                raise ValueError(
                    f"{name} cannot be negative"
                )

        params = {
            "position_id": position_id,
            "opened_at": _datetime_to_db(
                opened_at
            ),
            "entry_price": entry_price,
            "entry_bid": entry_bid,
            "entry_ask": entry_ask,
            "entry_mark": entry_mark,
        }

        with database_transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE positions
                SET
                    opened_at = :opened_at,
                    entry_price = :entry_price,
                    entry_bid = COALESCE(
                        :entry_bid,
                        entry_bid
                    ),
                    entry_ask = COALESCE(
                        :entry_ask,
                        entry_ask
                    ),
                    entry_mark = COALESCE(
                        :entry_mark,
                        entry_mark
                    ),
                    updated_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = :position_id
                  AND status = 'OPEN'
                  AND opened_at IS NULL;
                """,
                params,
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Position entry update failed: "
                    "position not found, not OPEN, "
                    "or entry was already recorded."
                )

            row = connection.execute(
                """
                SELECT *
                FROM positions
                WHERE id = ?;
                """,
                (
                    position_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Position entry update succeeded "
                "but the updated row could not be read."
            )

        return _row_to_position(row)
