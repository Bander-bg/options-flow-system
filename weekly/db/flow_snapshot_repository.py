from __future__ import annotations

from datetime import date, datetime

from weekly.db.database import (
    database_connection,
    database_transaction,
)
from weekly.domain.models import (
    FlowSnapshot,
)


def _serialize_date(
    value: date,
) -> str:
    return value.isoformat()


def _serialize_datetime(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        raise ValueError(
            "datetime must be timezone-aware"
        )

    return value.isoformat()


def _parse_date(
    value: str,
) -> date:
    return date.fromisoformat(
        value
    )


def _parse_datetime(
    value: str | None,
) -> datetime | None:
    if value is None:
        return None

    parsed = datetime.fromisoformat(
        value
    )

    if parsed.tzinfo is None:
        raise ValueError(
            "Stored datetime must be "
            "timezone-aware"
        )

    return parsed


def _row_to_model(
    row,
) -> FlowSnapshot:
    return FlowSnapshot(
        ticker=row["ticker"],

        trading_date_et=_parse_date(
            row["trading_date_et"]
        ),

        captured_at=_parse_datetime(
            row["captured_at"]
        ),

        target_expiry=_parse_date(
            row["target_expiry"]
        ),

        call_ask_premium=float(
            row["call_ask_premium"]
        ),

        put_ask_premium=float(
            row["put_ask_premium"]
        ),

        net_flow=float(
            row["net_flow"]
        ),

        call_bid_premium=float(
            row["call_bid_premium"]
        ),

        put_bid_premium=float(
            row["put_bid_premium"]
        ),

        bullish_premium=float(
            row["bullish_premium"]
        ),

        bearish_premium=float(
            row["bearish_premium"]
        ),

        directional_net=float(
            row["directional_net"]
        ),

        raw_alert_count=int(
            row["raw_alert_count"]
        ),

        clean_alert_count=int(
            row["clean_alert_count"]
        ),

        deduped_alert_count=int(
            row["deduped_alert_count"]
        ),

        flow_dedup_level=(
            row["flow_dedup_level"]
        ),

        trade_overlap_detected=bool(
            row[
                "trade_overlap_detected"
            ]
        ),

        sweep_alert_count=int(
            row["sweep_alert_count"]
        ),

        opening_alert_count=int(
            row["opening_alert_count"]
        ),

        total_premium=(
            None
            if row["total_premium"] is None
            else float(row["total_premium"])
        ),

        sweep_premium=(
            None
            if row["sweep_premium"] is None
            else float(row["sweep_premium"])
        ),

        provider=row["provider"],

        feed=row["feed"],

        source_timestamp=(
            _parse_datetime(
                row["source_timestamp"]
            )
        ),

        fetched_at=(
            _parse_datetime(
                row["fetched_at"]
            )
        ),

        freshness_status=(
            row["freshness_status"]
        ),

        id=int(
            row["id"]
        ),
    )


class FlowSnapshotRepository:

    def create(
        self,
        snapshot: FlowSnapshot,
    ) -> FlowSnapshot:
        """
        Persist one immutable flow snapshot.

        Legacy columns are still populated for
        backwards database compatibility:

        alert_count
            <- deduped_alert_count

        source_provider
            <- provider
        """

        with database_transaction() as conn:

            cursor = conn.execute(
                """
                INSERT INTO flow_snapshots (
                    ticker,
                    trading_date_et,
                    captured_at,
                    target_expiry,

                    call_ask_premium,
                    put_ask_premium,
                    net_flow,

                    alert_count,
                    flow_dedup_level,
                    source_provider,

                    call_bid_premium,
                    put_bid_premium,

                    bullish_premium,
                    bearish_premium,
                    directional_net,

                    raw_alert_count,
                    clean_alert_count,
                    deduped_alert_count,

                    trade_overlap_detected,

                    sweep_alert_count,
                    opening_alert_count,

                    total_premium,
                    sweep_premium,

                    provider,
                    feed,

                    source_timestamp,
                    fetched_at,
                    freshness_status
                )
                VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?
                )
                """,
                (
                    snapshot.ticker,

                    _serialize_date(
                        snapshot.trading_date_et
                    ),

                    _serialize_datetime(
                        snapshot.captured_at
                    ),

                    _serialize_date(
                        snapshot.target_expiry
                    ),

                    snapshot.call_ask_premium,
                    snapshot.put_ask_premium,
                    snapshot.net_flow,

                    # Legacy compatibility.
                    snapshot.deduped_alert_count,

                    snapshot.flow_dedup_level,

                    # Legacy compatibility.
                    snapshot.provider,

                    snapshot.call_bid_premium,
                    snapshot.put_bid_premium,

                    snapshot.bullish_premium,
                    snapshot.bearish_premium,
                    snapshot.directional_net,

                    snapshot.raw_alert_count,
                    snapshot.clean_alert_count,
                    snapshot.deduped_alert_count,

                    int(
                        snapshot
                        .trade_overlap_detected
                    ),

                    snapshot.sweep_alert_count,
                    snapshot.opening_alert_count,

                    snapshot.total_premium,
                    snapshot.sweep_premium,

                    snapshot.provider,
                    snapshot.feed,

                    _serialize_datetime(
                        snapshot.source_timestamp
                    ),

                    _serialize_datetime(
                        snapshot.fetched_at
                    ),

                    snapshot.freshness_status,
                ),
            )

            snapshot_id = (
                cursor.lastrowid
            )

        created = self.get_by_id(
            snapshot_id
        )

        if created is None:
            raise RuntimeError(
                "FlowSnapshot was inserted "
                "but could not be read back."
            )

        return created

    def get_by_id(
        self,
        snapshot_id: int,
    ) -> FlowSnapshot | None:

        if snapshot_id < 1:
            raise ValueError(
                "snapshot_id must be >= 1"
            )

        with database_connection() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM flow_snapshots
                WHERE id = ?
                """,
                (
                    snapshot_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_model(
            row
        )

    def get_latest(
        self,
        *,
        ticker: str,
        trading_date_et: date,
    ) -> FlowSnapshot | None:

        ticker = (
            ticker
            .upper()
            .strip()
        )

        if not ticker:
            raise ValueError(
                "ticker cannot be empty"
            )

        with database_connection() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM flow_snapshots
                WHERE
                    ticker = ?
                    AND trading_date_et = ?
                ORDER BY
                    captured_at DESC,
                    id DESC
                LIMIT 1
                """,
                (
                    ticker,
                    _serialize_date(
                        trading_date_et
                    ),
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_model(
            row
        )

    def get_latest_for_expiry(
        self,
        *,
        ticker: str,
        trading_date_et: date,
        target_expiry: date,
    ) -> FlowSnapshot | None:

        ticker = (
            ticker
            .upper()
            .strip()
        )

        if not ticker:
            raise ValueError(
                "ticker cannot be empty"
            )

        if target_expiry < trading_date_et:
            raise ValueError(
                "target_expiry cannot be before "
                "trading_date_et"
            )

        with database_connection() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM flow_snapshots
                WHERE
                    ticker = ?
                    AND trading_date_et = ?
                    AND target_expiry = ?
                ORDER BY
                    captured_at DESC,
                    id DESC
                LIMIT 1
                """,
                (
                    ticker,
                    _serialize_date(
                        trading_date_et
                    ),
                    _serialize_date(
                        target_expiry
                    ),
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_model(
            row
        )

    def list_for_session(
        self,
        *,
        ticker: str,
        trading_date_et: date,
    ) -> list[FlowSnapshot]:

        ticker = (
            ticker
            .upper()
            .strip()
        )

        if not ticker:
            raise ValueError(
                "ticker cannot be empty"
            )

        with database_connection() as conn:

            rows = conn.execute(
                """
                SELECT *
                FROM flow_snapshots
                WHERE
                    ticker = ?
                    AND trading_date_et = ?
                ORDER BY
                    captured_at ASC,
                    id ASC
                """,
                (
                    ticker,
                    _serialize_date(
                        trading_date_et
                    ),
                ),
            ).fetchall()

        return [
            _row_to_model(
                row
            )
            for row in rows
        ]