from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from weekly.providers.alpaca_options_provider import (
    OptionCandidatesResult,
    OptionContractCandidate,
    OptionRight,
)
from weekly.providers.alpaca_stock_provider import (
    StockBarsResult,
    StockMinuteBar,
)
from weekly.providers.weekly_provider_factory import WeeklyProviders
from weekly.services.market_context_service import MarketContextService
from weekly.services.weekly_runtime_cycle import WeeklyRuntimeCycle
from weekly.services.weekly_runtime_factory import build_weekly_runtime_services

from test_weekly_runtime_cycle import (
    ET,
    TEMP_DB,
    FakeTradingClient,
    FakeUWProvider,
    create_temp_database,
    patch_repositories,
)


class ConfirmedTradingClient(FakeTradingClient):
    def get_clock(self):
        base = super().get_clock()

        return SimpleNamespace(
            timestamp=datetime(
                2026, 9, 11, 12, 46,
                tzinfo=ET,
            ),
            is_open=True,
            next_open=base.next_open,
            next_close=base.next_close,
        )


class ConfirmedStockProvider:
    @staticmethod
    def _bar(
        *,
        start_at,
        open_price,
        high,
        low,
        close,
        volume,
    ):
        return StockMinuteBar(
            start_at=start_at,
            end_at=start_at + timedelta(minutes=1),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            trade_count=100,
            vwap=(
                open_price + close
            ) / 2.0,
        )

    def get_minute_bars(
        self,
        *,
        ticker,
        start,
        end,
    ):
        bars = []

        # 20 prior trading sessions:
        # one bar in the same 12:30 slot for RVOL,
        # ATR history, weekly ER history, etc.
        prior_dates = []
        day = date(2026, 8, 14)

        while day < date(2026, 9, 11):
            if day.weekday() < 5:
                prior_dates.append(day)
            day += timedelta(days=1)

        prior_dates = prior_dates[-20:]

        for index, session_date in enumerate(
            prior_dates
        ):
            base_price = 185.0 + index * 0.5

            bars.append(
                self._bar(
                    start_at=datetime(
                        session_date.year,
                        session_date.month,
                        session_date.day,
                        12,
                        30,
                        tzinfo=ET,
                    ),
                    open_price=base_price,
                    high=base_price + 0.5,
                    low=base_price - 0.5,
                    close=base_price + 0.2,
                    volume=100.0,
                )
            )

        # Current session prior 15m slots:
        # 09:30 through 12:15.
        current_date = date(2026, 9, 11)
        slot_start = datetime(
            2026, 9, 11, 9, 30,
            tzinfo=ET,
        )

        for index in range(12):
            price = 197.0 + index * 0.25

            bars.append(
                self._bar(
                    start_at=(
                        slot_start
                        + timedelta(
                            minutes=15 * index
                        )
                    ),
                    open_price=price,
                    high=price + 0.4,
                    low=price - 0.4,
                    close=price + 0.2,
                    volume=100.0,
                )
            )

        # Fresh trigger bar in the confirmation window:
        # 12:30 -> 12:45.
        bars.append(
            self._bar(
                start_at=datetime(
                    2026, 9, 11, 12, 30,
                    tzinfo=ET,
                ),
                open_price=200.0,
                high=205.5,
                low=199.5,
                close=205.0,
                volume=1000.0,
            )
        )

        return StockBarsResult(
            ticker=ticker,
            provider="ALPACA",
            feed="iex",
            requested_start=start,
            requested_end=end,
            bars=tuple(bars),
        )


class ConfirmedOptionsProvider:
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

    def get_contract_candidates(
        self,
        *,
        ticker,
        target_expiry,
    ):
        quote_at = datetime(
            2026, 9, 11, 12, 45, 45,
            tzinfo=ET,
        )

        candidates = (
            OptionContractCandidate(
                symbol=f"{ticker}260918C00205000",
                underlying_symbol=ticker,
                root_symbol=ticker,
                expiry=target_expiry,
                right=OptionRight.CALL,
                strike=205.0,
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
                symbol=f"{ticker}260918P00205000",
                underlying_symbol=ticker,
                root_symbol=ticker,
                expiry=target_expiry,
                right=OptionRight.PUT,
                strike=205.0,
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
                iv=0.45,
            ),
        )

        return OptionCandidatesResult(
            ticker=ticker,
            target_expiry=target_expiry,
            provider="ALPACA",
            feed="indicative",
            candidates=candidates,
        )


def main() -> None:
    create_temp_database()
    patch_repositories()

    try:
        services = build_weekly_runtime_services()

        trading_client = ConfirmedTradingClient()

        providers = WeeklyProviders(
            stock=ConfirmedStockProvider(),
            options=ConfirmedOptionsProvider(),
            unusual_whales=FakeUWProvider(),
            trading_client=trading_client,
        )

        cycle = WeeklyRuntimeCycle(
            services=services,
            providers=providers,
            market_context_service=(
                MarketContextService(
                    trading_client=trading_client
                )
            ),
        )

        result = cycle.run()

        assert result.reason == "CYCLE_COMPLETED"
        assert len(result.ticker_results) == 5

        for ticker_result in result.ticker_results:
            assert (
                len(ticker_result.resolution_results)
                == 1
            )

            assert (
                len(
                    ticker_result
                    .price_action_evaluations
                )
                >= 1
            )

            assert any(
                evaluation.result
                .price_action_status.value
                == "PASS"
                for evaluation
                in ticker_result
                .price_action_evaluations
            )

            regime = (
                ticker_result
                .market_regime_evaluations[0]
            )

            assert (
                regime.vwap_result.status.value
                == "PASS"
            )

            assert (
                regime.efficiency_ratio_result.status.value
                == "PASS"
            )

            contract = (
                ticker_result
                .eligible_contract_evaluations[0]
            )

            assert (
                contract.result.status.value
                == "PASS"
            )

            earnings = (
                ticker_result
                .earnings_event_risk_evaluations[0]
            )

            assert (
                earnings.result.status.value
                == "PASS"
            )

            resolution = (
                ticker_result.resolution_results[0]
            )

            assert (
                resolution
                .price_action_confirmation
                .status.value
                == "PASS"
            )

            assert (
                resolution
                .hard_gate_result
                .status.value
                == "PASS"
            )

            assert (
                resolution
                .transition
                .resolution
                .target_state.value
                == "CONFIRMED"
            )

            assert (
                resolution
                .transition
                .resolution
                .reason
                == "ALL_HARD_GATES_PASS"
            )

            assert (
                resolution.transition.persisted
                is True
            )

            assert (
                resolution.transition.signal.state.value
                == "CONFIRMED"
            )

            assert (
                resolution
                .transition
                .signal
                .net_flow_at_confirmation
                == 550_000.0
            )

        print(
            "WEEKLY RUNTIME CONFIRMED: "
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
