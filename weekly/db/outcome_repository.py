from __future__ import annotations

from datetime import datetime

from weekly.db.database import (
    database_connection,
    database_transaction,
)
from weekly.domain.enums import (
    OutcomeScope,
    OutcomeStatus,
)
from weekly.domain.models import Outcome


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


def _row_to_outcome(
    row,
) -> Outcome:
    return Outcome(
        id=row["id"],

        signal_id=row["signal_id"],

        outcome_scope=OutcomeScope(
            row["outcome_scope"]
        ),

        checkpoint_name=row[
            "checkpoint_name"
        ],

        outcome_status=OutcomeStatus(
            row["outcome_status"]
        ),

        scheduled_at=_datetime_from_db(
            row["scheduled_at"]
        ),

        observed_at=_datetime_from_db(
            row["observed_at"]
        ),

        baseline_at=_datetime_from_db(
            row["baseline_at"]
        ),

        baseline_underlying_price=row[
            "baseline_underlying_price"
        ],

        observed_underlying_price=row[
            "observed_underlying_price"
        ],

        underlying_raw_return=row[
            "underlying_raw_return"
        ],

        underlying_directional_return=row[
            "underlying_directional_return"
        ],

        contract_symbol=row[
            "contract_symbol"
        ],

        baseline_option_bid=row[
            "baseline_option_bid"
        ],

        baseline_option_ask=row[
            "baseline_option_ask"
        ],

        baseline_option_mark=row[
            "baseline_option_mark"
        ],

        observed_option_bid=row[
            "observed_option_bid"
        ],

        observed_option_ask=row[
            "observed_option_ask"
        ],

        observed_option_mark=row[
            "observed_option_mark"
        ],

        option_executable_return=row[
            "option_executable_return"
        ],

        option_mark_return=row[
            "option_mark_return"
        ],

        settlement_value=row[
            "settlement_value"
        ],

        stock_data_provider=row[
            "stock_data_provider"
        ],

        stock_data_feed=row[
            "stock_data_feed"
        ],

        options_data_provider=row[
            "options_data_provider"
        ],

        options_data_feed=row[
            "options_data_feed"
        ],
    )


class OutcomeRepository:

    def create(
        self,
        outcome: Outcome,
    ) -> Outcome:

        with database_transaction() as connection:

            cursor = connection.execute(
                """
                INSERT INTO outcomes (
                    signal_id,
                    outcome_scope,
                    checkpoint_name,

                    scheduled_at,
                    observed_at,
                    baseline_at,

                    baseline_underlying_price,
                    observed_underlying_price,

                    underlying_raw_return,
                    underlying_directional_return,

                    contract_symbol,

                    baseline_option_bid,
                    baseline_option_ask,
                    baseline_option_mark,

                    observed_option_bid,
                    observed_option_ask,
                    observed_option_mark,

                    option_executable_return,
                    option_mark_return,

                    settlement_value,

                    stock_data_provider,
                    stock_data_feed,

                    options_data_provider,
                    options_data_feed,

                    outcome_status
                )
                VALUES (
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?,
                    ?, ?,
                    ?, ?,
                    ?
                );
                """,
                (
                    outcome.signal_id,
                    outcome.outcome_scope.value,
                    outcome.checkpoint_name,

                    _datetime_to_db(
                        outcome.scheduled_at
                    ),

                    _datetime_to_db(
                        outcome.observed_at
                    ),

                    _datetime_to_db(
                        outcome.baseline_at
                    ),

                    outcome.baseline_underlying_price,
                    outcome.observed_underlying_price,

                    outcome.underlying_raw_return,
                    outcome.underlying_directional_return,

                    outcome.contract_symbol,

                    outcome.baseline_option_bid,
                    outcome.baseline_option_ask,
                    outcome.baseline_option_mark,

                    outcome.observed_option_bid,
                    outcome.observed_option_ask,
                    outcome.observed_option_mark,

                    outcome.option_executable_return,
                    outcome.option_mark_return,

                    outcome.settlement_value,

                    outcome.stock_data_provider,
                    outcome.stock_data_feed,

                    outcome.options_data_provider,
                    outcome.options_data_feed,

                    outcome.outcome_status.value,
                ),
            )

            outcome_id = cursor.lastrowid

            row = connection.execute(
                """
                SELECT *
                FROM outcomes
                WHERE id = ?;
                """,
                (
                    outcome_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Outcome insert succeeded "
                "but row could not be read."
            )

        return _row_to_outcome(row)

    def get_by_id(
        self,
        outcome_id: int,
    ) -> Outcome | None:

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM outcomes
                WHERE id = ?;
                """,
                (
                    outcome_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_outcome(row)

    def get_by_key(
        self,
        *,
        signal_id: int,
        outcome_scope: OutcomeScope,
        checkpoint_name: str,
    ) -> Outcome | None:

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM outcomes
                WHERE signal_id = ?
                  AND outcome_scope = ?
                  AND checkpoint_name = ?
                LIMIT 1;
                """,
                (
                    signal_id,
                    outcome_scope.value,
                    checkpoint_name,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_outcome(row)

    def list_for_signal(
        self,
        signal_id: int,
    ) -> list[Outcome]:

        with database_connection() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM outcomes
                WHERE signal_id = ?
                ORDER BY
                    outcome_scope ASC,
                    scheduled_at ASC,
                    checkpoint_name ASC;
                """,
                (
                    signal_id,
                ),
            ).fetchall()

        return [
            _row_to_outcome(row)
            for row in rows
        ]