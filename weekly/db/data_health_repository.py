from __future__ import annotations

from datetime import date, datetime

from weekly.db.database import (
    database_connection,
    database_transaction,
)
from weekly.domain.enums import (
    DataHealthStatus,
)
from weekly.domain.models import (
    DataHealth,
)


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


def _row_to_data_health(
    row,
) -> DataHealth:
    return DataHealth(
        id=row["id"],

        captured_at=_datetime_from_db(
            row["captured_at"]
        ),

        trading_date_et=_date_from_db(
            row["trading_date_et"]
        ),

        ticker=row["ticker"],

        component=row[
            "component"
        ],

        status=DataHealthStatus(
            row["status"]
        ),

        provider=row[
            "provider"
        ],

        feed=row[
            "feed"
        ],

        message=row[
            "message"
        ],
    )


class DataHealthRepository:

    def create(
        self,
        health: DataHealth,
    ) -> DataHealth:

        with database_transaction() as connection:

            cursor = connection.execute(
                """
                INSERT INTO data_health (
                    captured_at,
                    trading_date_et,
                    ticker,

                    component,
                    status,

                    provider,
                    feed,

                    message
                )
                VALUES (
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?
                );
                """,
                (
                    _datetime_to_db(
                        health.captured_at
                    ),

                    _date_to_db(
                        health.trading_date_et
                    ),

                    health.ticker,

                    health.component,
                    health.status.value,

                    health.provider,
                    health.feed,

                    health.message,
                ),
            )

            health_id = cursor.lastrowid

            row = connection.execute(
                """
                SELECT *
                FROM data_health
                WHERE id = ?;
                """,
                (
                    health_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "DataHealth insert succeeded "
                "but row could not be read."
            )

        return _row_to_data_health(row)

    def get_by_id(
        self,
        health_id: int,
    ) -> DataHealth | None:

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM data_health
                WHERE id = ?;
                """,
                (
                    health_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_data_health(row)

    def get_latest_for_component(
        self,
        *,
        component: str,
        ticker: str | None = None,
    ) -> DataHealth | None:

        with database_connection() as connection:

            if ticker is None:
                row = connection.execute(
                    """
                    SELECT *
                    FROM data_health
                    WHERE component = ?
                    ORDER BY
                        captured_at DESC,
                        id DESC
                    LIMIT 1;
                    """,
                    (
                        component,
                    ),
                ).fetchone()

            else:
                row = connection.execute(
                    """
                    SELECT *
                    FROM data_health
                    WHERE component = ?
                      AND ticker = ?
                    ORDER BY
                        captured_at DESC,
                        id DESC
                    LIMIT 1;
                    """,
                    (
                        component,
                        ticker,
                    ),
                ).fetchone()

        if row is None:
            return None

        return _row_to_data_health(row)

    def list_latest(
        self,
        *,
        limit: int = 100,
    ) -> list[DataHealth]:

        if limit < 1:
            raise ValueError(
                "limit must be >= 1"
            )

        with database_connection() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM data_health
                ORDER BY
                    captured_at DESC,
                    id DESC
                LIMIT ?;
                """,
                (
                    limit,
                ),
            ).fetchall()

        return [
            _row_to_data_health(row)
            for row in rows
        ]