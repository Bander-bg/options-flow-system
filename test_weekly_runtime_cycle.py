from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import weekly.db.flow_snapshot_repository as flow_repo_module
import weekly.db.signal_repository as signal_repo_module
import weekly.db.signal_feature_repository as feature_repo_module

from weekly.providers.unusual_whales_provider import (
    EarningsSnapshot,
    FlowAlertsBatch,
    GreekExposureSnapshot,
)
from weekly.providers.alpaca_stock_provider import (
    StockBarsResult,
    StockMinuteBar,
)
from weekly.providers.alpaca_options_provider import (
    OptionCandidatesResult,
    OptionContractCandidate,
    OptionRight,
)
from weekly.providers.weekly_provider_factory import WeeklyProviders
from weekly.services.market_context_service import MarketContextService
from weekly.services.weekly_runtime_cycle import WeeklyRuntimeCycle
from weekly.services.weekly_runtime_factory import build_weekly_runtime_services


ET = ZoneInfo("America/New_York")

TEMP_DB = Path("weekly_runtime_cycle_test.db")
MIGRATIONS_DIR = Path("weekly/db/migrations")


def connect_temp() -> sqlite3.Connection:
    connection = sqlite3.connect(
        TEMP_DB,
        timeout=5,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL;")
    connection.execute("PRAGMA busy_timeout=5000;")
    connection.execute("PRAGMA foreign_keys=ON;")
    return connection


@contextmanager
def temp_database_connection():
    connection = connect_temp()
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def temp_database_transaction():
    connection = connect_temp()
    try:
        connection.execute("BEGIN IMMEDIATE;")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_temp_database() -> None:
    for path in (
        TEMP_DB,
        Path(str(TEMP_DB) + "-wal"),
        Path(str(TEMP_DB) + "-shm"),
    ):
        if path.exists():
            path.unlink()

    connection = connect_temp()

    try:
        for migration in sorted(
            MIGRATIONS_DIR.glob("*.sql")
        ):
            connection.executescript(
                migration.read_text(
                    encoding="utf-8"
                )
            )
        connection.commit()
    finally:
        connection.close()


def patch_repositories() -> None:
    signal_repo_module.database_connection = (
        temp_database_connection
    )
    signal_repo_module.database_transaction = (
        temp_database_transaction
    )

    flow_repo_module.database_connection = (
        temp_database_connection
    )
    flow_repo_module.database_transaction = (
        temp_database_transaction
    )

    feature_repo_module.database_connection = (
        temp_database_connection
    )
    feature_repo_module.database_transaction = (
        temp_database_transaction
    )


def make_session(day: date):
    return SimpleNamespace(
        date=day,
        open=datetime(
            day.year,
            day.month,
            day.day,
            9,
            30,
            tzinfo=ET,
        ),
        close=datetime(
            day.year,
            day.month,
            day.day,
            16,
            0,
            tzinfo=ET,
        ),
    )


class FakeTradingClient:
    def get_clock(self):
        return SimpleNamespace(
            timestamp=datetime(
                2026,
                9,
                11,
                12,
                15,
                tzinfo=ET,
            ),
            is_open=True,
            next_open=datetime(
                2026,
                9,
                14,
                9,
                30,
                tzinfo=ET,
            ),
            next_close=datetime(
                2026,
                9,
                11,
                16,
                0,
                tzinfo=ET,
            ),
        )

    def get_calendar(self, request):
        sessions = []
        day = date(2026, 8, 1)

        while day <= date(2026, 10, 11):
            if day.weekday() < 5:
                sessions.append(
                    make_session(day)
                )
            day += timedelta(days=1)

        return sessions


class FakeStockProvider:
    def get_minute_bars(
        self,
        *,
        ticker,
        start,
        end,
    ):
        bar = StockMinuteBar(
            start_at=datetime(
                2026, 9, 11, 12, 13,
                tzinfo=ET,
            ),
            end_at=datetime(
                2026, 9, 11, 12, 14,
                tzinfo=ET,
            ),
            open=199.0,
            high=201.0,
            low=198.5,
            close=200.0,
            volume=1000.0,
            trade_count=100,
            vwap=199.5,
        )

        return StockBarsResult(
            ticker=ticker,
            provider="ALPACA",
            feed="iex",
            requested_start=start,
            requested_end=end,
            bars=(bar,),
        )


class FakeOptionsProvider:
    def __init__(self):
        self.contract_candidate_calls = 0

    def get_contract_candidates(
        self,
        *,
        ticker,
        target_expiry,
    ):
        self.contract_candidate_calls += 1

        quote_at = datetime(
            2026, 9, 11, 12, 15,
            tzinfo=ET,
        )

        candidates = (
            OptionContractCandidate(
                symbol=f"{ticker}260918C00200000",
                underlying_symbol=ticker,
                root_symbol=ticker,
                expiry=target_expiry,
                right=OptionRight.CALL,
                strike=200.0,
                active=True,
                tradable=True,
                size=100,
                bid=4.80,
                ask=5.00,
                quote_at=quote_at,
                delta=0.50,
                gamma=0.02,
                theta=-0.10,
                vega=0.15,
                iv=0.40,
            ),
            OptionContractCandidate(
                symbol=f"{ticker}260918P00200000",
                underlying_symbol=ticker,
                root_symbol=ticker,
                expiry=target_expiry,
                right=OptionRight.PUT,
                strike=200.0,
                active=True,
                tradable=True,
                size=100,
                bid=4.70,
                ask=4.90,
                quote_at=quote_at,
                delta=-0.50,
                gamma=0.02,
                theta=-0.10,
                vega=0.15,
                iv=0.50,
            ),
        )

        return OptionCandidatesResult(
            ticker=ticker,
            target_expiry=target_expiry,
            provider="ALPACA",
            feed="indicative",
            candidates=candidates,
        )

    def get_listed_expiries(
        self,
        *,
        ticker,
        start_date,
        end_date,
    ):
        return (
            date(2026, 9, 18),
            date(2026, 9, 25),
        )


class FakeUWProvider:
    def fetch_greek_exposure(
        self,
        *,
        ticker,
        trading_date,
    ):
        return GreekExposureSnapshot(
            ticker=ticker,
            trading_date=trading_date,
            call_gamma=100.0,
            put_gamma=-200.0,
            total_gex=-100.0,
            provider="UNUSUAL_WHALES",
            fetched_at=datetime(
                2026, 9, 11, 12, 15,
                tzinfo=ET,
            ),
        )

    def fetch_earnings_snapshot(
        self,
        *,
        ticker,
    ):
        return EarningsSnapshot(
            ticker=ticker,
            next_earnings_date=date(2026, 10, 29),
            earnings_time="AMC",
            provider="UNUSUAL_WHALES",
            fetched_at=datetime(
                2026, 9, 11, 12, 15,
                tzinfo=ET,
            ),
        )

    def fetch_volatility_term_structure(
        self,
        *,
        ticker,
    ):
        return [
            {
                "expiry": "2026-09-18",
                "implied_move": 8.0,
                "volatility": 0.30,
                "implied_move_perc": 0.04,
            }
        ]

    def fetch_session_to_date_flow_alerts(
        self,
        *,
        ticker,
        session_open_et,
        max_pages=20,
        page_limit=500,
        require_complete=True,
    ):
        alerts = [
            {
                "created_at": "2026-09-11T14:00:00Z",
                "expiry": "2026-09-18",
                "option_chain": (
                    f"{ticker}260918C00200000"
                ),
                "alert_rule": "Sweep",
                "type": "call",
                "total_ask_side_prem": 650_000.0,
                "total_bid_side_prem": 25_000.0,
                "has_multileg": False,
                "has_singleleg": True,
                "has_sweep": True,
                "all_opening_trades": True,
                "total_premium": 675_000.0,
            },
            {
                "created_at": "2026-09-11T14:05:00Z",
                "expiry": "2026-09-18",
                "option_chain": (
                    f"{ticker}260918P00190000"
                ),
                "alert_rule": "RepeatedHitsDescendingFill",
                "type": "put",
                "total_ask_side_prem": 100_000.0,
                "total_bid_side_prem": 200_000.0,
                "has_multileg": False,
                "has_singleleg": True,
                "has_sweep": False,
                "all_opening_trades": False,
                "total_premium": 300_000.0,
            },
        ]

        fetched_at = datetime(
            2026,
            9,
            11,
            12,
            15,
            30,
            tzinfo=ET,
        )

        return FlowAlertsBatch(
            ticker=ticker,
            alerts=alerts,
            pages_fetched=1,
            rows_fetched=len(alerts),
            session_coverage_complete=True,
            session_start_reached=True,
            history_exhausted=False,
            newest_created_at=datetime(
                2026,
                9,
                11,
                10,
                5,
                tzinfo=ET,
            ),
            oldest_created_at=datetime(
                2026,
                9,
                11,
                10,
                0,
                tzinfo=ET,
            ),
            provider="UNUSUAL_WHALES",
            feed="FLOW_ALERTS",
            source_timestamp=datetime(
                2026,
                9,
                11,
                10,
                5,
                tzinfo=ET,
            ),
            fetched_at=fetched_at,
            freshness_status="PASS",
        )


def main() -> None:
    create_temp_database()
    patch_repositories()

    try:
        services = build_weekly_runtime_services()

        trading_client = FakeTradingClient()

        providers = WeeklyProviders(
            stock=FakeStockProvider(),
            options=FakeOptionsProvider(),
            unusual_whales=FakeUWProvider(),
            trading_client=trading_client,
        )

        market_context_service = MarketContextService(
            trading_client=trading_client
        )

        cycle = WeeklyRuntimeCycle(
            services=services,
            providers=providers,
            market_context_service=market_context_service,
        )

        result = cycle.run()

        assert result.reason == "CYCLE_COMPLETED"
        assert len(result.ticker_results) == 5

        for ticker_result in result.ticker_results:
            assert (
                ticker_result.target_expiry
                == date(2026, 9, 18)
            )

            assert (
                ticker_result.flow_snapshot
                is not None
            )

            assert (
                ticker_result.flow_snapshot.net_flow
                == 550_000.0
            )

            assert (
                ticker_result.candidate_result
                is not None
            )

            assert (
                ticker_result.candidate_result.created
                is True
            )

            assert (
                ticker_result.candidate_result.reason
                == "CANDIDATE_CREATED"
            )

            assert (
                len(
                    ticker_result
                    .expected_move_evaluations
                )
                == 1
            )

            expected_move_evaluation = (
                ticker_result
                .expected_move_evaluations[0]
            )

            assert (
                expected_move_evaluation.result.source
                == "UW_TERM_STRUCTURE"
            )

            assert (
                expected_move_evaluation
                .result.expected_move
                == 8.0
            )

            assert (
                ticker_result
                .option_candidates_result
                is not None
            )

            assert (
                len(
                    ticker_result
                    .eligible_contract_evaluations
                )
                == 1
            )

            eligible_contract_evaluation = (
                ticker_result
                .eligible_contract_evaluations[0]
            )

            assert (
                eligible_contract_evaluation.result.status.value
                == "PASS"
            )

            assert (
                eligible_contract_evaluation.result.reason
                == "ELIGIBLE_CONTRACT_FOUND"
            )

            assert (
                eligible_contract_evaluation
                .result.selected
                is not None
            )


            assert (
                len(
                    ticker_result
                    .earnings_event_risk_evaluations
                )
                == 1
            )

            earnings_evaluation = (
                ticker_result
                .earnings_event_risk_evaluations[0]
            )

            assert (
                earnings_evaluation.result.status.value
                == "PASS"
            )

            assert (
                earnings_evaluation.result.reason
                == "EARNINGS_AFTER_TARGET_EXPIRY"
            )


            assert (
                len(
                    ticker_result
                    .quality_evidence_evaluations
                )
                == 1
            )

            quality_evidence_evaluation = (
                ticker_result
                .quality_evidence_evaluations[0]
            )

            assert (
                quality_evidence_evaluation
                .result.negative_gamma_regime
                is True
            )

            assert (
                quality_evidence_evaluation
                .result.negative_gamma_regime_status
                .value
                == "PASS"
            )


            assert (
                len(
                    ticker_result
                    .quality_scoring_evaluations
                )
                == 1
            )

            quality_scoring_evaluation = (
                ticker_result
                .quality_scoring_evaluations[0]
            )

            assert (
                0.0
                <= quality_scoring_evaluation.result.base_score
                <= 100.0
            )

            assert (
                0.0
                <= quality_scoring_evaluation.result.final_score
                <= 100.0
            )

            assert (
                0.0
                <= quality_scoring_evaluation.result.coverage_pct
                <= 1.0
            )

            assert (
                quality_scoring_evaluation.result.final_grade
                in {"A", "B", "C", "UNRATED"}
            )

            assert (
                quality_scoring_evaluation.feature.final_score
                == quality_scoring_evaluation.result.final_score
            )


            assert (
                len(
                    ticker_result.resolution_results
                )
                == 1
            )

            resolution_result = (
                ticker_result.resolution_results[0]
            )

            assert (
                resolution_result
                .hard_gate_result.status.value
                == "UNKNOWN"
            )

            assert (
                resolution_result
                .transition.resolution.target_state.value
                == "DATA_BLOCKED"
            )

            assert (
                resolution_result
                .transition.resolution.reason
                == "HARD_GATE_UNKNOWN"
            )

            assert (
                resolution_result
                .transition.persisted
                is True
            )

            assert (
                resolution_result
                .transition.signal.state.value
                == "DATA_BLOCKED"
            )





            assert ticker_result.invalidations == ()

        connection = connect_temp()

        try:
            signal_count = connection.execute(
                "SELECT COUNT(*) FROM signals"
            ).fetchone()[0]

            snapshot_count = connection.execute(
                "SELECT COUNT(*) FROM flow_snapshots"
            ).fetchone()[0]
        finally:
            connection.close()

        assert signal_count == 5
        assert snapshot_count == 5

        print(
            "WEEKLY RUNTIME CYCLE FLOW STAGE: "
            "PASS 5/5"
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
