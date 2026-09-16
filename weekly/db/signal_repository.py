from __future__ import annotations

from datetime import date, datetime

from weekly.db.database import (
    database_connection,
    database_transaction,
)
from weekly.domain.enums import (
    Direction,
    SignalState,
)
from weekly.domain.models import Signal


def _date_to_db(value: date | None) -> str | None:
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


def _row_to_signal(row) -> Signal:
    return Signal(
        id=row["id"],

        strategy_version=row[
            "strategy_version"
        ],

        config_hash=row[
            "config_hash"
        ],

        ticker=row["ticker"],

        trading_date_et=_date_from_db(
            row["trading_date_et"]
        ),

        target_expiry=_date_from_db(
            row["target_expiry"]
        ),

        direction=Direction(
            row["direction"]
        ),

        candidate_sequence=row[
            "candidate_sequence"
        ],

        state=SignalState(
            row["state"]
        ),

        candidate_at=_datetime_from_db(
            row["candidate_at"]
        ),

        requested_confirmation_deadline_at=(
            _datetime_from_db(
                row[
                    "requested_confirmation_deadline_at"
                ]
            )
        ),

        confirmation_deadline_at=(
            _datetime_from_db(
                row[
                    "confirmation_deadline_at"
                ]
            )
        ),

        confirmed_at=_datetime_from_db(
            row["confirmed_at"]
        ),

        terminal_at=_datetime_from_db(
            row["terminal_at"]
        ),

        terminal_reason=row[
            "terminal_reason"
        ],

        net_flow_at_candidate=row[
            "net_flow_at_candidate"
        ],

        net_flow_at_confirmation=row[
            "net_flow_at_confirmation"
        ],

        flow_dedup_level=row[
            "flow_dedup_level"
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

        theta_convention_status=row[
            "theta_convention_status"
        ],

        scenario_return_enabled=bool(
            row[
                "scenario_return_enabled"
            ]
        ),
    )


class SignalRepository:

    def create(
        self,
        signal: Signal,
    ) -> Signal:
        """
        Persist a new signal.

        The database UNIQUE constraint protects the
        logical signal key from duplicate inserts.
        """

        with database_transaction() as connection:

            cursor = connection.execute(
                """
                INSERT INTO signals (
                    strategy_version,
                    config_hash,

                    ticker,
                    trading_date_et,
                    target_expiry,

                    direction,
                    signal_sign,
                    candidate_sequence,

                    state,
                    candidate_at,

                    requested_confirmation_deadline_at,
                    confirmation_deadline_at,

                    confirmed_at,
                    terminal_at,
                    terminal_reason,

                    net_flow_at_candidate,
                    net_flow_at_confirmation,

                    flow_dedup_level,

                    stock_data_provider,
                    stock_data_feed,

                    options_data_provider,
                    options_data_feed,

                    theta_convention_status,
                    scenario_return_enabled
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                );
                """,
                (
                    signal.strategy_version,
                    signal.config_hash,

                    signal.ticker,
                    _date_to_db(
                        signal.trading_date_et
                    ),
                    _date_to_db(
                        signal.target_expiry
                    ),

                    signal.direction.value,
                    signal.signal_sign,
                    signal.candidate_sequence,

                    signal.state.value,
                    _datetime_to_db(
                        signal.candidate_at
                    ),

                    _datetime_to_db(
                        signal
                        .requested_confirmation_deadline_at
                    ),

                    _datetime_to_db(
                        signal
                        .confirmation_deadline_at
                    ),

                    _datetime_to_db(
                        signal.confirmed_at
                    ),

                    _datetime_to_db(
                        signal.terminal_at
                    ),

                    signal.terminal_reason,

                    signal.net_flow_at_candidate,
                    signal.net_flow_at_confirmation,

                    signal.flow_dedup_level,

                    signal.stock_data_provider,
                    signal.stock_data_feed,

                    signal.options_data_provider,
                    signal.options_data_feed,

                    signal.theta_convention_status,

                    1
                    if signal.scenario_return_enabled
                    else 0,
                ),
            )

            signal_id = cursor.lastrowid

            row = connection.execute(
                """
                SELECT *
                FROM signals
                WHERE id = ?;
                """,
                (
                    signal_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Signal insert succeeded but "
                "the inserted row could not be read."
            )

        return _row_to_signal(row)

    def get_by_id(
        self,
        signal_id: int,
    ) -> Signal | None:

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM signals
                WHERE id = ?;
                """,
                (
                    signal_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_signal(row)

    def get_latest(
        self,
        *,
        strategy_version: str,
        ticker: str,
        trading_date_et: date,
        target_expiry: date,
        direction: Direction,
    ) -> Signal | None:

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM signals
                WHERE strategy_version = ?
                  AND ticker = ?
                  AND trading_date_et = ?
                  AND target_expiry = ?
                  AND direction = ?
                ORDER BY
                    candidate_sequence DESC
                LIMIT 1;
                """,
                (
                    strategy_version,
                    ticker,
                    _date_to_db(
                        trading_date_et
                    ),
                    _date_to_db(
                        target_expiry
                    ),
                    direction.value,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_signal(row)

    def get_latest_with_confirmation(
        self,
        *,
        strategy_version: str,
        ticker: str,
        trading_date_et: date,
        target_expiry: date,
        direction: Direction,
    ) -> Signal | None:
        """
        Return the newest signal in this logical scope
        that has actual confirmation provenance.

        ReArm eligibility intentionally does NOT infer
        eligibility from SignalState. The frozen ReArm
        contract requires:
        - confirmed_at
        - net_flow_at_confirmation
        """

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM signals
                WHERE strategy_version = ?
                  AND ticker = ?
                  AND trading_date_et = ?
                  AND target_expiry = ?
                  AND direction = ?
                  AND confirmed_at IS NOT NULL
                  AND net_flow_at_confirmation IS NOT NULL
                ORDER BY
                    candidate_sequence DESC
                LIMIT 1;
                """,
                (
                    strategy_version,
                    ticker,
                    _date_to_db(
                        trading_date_et
                    ),
                    _date_to_db(
                        target_expiry
                    ),
                    direction.value,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_signal(row)

    def get_resolvable_for_scope(
        self,
        *,
        strategy_version: str,
        ticker: str,
        trading_date_et: date,
        target_expiry: date,
    ) -> list[Signal]:
        """
        Return all currently resolvable signals for the
        ticker/date/expiry scope, regardless of direction.

        Only CANDIDATE and DATA_BLOCKED are eligible for
        further pre-confirmation resolution.
        """

        with database_connection() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM signals
                WHERE strategy_version = ?
                  AND ticker = ?
                  AND trading_date_et = ?
                  AND target_expiry = ?
                  AND state IN (?, ?)
                ORDER BY
                    candidate_at ASC,
                    id ASC;
                """,
                (
                    strategy_version,
                    ticker,
                    _date_to_db(
                        trading_date_et
                    ),
                    _date_to_db(
                        target_expiry
                    ),
                    SignalState.CANDIDATE.value,
                    SignalState.DATA_BLOCKED.value,
                ),
            ).fetchall()

        return [
            _row_to_signal(row)
            for row in rows
        ]

    def next_candidate_sequence(
        self,
        *,
        strategy_version: str,
        ticker: str,
        trading_date_et: date,
        target_expiry: date,
        direction: Direction,
    ) -> int:
        """
        Return the next sequence for this logical
        signal scope.

        The final insert is still protected by the
        database UNIQUE constraint.
        """

        with database_connection() as connection:

            row = connection.execute(
                """
                SELECT
                    COALESCE(
                        MAX(candidate_sequence),
                        0
                    ) AS max_sequence
                FROM signals
                WHERE strategy_version = ?
                  AND ticker = ?
                  AND trading_date_et = ?
                  AND target_expiry = ?
                  AND direction = ?;
                """,
                (
                    strategy_version,
                    ticker,
                    _date_to_db(
                        trading_date_et
                    ),
                    _date_to_db(
                        target_expiry
                    ),
                    direction.value,
                ),
            ).fetchone()

        return int(
            row["max_sequence"]
        ) + 1
    def update_state(
        self,
        *,
        signal_id: int,
        new_state: SignalState,
        expected_state: SignalState | None = None,
        confirmed_at: datetime | None = None,
        terminal_at: datetime | None = None,
        terminal_reason: str | None = None,
        net_flow_at_confirmation: float | None = None,
    ) -> Signal:
        if signal_id < 1:
            raise ValueError("signal_id must be >= 1")

        for name, value in (
            ("confirmed_at", confirmed_at),
            ("terminal_at", terminal_at),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")

        params = {
            "signal_id": signal_id,
            "new_state": new_state.value,
            "expected_state": (
                expected_state.value
                if expected_state is not None
                else None
            ),
            "confirmed_at": _datetime_to_db(confirmed_at),
            "terminal_at": _datetime_to_db(terminal_at),
            "terminal_reason": terminal_reason,
            "net_flow_at_confirmation": net_flow_at_confirmation,
        }

        with database_transaction() as connection:
            if expected_state is None:
                cursor = connection.execute(
                    """
                    UPDATE signals
                    SET
                        state = :new_state,
                        confirmed_at = COALESCE(:confirmed_at, confirmed_at),
                        terminal_at = COALESCE(:terminal_at, terminal_at),
                        terminal_reason = COALESCE(:terminal_reason, terminal_reason),
                        net_flow_at_confirmation = COALESCE(
                            :net_flow_at_confirmation,
                            net_flow_at_confirmation
                        ),
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    WHERE id = :signal_id;
                    """,
                    params,
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE signals
                    SET
                        state = :new_state,
                        confirmed_at = COALESCE(:confirmed_at, confirmed_at),
                        terminal_at = COALESCE(:terminal_at, terminal_at),
                        terminal_reason = COALESCE(:terminal_reason, terminal_reason),
                        net_flow_at_confirmation = COALESCE(
                            :net_flow_at_confirmation,
                            net_flow_at_confirmation
                        ),
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    WHERE id = :signal_id
                      AND state = :expected_state;
                    """,
                    params,
                )

            if cursor.rowcount != 1:
                if expected_state is None:
                    raise RuntimeError(
                        "Signal state update failed: signal not found."
                    )
                raise RuntimeError(
                    "Signal state update failed: signal not found or current state "
                    "does not match expected_state."
                )

            row = connection.execute(
                "SELECT * FROM signals WHERE id = ?;",
                (signal_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Signal state update succeeded but the updated row could not be read."
            )

        return _row_to_signal(row)


    def update_market_data_provenance(
        self,
        *,
        signal_id: int,
        stock_data_provider: str | None = None,
        stock_data_feed: str | None = None,
        options_data_provider: str | None = None,
        options_data_feed: str | None = None,
    ) -> Signal:
        if signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        stock_pair_complete = (
            stock_data_provider is not None
            and stock_data_feed is not None
        )

        stock_pair_empty = (
            stock_data_provider is None
            and stock_data_feed is None
        )

        if not (
            stock_pair_complete
            or stock_pair_empty
        ):
            raise ValueError(
                "stock_data_provider and "
                "stock_data_feed must be "
                "provided together."
            )

        options_pair_complete = (
            options_data_provider is not None
            and options_data_feed is not None
        )

        options_pair_empty = (
            options_data_provider is None
            and options_data_feed is None
        )

        if not (
            options_pair_complete
            or options_pair_empty
        ):
            raise ValueError(
                "options_data_provider and "
                "options_data_feed must be "
                "provided together."
            )

        if (
            stock_pair_empty
            and options_pair_empty
        ):
            raise ValueError(
                "At least one market-data "
                "provenance pair is required."
            )

        for name, value in (
            (
                "stock_data_provider",
                stock_data_provider,
            ),
            (
                "stock_data_feed",
                stock_data_feed,
            ),
            (
                "options_data_provider",
                options_data_provider,
            ),
            (
                "options_data_feed",
                options_data_feed,
            ),
        ):
            if (
                value is not None
                and not value.strip()
            ):
                raise ValueError(
                    f"{name} cannot be empty."
                )

        params = {
            "signal_id": signal_id,
            "stock_data_provider": (
                stock_data_provider
            ),
            "stock_data_feed": (
                stock_data_feed
            ),
            "options_data_provider": (
                options_data_provider
            ),
            "options_data_feed": (
                options_data_feed
            ),
        }

        with database_transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE signals
                SET
                    stock_data_provider = COALESCE(
                        :stock_data_provider,
                        stock_data_provider
                    ),
                    stock_data_feed = COALESCE(
                        :stock_data_feed,
                        stock_data_feed
                    ),
                    options_data_provider = COALESCE(
                        :options_data_provider,
                        options_data_provider
                    ),
                    options_data_feed = COALESCE(
                        :options_data_feed,
                        options_data_feed
                    ),
                    updated_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = :signal_id;
                """,
                params,
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Signal market-data provenance "
                    "update failed: signal not found."
                )

            row = connection.execute(
                """
                SELECT *
                FROM signals
                WHERE id = ?;
                """,
                (
                    signal_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Signal market-data provenance "
                "update succeeded but the updated "
                "row could not be read."
            )

        return _row_to_signal(row)
