from __future__ import annotations

import sqlite3

from weekly.db.database import get_database_path


DB_PATH = get_database_path()


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{DB_PATH}?mode=ro",
        uri=True,
        timeout=5,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _rows(query: str, params: tuple = ()) -> list[dict]:
    with _connect() as connection:
        return [
            dict(row)
            for row in connection.execute(query, params).fetchall()
        ]


def load_engine_signals() -> list[dict]:
    return _rows(
        """
        SELECT
            s.*,
            sf.selected_contract_symbol,
            sf.selected_contract_right,
            sf.selected_contract_strike,
            sf.selected_contract_ask,
            sf.selected_contract_mark,
            sf.final_score,
            sf.final_grade,
            sf.coverage_pct,
            sf.price_action_status,
            sf.vwap_status,
            sf.efficiency_ratio_status,
            sf.eligible_contract_status
        FROM signals s
        LEFT JOIN signal_features sf
            ON sf.id = (
                SELECT sf2.id
                FROM signal_features sf2
                WHERE sf2.signal_id = s.id
                ORDER BY sf2.evaluation_sequence DESC, sf2.id DESC
                LIMIT 1
            )
        ORDER BY s.id DESC
        """
    )


def load_engine_positions() -> list[dict]:
    return _rows(
        """
        SELECT
            p.*,
            s.ticker,
            s.direction
        FROM positions p
        JOIN signals s ON s.id = p.signal_id
        ORDER BY p.id DESC
        """
    )


def load_engine_trades() -> list[dict]:
    return _rows(
        """
        SELECT
            t.*,
            s.ticker,
            p.contract_symbol
        FROM trades t
        JOIN signals s ON s.id = t.signal_id
        LEFT JOIN positions p ON p.id = t.position_id
        ORDER BY t.id DESC
        """
    )


def load_engine_outcomes() -> list[dict]:
    return _rows(
        """
        SELECT
            o.*,
            s.ticker,
            s.direction
        FROM outcomes o
        JOIN signals s ON s.id = o.signal_id
        ORDER BY o.id DESC
        """
    )


def load_engine_data_health() -> list[dict]:
    return _rows(
        """
        SELECT *
        FROM data_health
        ORDER BY id DESC
        """
    )


def engine_connection_status() -> dict:
    if not DB_PATH.exists():
        return {
            "connected": False,
            "database": str(DB_PATH),
            "reason": "DATABASE_NOT_FOUND",
        }

    try:
        with _connect() as connection:
            connection.execute("SELECT 1").fetchone()

        return {
            "connected": True,
            "database": str(DB_PATH),
            "reason": "READ_ONLY_CONNECTION_OK",
        }

    except Exception as exc:
        return {
            "connected": False,
            "database": str(DB_PATH),
            "reason": str(exc),
        }


def load_engine_signal_detail(ticker: str) -> dict | None:
    rows = _rows(
        """
        SELECT
            s.*,

            sf.selected_contract_symbol,
            sf.selected_contract_right,
            sf.selected_contract_strike,
            sf.selected_contract_bid,
            sf.selected_contract_ask,
            sf.selected_contract_mark,
            sf.selected_contract_delta,
            sf.selected_contract_spread_pct,
            sf.final_score,
            sf.final_grade,
            sf.coverage_pct,

            sf.structure_status,
            sf.impulse_status,
            sf.participation_status,
            sf.price_action_status,

            sf.vwap_status,
            sf.efficiency_ratio_status,
            sf.atr_1h,

            fs.call_ask_premium,
            fs.put_ask_premium,
            fs.call_bid_premium,
            fs.put_bid_premium,
            fs.bullish_premium,
            fs.bearish_premium,
            fs.directional_net,
            fs.total_premium

        FROM signals s

        LEFT JOIN signal_features sf
            ON sf.id = (
                SELECT sf2.id
                FROM signal_features sf2
                WHERE sf2.signal_id = s.id
                ORDER BY
                    sf2.evaluation_sequence DESC,
                    sf2.id DESC
                LIMIT 1
            )

        LEFT JOIN flow_snapshots fs
            ON fs.id = (
                SELECT fs2.id
                FROM flow_snapshots fs2
                WHERE fs2.ticker = s.ticker
                  AND fs2.trading_date_et = s.trading_date_et
                  AND fs2.target_expiry = s.target_expiry
                ORDER BY fs2.id DESC
                LIMIT 1
            )

        WHERE s.ticker = ?
        ORDER BY s.id DESC
        LIMIT 1
        """,
        (ticker.upper(),),
    )

    return rows[0] if rows else None
