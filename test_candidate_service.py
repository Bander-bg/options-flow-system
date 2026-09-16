from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.signal_repository as signal_repo_module

from weekly.db.signal_repository import (
    SignalRepository,
)
from weekly.domain.enums import (
    Direction,
    SignalState,
)
from weekly.domain.models import (
    FlowSnapshot,
)
from weekly.services.candidate_service import (
    CandidateService,
)


ROOT = Path(__file__).resolve().parent

PRODUCTION_DB = (
    ROOT
    / "weekly_trading.db"
)

TEST_DB = (
    ROOT
    / "weekly_candidate_service_test.db"
)


ET = ZoneInfo(
    "America/New_York"
)

UTC = ZoneInfo(
    "UTC"
)


TRADING_DATE = date(
    2026,
    9,
    4,
)

TARGET_EXPIRY = date(
    2026,
    9,
    11,
)

FLOW_THRESHOLD = 500_000

CONFIRMATION_MINUTES = 30

STRATEGY_VERSION = "weekly_v1"

CONFIG_HASH = (
    "ee91b36101bbd4784c3170ab16697ad772fc7b37a149b1e6626bd9bcf10af458"
)


@dataclass(frozen=True)
class FakeCalendarSession:
    date: date
    open: datetime
    close: datetime


CALENDAR = [
    FakeCalendarSession(
        date=date(
            2026,
            9,
            4,
        ),
        open=datetime(
            2026,
            9,
            4,
            9,
            30,
            tzinfo=ET,
        ),
        close=datetime(
            2026,
            9,
            4,
            16,
            0,
            tzinfo=ET,
        ),
    ),
    FakeCalendarSession(
        date=date(
            2026,
            9,
            8,
        ),
        open=datetime(
            2026,
            9,
            8,
            9,
            30,
            tzinfo=ET,
        ),
        close=datetime(
            2026,
            9,
            8,
            16,
            0,
            tzinfo=ET,
        ),
    ),
]


def file_sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as file:
        while True:
            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def clone_database():
    if TEST_DB.exists():
        TEST_DB.unlink()

    source = sqlite3.connect(
        PRODUCTION_DB
    )

    target = sqlite3.connect(
        TEST_DB
    )

    source.backup(
        target
    )

    source.close()
    target.close()


def configure_connection(
    connection: sqlite3.Connection,
):
    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        "PRAGMA busy_timeout = 5000"
    )


@contextmanager
def test_database_connection():
    connection = sqlite3.connect(
        TEST_DB,
        timeout=5,
    )

    configure_connection(
        connection
    )

    try:
        yield connection

    finally:
        connection.close()


@contextmanager
def test_database_transaction():
    connection = sqlite3.connect(
        TEST_DB,
        timeout=5,
    )

    configure_connection(
        connection
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        yield connection

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def patch_repository_database():
    signal_repo_module.database_connection = (
        test_database_connection
    )

    signal_repo_module.database_transaction = (
        test_database_transaction
    )


def clear_test_signals():
    connection = sqlite3.connect(
        TEST_DB
    )

    connection.execute(
        "DELETE FROM signals"
    )

    connection.commit()
    connection.close()


def cleanup():
    for suffix in (
        "",
        "-wal",
        "-shm",
    ):
        path = Path(
            str(TEST_DB) + suffix
        )

        if path.exists():
            path.unlink()


def make_snapshot(
    *,
    ticker: str,
    net_flow: float,
    captured_at: datetime,
) -> FlowSnapshot:

    if net_flow >= 0:
        call_ask = (
            600_000.0
            + net_flow
        )

        put_ask = 600_000.0

    else:
        call_ask = 600_000.0

        put_ask = (
            600_000.0
            + abs(
                net_flow
            )
        )

    return FlowSnapshot(
        ticker=ticker,

        trading_date_et=(
            TRADING_DATE
        ),

        captured_at=(
            captured_at
        ),

        target_expiry=(
            TARGET_EXPIRY
        ),

        call_ask_premium=(
            call_ask
        ),

        put_ask_premium=(
            put_ask
        ),

        net_flow=(
            net_flow
        ),

        call_bid_premium=(
            100_000.0
        ),

        put_bid_premium=(
            100_000.0
        ),

        bullish_premium=(
            call_ask
            + 100_000.0
        ),

        bearish_premium=(
            put_ask
            + 100_000.0
        ),

        directional_net=(
            call_ask
            - put_ask
        ),

        raw_alert_count=100,

        clean_alert_count=20,

        deduped_alert_count=20,

        flow_dedup_level=(
            "alert_uuid"
        ),

        trade_overlap_detected=False,

        sweep_alert_count=0,

        opening_alert_count=0,

        provider=(
            "UNUSUAL_WHALES"
        ),

        feed="UNKNOWN",

        source_timestamp=(
            captured_at
            .astimezone(
                UTC
            )
        ),

        fetched_at=(
            captured_at
            .astimezone(
                UTC
            )
        ),

        freshness_status=(
            "UNKNOWN"
        ),
    )


def create_candidate(
    service: CandidateService,
    *,
    snapshot: FlowSnapshot,
    candidate_at: datetime,
):
    return (
        service
        .create_initial_candidate(
            snapshot=snapshot,

            candidate_at=(
                candidate_at
            ),

            calendar=(
                CALENDAR
            ),

            strategy_version=(
                STRATEGY_VERSION
            ),

            config_hash=(
                CONFIG_HASH
            ),

            flow_threshold=(
                FLOW_THRESHOLD
            ),

            confirmation_minutes=(
                CONFIRMATION_MINUTES
            ),

            theta_convention_status=(
                "UNRESOLVED"
            ),

            scenario_return_enabled=False,
        )
    )


def assert_equal(
    actual,
    expected,
    name: str,
):
    if actual != expected:
        raise AssertionError(
            f"{name}: expected "
            f"{expected!r}, got {actual!r}"
        )


def reset_signals():
    clear_test_signals()


def test_bullish_candidate(
    service: CandidateService,
):
    reset_signals()

    captured_at = datetime(
        2026,
        9,
        4,
        10,
        0,
        tzinfo=ET,
    )

    snapshot = make_snapshot(
        ticker="AAPL",
        net_flow=500_000,
        captured_at=captured_at,
    )

    result = create_candidate(
        service,
        snapshot=snapshot,
        candidate_at=captured_at,
    )

    assert_equal(
        result.created,
        True,
        "bullish created",
    )

    assert_equal(
        result.reason,
        "CANDIDATE_CREATED",
        "bullish reason",
    )

    assert_equal(
        result.direction,
        Direction.BULLISH,
        "bullish direction",
    )

    if result.signal is None:
        raise AssertionError(
            "Bullish signal missing."
        )

    assert_equal(
        result.signal.state,
        SignalState.CANDIDATE,
        "bullish state",
    )

    assert_equal(
        result.signal.candidate_sequence,
        1,
        "bullish candidate_sequence",
    )

    assert_equal(
        result.signal.net_flow_at_candidate,
        500_000,
        "bullish net flow",
    )


def test_bearish_candidate(
    service: CandidateService,
):
    reset_signals()

    captured_at = datetime(
        2026,
        9,
        4,
        10,
        5,
        tzinfo=ET,
    )

    snapshot = make_snapshot(
        ticker="TSLA",
        net_flow=-500_000,
        captured_at=captured_at,
    )

    result = create_candidate(
        service,
        snapshot=snapshot,
        candidate_at=captured_at,
    )

    assert_equal(
        result.created,
        True,
        "bearish created",
    )

    assert_equal(
        result.direction,
        Direction.BEARISH,
        "bearish direction",
    )

    if result.signal is None:
        raise AssertionError(
            "Bearish signal missing."
        )

    assert_equal(
        result.signal.state,
        SignalState.CANDIDATE,
        "bearish state",
    )

    assert_equal(
        result.signal.net_flow_at_candidate,
        -500_000,
        "bearish net flow",
    )


def test_below_positive_threshold(
    service: CandidateService,
):
    reset_signals()

    captured_at = datetime(
        2026,
        9,
        4,
        10,
        10,
        tzinfo=ET,
    )

    snapshot = make_snapshot(
        ticker="NVDA",
        net_flow=499_999,
        captured_at=captured_at,
    )

    result = create_candidate(
        service,
        snapshot=snapshot,
        candidate_at=captured_at,
    )

    assert_equal(
        result.created,
        False,
        "positive below threshold",
    )

    assert_equal(
        result.reason,
        "BELOW_FLOW_THRESHOLD",
        "positive threshold reason",
    )

    assert_equal(
        result.signal,
        None,
        "positive threshold signal",
    )


def test_below_negative_threshold(
    service: CandidateService,
):
    reset_signals()

    captured_at = datetime(
        2026,
        9,
        4,
        10,
        15,
        tzinfo=ET,
    )

    snapshot = make_snapshot(
        ticker="GOOGL",
        net_flow=-499_999,
        captured_at=captured_at,
    )

    result = create_candidate(
        service,
        snapshot=snapshot,
        candidate_at=captured_at,
    )

    assert_equal(
        result.created,
        False,
        "negative below threshold",
    )

    assert_equal(
        result.reason,
        "BELOW_FLOW_THRESHOLD",
        "negative threshold reason",
    )


def test_duplicate_poll_blocked(
    service: CandidateService,
):
    reset_signals()

    first_time = datetime(
        2026,
        9,
        4,
        11,
        0,
        tzinfo=ET,
    )

    first_snapshot = make_snapshot(
        ticker="META",
        net_flow=700_000,
        captured_at=first_time,
    )

    first = create_candidate(
        service,
        snapshot=first_snapshot,
        candidate_at=first_time,
    )

    if not first.created:
        raise AssertionError(
            "First Candidate was not created."
        )

    second_time = datetime(
        2026,
        9,
        4,
        11,
        3,
        tzinfo=ET,
    )

    second_snapshot = make_snapshot(
        ticker="META",
        net_flow=900_000,
        captured_at=second_time,
    )

    second = create_candidate(
        service,
        snapshot=second_snapshot,
        candidate_at=second_time,
    )

    assert_equal(
        second.created,
        False,
        "duplicate created",
    )

    assert_equal(
        second.reason,
        "EXISTING_SIGNAL_REQUIRES_REARM",
        "duplicate reason",
    )

    rows = (
        service.repository
        .get_latest(
            strategy_version=(
                STRATEGY_VERSION
            ),
            ticker="META",
            trading_date_et=(
                TRADING_DATE
            ),
            target_expiry=(
                TARGET_EXPIRY
            ),
            direction=(
                Direction.BULLISH
            ),
        )
    )

    if rows is None:
        raise AssertionError(
            "Original Candidate disappeared."
        )

    assert_equal(
        rows.candidate_sequence,
        1,
        "duplicate candidate sequence",
    )


def test_normal_deadline(
    service: CandidateService,
):
    reset_signals()

    candidate_at = datetime(
        2026,
        9,
        4,
        12,
        0,
        tzinfo=ET,
    )

    snapshot = make_snapshot(
        ticker="AAPL",
        net_flow=600_000,
        captured_at=candidate_at,
    )

    result = create_candidate(
        service,
        snapshot=snapshot,
        candidate_at=candidate_at,
    )

    if result.signal is None:
        raise AssertionError(
            "Normal deadline signal missing."
        )

    expected = datetime(
        2026,
        9,
        4,
        12,
        30,
        tzinfo=ET,
    )

    assert_equal(
        result.signal
        .requested_confirmation_deadline_at,
        expected,
        "requested normal deadline",
    )

    assert_equal(
        result.signal
        .confirmation_deadline_at,
        expected,
        "actual normal deadline",
    )


def test_near_close_deadline(
    service: CandidateService,
):
    reset_signals()

    candidate_at = datetime(
        2026,
        9,
        4,
        15,
        50,
        tzinfo=ET,
    )

    snapshot = make_snapshot(
        ticker="TSLA",
        net_flow=-750_000,
        captured_at=candidate_at,
    )

    result = create_candidate(
        service,
        snapshot=snapshot,
        candidate_at=candidate_at,
    )

    if result.signal is None:
        raise AssertionError(
            "Near-close signal missing."
        )

    expected_requested = datetime(
        2026,
        9,
        8,
        9,
        50,
        tzinfo=ET,
    )

    expected_actual = datetime(
        2026,
        9,
        4,
        16,
        0,
        tzinfo=ET,
    )

    assert_equal(
        result.signal
        .requested_confirmation_deadline_at,
        expected_requested,
        "near-close requested deadline",
    )

    assert_equal(
        result.signal
        .confirmation_deadline_at,
        expected_actual,
        "near-close clipped deadline",
    )


def test_config_and_metadata_persisted(
    service: CandidateService,
):
    reset_signals()

    candidate_at = datetime(
        2026,
        9,
        4,
        13,
        0,
        tzinfo=ET,
    )

    snapshot = make_snapshot(
        ticker="NVDA",
        net_flow=800_000,
        captured_at=candidate_at,
    )

    result = create_candidate(
        service,
        snapshot=snapshot,
        candidate_at=candidate_at,
    )

    signal = result.signal

    if signal is None:
        raise AssertionError(
            "Metadata signal missing."
        )

    assert_equal(
        signal.strategy_version,
        STRATEGY_VERSION,
        "strategy_version",
    )

    assert_equal(
        signal.config_hash,
        CONFIG_HASH,
        "config_hash",
    )

    assert_equal(
        signal.flow_dedup_level,
        "alert_uuid",
        "flow_dedup_level",
    )

    assert_equal(
        signal.theta_convention_status,
        "UNRESOLVED",
        "theta status",
    )

    assert_equal(
        signal.scenario_return_enabled,
        False,
        "scenario return enabled",
    )

    assert_equal(
        signal.stock_data_provider,
        None,
        "stock provider",
    )

    assert_equal(
        signal.options_data_provider,
        None,
        "options provider",
    )


def test_before_snapshot_rejected(
    service: CandidateService,
):
    reset_signals()

    snapshot = make_snapshot(
        ticker="AAPL",
        net_flow=600_000,
        captured_at=datetime(
            2026,
            9,
            4,
            14,
            3,
            tzinfo=ET,
        ),
    )

    candidate_at = datetime(
        2026,
        9,
        4,
        14,
        0,
        tzinfo=ET,
    )

    error_raised = False

    try:
        create_candidate(
            service,
            snapshot=snapshot,
            candidate_at=candidate_at,
        )

    except ValueError as exc:
        if (
            "earlier than snapshot.captured_at"
            in str(exc)
        ):
            error_raised = True

    if not error_raised:
        raise AssertionError(
            "Candidate before snapshot "
            "was not rejected."
        )


def test_outside_session_rejected(
    service: CandidateService,
):
    reset_signals()

    candidate_at = datetime(
        2026,
        9,
        4,
        9,
        15,
        tzinfo=ET,
    )

    snapshot = make_snapshot(
        ticker="AAPL",
        net_flow=600_000,
        captured_at=candidate_at,
    )

    error_raised = False

    try:
        create_candidate(
            service,
            snapshot=snapshot,
            candidate_at=candidate_at,
        )

    except ValueError as exc:
        if (
            "official RTH session"
            in str(exc)
        ):
            error_raised = True

    if not error_raised:
        raise AssertionError(
            "Pre-market Candidate "
            "was not rejected."
        )


def run_test(
    name: str,
    function,
    service: CandidateService,
):
    try:
        function(
            service
        )

        print(
            f"PASS - {name}"
        )

        return True

    except Exception as exc:
        print(
            f"FAIL - {name}"
        )

        print(
            f"       {type(exc).__name__}: "
            f"{exc}"
        )

        return False


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 CANDIDATE SERVICE TEST"
    )
    print("=" * 78)
    print()

    production_hash_before = (
        file_sha256(
            PRODUCTION_DB
        )
    )

    try:
        clone_database()

        patch_repository_database()

        clear_test_signals()

        repository = (
            SignalRepository()
        )

        service = CandidateService(
            repository=repository
        )

        tests = [
            (
                "Exact +500k creates BULLISH Candidate",
                test_bullish_candidate,
            ),
            (
                "Exact -500k creates BEARISH Candidate",
                test_bearish_candidate,
            ),
            (
                "+499,999 creates no Candidate",
                test_below_positive_threshold,
            ),
            (
                "-499,999 creates no Candidate",
                test_below_negative_threshold,
            ),
            (
                "Repeated scanner poll does not duplicate Candidate",
                test_duplicate_poll_blocked,
            ),
            (
                "Normal 30-minute confirmation deadline",
                test_normal_deadline,
            ),
            (
                "Near-close deadline clips to official close",
                test_near_close_deadline,
            ),
            (
                "Config/provenance fields persist",
                test_config_and_metadata_persisted,
            ),
            (
                "Candidate cannot precede FlowSnapshot",
                test_before_snapshot_rejected,
            ),
            (
                "Candidate outside RTH is rejected",
                test_outside_session_rejected,
            ),
        ]

        results = []

        for name, function in tests:
            results.append(
                run_test(
                    name,
                    function,
                    service,
                )
            )

        production_hash_after = (
            file_sha256(
                PRODUCTION_DB
            )
        )

        production_unchanged = (
            production_hash_before
            == production_hash_after
        )

        print()
        print("=" * 78)
        print("FINAL RESULT")
        print("=" * 78)
        print()

        passed = sum(
            1
            for result in results
            if result
        )

        print(
            "tests_passed:",
            passed,
            "/",
            len(results),
        )

        print(
            "Production weekly_trading.db "
            "modified:",
            (
                "NO"
                if production_unchanged
                else "YES"
            ),
        )

        print()

        if (
            all(results)
            and production_unchanged
        ):
            print(
                "CandidateService: PASS"
            )

            print(
                "Bullish threshold: PASS"
            )

            print(
                "Bearish threshold: PASS"
            )

            print(
                "Below-threshold suppression: PASS"
            )

            print(
                "Duplicate polling protection: PASS"
            )

            print(
                "Candidate sequence #1: PASS"
            )

            print(
                "30-minute deadline logic: PASS"
            )

            print(
                "Session-close clipping: PASS"
            )

            print(
                "Config/provenance persistence: PASS"
            )

            print(
                "RTH/time guards: PASS"
            )

            print()

            print(
                "INITIAL CANDIDATE CREATION: READY"
            )

            print(
                "Re-arm was NOT executed."
            )

            print(
                "Price Action was NOT executed."
            )

        else:
            print(
                "CandidateService: CHECK REQUIRED"
            )

    finally:
        cleanup()


if __name__ == "__main__":
    main()