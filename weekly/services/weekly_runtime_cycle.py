from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from weekly.providers.weekly_provider_factory import (
    WeeklyProviders,
)
from weekly.providers.unusual_whales_provider import (
    UnusualWhalesError,
)
from weekly.providers.alpaca_options_provider import (
    AlpacaOptionsProviderError,
)
from weekly.services.calendar_service import (
    find_session,
    select_target_expiry,
    session_close,
    session_open,
)
from weekly.services.flow_service import (
    calculate_flow,
)
from weekly.services.flow_snapshot_mapper import (
    map_flow_snapshot,
)
from weekly.services.market_context_service import (
    MarketContext,
    MarketContextService,
)
from weekly.services.weekly_runtime_factory import (
    WeeklyRuntimeServices,
)


@dataclass(frozen=True)
class SignalInvalidationRecord:
    signal_id: int | None
    result: Any


@dataclass(frozen=True)
class TickerRuntimeCycleResult:
    ticker: str
    target_expiry: date | None
    target_expiry_sessions: int | None
    flow_snapshot: Any | None
    market_data_window: Any | None
    stock_bars_result: Any | None
    atr_evaluations: tuple[Any, ...]
    market_regime_evaluations: tuple[Any, ...]
    price_action_evaluations: tuple[Any, ...]
    expected_move_evaluations: tuple[Any, ...]
    eligible_contract_evaluations: tuple[Any, ...]
    earnings_event_risk_evaluations: tuple[Any, ...]
    quality_evidence_evaluations: tuple[Any, ...]
    quality_scoring_evaluations: tuple[Any, ...]
    resolution_results: tuple[Any, ...]
    option_candidates_result: Any | None
    invalidations: tuple[SignalInvalidationRecord, ...]
    candidate_result: Any | None
    rearm_result: Any | None
    reason: str


@dataclass(frozen=True)
class WeeklyRuntimeCycleResult:
    market_context: MarketContext
    ticker_results: tuple[TickerRuntimeCycleResult, ...]
    reason: str


class WeeklyRuntimeCycle:
    """
    Integrated weekly_v1 runtime cycle.

    Current pipeline includes:
    - market context and target-expiry selection
    - UW flow fetch, calculation, and persistence
    - signal invalidation and initial candidate creation
    - stock/calendar context and market-data windows
    - ATR, market regime, and price action evaluation
    - expected move and eligible-contract evaluation
    - earnings, quality evidence, and quality scoring
    - signal resolution and state transitions
    - ReArm diagnostic evaluation

    ReArm persistence for Candidate #2+ and ACCELERATED
    remains intentionally undefined and is not performed here.
    """

    def __init__(
        self,
        *,
        services: WeeklyRuntimeServices,
        providers: WeeklyProviders,
        market_context_service: MarketContextService | None = None,
    ) -> None:
        self.services = services
        self.providers = providers

        self.market_context_service = (
            market_context_service
            if market_context_service is not None
            else MarketContextService(
                trading_client=providers.trading_client
            )
        )

    def run(self) -> WeeklyRuntimeCycleResult:
        config = self.services.config

        required_previous_sessions = int(
            config["price_action"]["participation"][
                "rvol_lookback_sessions"
            ]
        )

        context = self.market_context_service.fetch(
            required_previous_sessions=(
                required_previous_sessions
            )
        )

        if not context.is_trading_day:
            return WeeklyRuntimeCycleResult(
                market_context=context,
                ticker_results=(),
                reason="NOT_TRADING_DAY",
            )

        ticker_results = tuple(
            self._run_ticker(
                ticker=str(ticker).upper(),
                context=context,
            )
            for ticker in config["universe"]["tickers"]
        )

        return WeeklyRuntimeCycleResult(
            market_context=context,
            ticker_results=ticker_results,
            reason="CYCLE_COMPLETED",
        )

    def _run_ticker(
        self,
        *,
        ticker: str,
        context: MarketContext,
    ) -> TickerRuntimeCycleResult:
        config = self.services.config

        current_session = find_session(
            trading_date_et=context.trading_date_et,
            calendar=context.calendar,
        )

        if current_session is None:
            return TickerRuntimeCycleResult(
                ticker=ticker,
                target_expiry=None,
                target_expiry_sessions=None,
                flow_snapshot=None,
                market_data_window=None,
                stock_bars_result=None,
                atr_evaluations=(),
                market_regime_evaluations=(),
                price_action_evaluations=(),
                expected_move_evaluations=(),
                eligible_contract_evaluations=(),
                earnings_event_risk_evaluations=(),
                quality_evidence_evaluations=(),
                quality_scoring_evaluations=(),
                resolution_results=(),
                option_candidates_result=None,
                invalidations=(),
                candidate_result=None,
                rearm_result=None,
                reason="CURRENT_SESSION_NOT_FOUND",
            )

        current_session_open = session_open(
            current_session
        )
        current_session_close = session_close(
            current_session
        )

        future_calendar_dates = [
            session.date
            for session in context.calendar
            if session.date >= context.trading_date_et
        ]

        expiry_search_end = (
            max(future_calendar_dates)
            if future_calendar_dates
            else context.trading_date_et
            + timedelta(days=30)
        )

        listed_expiries = (
            self.providers.options.get_listed_expiries(
                ticker=ticker,
                start_date=context.trading_date_et,
                end_date=expiry_search_end,
            )
        )

        target = select_target_expiry(
            trading_date_et=context.trading_date_et,
            listed_expiries=list(listed_expiries),
            calendar=context.calendar,
            min_sessions=int(
                config["target_expiry"]["min_sessions"]
            ),
            max_sessions=int(
                config["target_expiry"]["max_sessions"]
            ),
        )

        if target is None:
            return TickerRuntimeCycleResult(
                ticker=ticker,
                target_expiry=None,
                target_expiry_sessions=None,
                flow_snapshot=None,
                market_data_window=None,
                stock_bars_result=None,
                atr_evaluations=(),
                market_regime_evaluations=(),
                price_action_evaluations=(),
                expected_move_evaluations=(),
                eligible_contract_evaluations=(),
                earnings_event_risk_evaluations=(),
                quality_evidence_evaluations=(),
                quality_scoring_evaluations=(),
                resolution_results=(),
                option_candidates_result=None,
                invalidations=(),
                candidate_result=None,
                rearm_result=None,
                reason="NO_ELIGIBLE_TARGET_EXPIRY",
            )

        target_expiry, target_expiry_sessions = target

        batch = (
            self.providers.unusual_whales
            .fetch_session_to_date_flow_alerts(
                ticker=ticker,
                session_open_et=current_session_open,
            )
        )

        calculation = calculate_flow(
            ticker=ticker,
            alerts=batch.alerts,
            trading_date_et=context.trading_date_et,
            target_expiry=target_expiry,
            session_open_et=current_session_open,
            session_close_et=current_session_close,
        )

        snapshot = map_flow_snapshot(
            calculation=calculation,
            batch=batch,
        )

        persisted_snapshot = (
            self.services.flow_snapshot_repository.create(
                snapshot
            )
        )

        # MarketContext is captured before external provider calls.
        # Keep Alpaca authoritative for the trading date/session, while
        # ensuring runtime evaluation time never precedes persisted data.
        runtime_as_of = max(
            context.market_timestamp,
            persisted_snapshot.captured_at,
        )

        resolvable_signals = (
            self.services.signal_repository
            .get_resolvable_for_scope(
                strategy_version=str(
                    config["strategy"]["strategy_version"]
                ),
                ticker=ticker,
                trading_date_et=context.trading_date_et,
                target_expiry=target_expiry,
            )
        )

        flow_threshold = float(
            config["flow"]["flow_threshold"]
        )

        invalidations = tuple(
            SignalInvalidationRecord(
                signal_id=getattr(signal, "id", None),
                result=(
                    self.services
                    .signal_invalidation_service
                    .evaluate(
                        signal=signal,
                        current_net_flow=(
                            persisted_snapshot.net_flow
                        ),
                        flow_threshold=flow_threshold,
                        as_of=runtime_as_of,
                    )
                ),
            )
            for signal in resolvable_signals
        )

        candidate_result = None

        if context.market_is_open:
            candidate_result = (
                self.services.candidate_service
                .create_initial_candidate(
                    snapshot=persisted_snapshot,
                    candidate_at=(
                        persisted_snapshot.captured_at
                    ),
                    calendar=context.calendar,
                    strategy_version=str(
                        config["strategy"][
                            "strategy_version"
                        ]
                    ),
                    config_hash=self.services.config_hash,
                    flow_threshold=flow_threshold,
                    confirmation_minutes=int(
                        config["price_action"][
                            "price_action_confirmation_minutes"
                        ]
                    ),
                    theta_convention_status=str(
                        config["contract_selector"][
                            "scenario"
                        ][
                            "theta_convention_status"
                        ]
                    ),
                    scenario_return_enabled=bool(
                        config["contract_selector"][
                            "scenario"
                        ][
                            "scenario_return_enabled"
                        ]
                    ),
                )
            )

        previous_sessions = int(
            config["price_action"]["participation"][
                "rvol_lookback_sessions"
            ]
        )

        market_data_window = (
            self.services.market_data_window_service.build(
                trading_date_et=context.trading_date_et,
                as_of=runtime_as_of,
                calendar=context.calendar,
                previous_sessions=previous_sessions,
            )
        )

        stock_bars_result = (
            self.providers.stock.get_minute_bars(
                ticker=ticker,
                start=market_data_window.start_at,
                end=market_data_window.end_at,
            )
        )

        # --------------------------------------------------
        # REARM DIAGNOSTIC EVALUATION
        # --------------------------------------------------
        #
        # This block intentionally performs NO persistence:
        # - no Candidate #2+ creation
        # - no Signal state transition
        # - no ACCELERATED transition
        # - no SignalFeature overwrite
        #
        # CandidateService remains authoritative for deciding
        # whether the current Base Flow direction points to an
        # existing same-scope signal that requires ReArm.
        # --------------------------------------------------

        rearm_result = None

        if (
            candidate_result is not None
            and candidate_result.reason
            == "EXISTING_SIGNAL_REQUIRES_REARM"
            and candidate_result.direction is not None
        ):
            previous_rearm_signal = (
                self.services.signal_repository
                .get_latest_with_confirmation(
                    strategy_version=str(
                        config["strategy"][
                            "strategy_version"
                        ]
                    ),
                    ticker=ticker,
                    trading_date_et=(
                        context.trading_date_et
                    ),
                    target_expiry=target_expiry,
                    direction=(
                        candidate_result.direction
                    ),
                )
            )

            if previous_rearm_signal is not None:
                rearm_result = (
                    self.services.rearm_service.evaluate(
                        previous_signal=(
                            previous_rearm_signal
                        ),
                        current_trading_date_et=(
                            context.trading_date_et
                        ),
                        as_of=runtime_as_of,
                        current_net_flow=(
                            persisted_snapshot.net_flow
                        ),
                        rearm_aligned_flow_min=float(
                            config["flow"][
                                "rearm_aligned_flow_min"
                            ]
                        ),
                        cooldown_minutes=int(
                            config["flow"][
                                "cooldown_minutes"
                            ]
                        ),
                        new_trigger_bar_close=None,
                    )
                )

                # Only search Price Action after the
                # same-session, cooldown and aligned-flow
                # requirements have already passed.
                if (
                    rearm_result.reason
                    == "NO_NEW_PRICE_TRIGGER"
                ):
                    rearm_atr = (
                        self.services.atr_service.evaluate(
                            as_of=runtime_as_of,
                            trading_date_et=(
                                context.trading_date_et
                            ),
                            calendar=context.calendar,
                            minute_bars=(
                                stock_bars_result.bars
                            ),
                        )
                    )

                    rearm_inputs = (
                        self.services
                        .price_action_input_service
                        .prepare_rearm_inputs(
                            confirmed_at=(
                                previous_rearm_signal
                                .confirmed_at
                            ),
                            as_of=runtime_as_of,
                            calendar=context.calendar,
                            fifteen_minute_bars=(
                                rearm_atr
                                .fifteen_minute_bars
                            ),
                        )
                    )

                    rearm_trigger = (
                        self.services
                        .rearm_price_action_trigger_service
                        .find_first_pass(
                            direction=(
                                previous_rearm_signal
                                .direction
                            ),
                            inputs=rearm_inputs,
                            atr_15m=(
                                rearm_atr.atr_15m
                            ),
                        )
                    )

                    rearm_result = (
                        self.services.rearm_service.evaluate(
                            previous_signal=(
                                previous_rearm_signal
                            ),
                            current_trading_date_et=(
                                context.trading_date_et
                            ),
                            as_of=runtime_as_of,
                            current_net_flow=(
                                persisted_snapshot.net_flow
                            ),
                            rearm_aligned_flow_min=float(
                                config["flow"][
                                    "rearm_aligned_flow_min"
                                ]
                            ),
                            cooldown_minutes=int(
                                config["flow"][
                                    "cooldown_minutes"
                                ]
                            ),
                            new_trigger_bar_close=(
                                rearm_trigger
                                .trigger_bar_close
                            ),
                        )
                    )

        provenance_signal_ids = {
            signal.id
            for signal in resolvable_signals
            if signal.id is not None
        }

        if (
            candidate_result is not None
            and candidate_result.created is True
            and candidate_result.signal is not None
            and candidate_result.signal.id is not None
        ):
            provenance_signal_ids.add(
                candidate_result.signal.id
            )

        for signal_id in sorted(provenance_signal_ids):
            self.services.signal_repository.update_market_data_provenance(
                signal_id=signal_id,
                stock_data_provider=stock_bars_result.provider,
                stock_data_feed=stock_bars_result.feed,
            )

        invalidated_signal_ids = {
            record.signal_id
            for record in invalidations
            if (
                record.signal_id is not None
                and record.result.invalidated
            )
        }

        evaluation_signal_ids = {
            signal.id
            for signal in resolvable_signals
            if (
                signal.id is not None
                and signal.id not in invalidated_signal_ids
            )
        }

        if (
            candidate_result is not None
            and candidate_result.created is True
            and candidate_result.signal is not None
            and candidate_result.signal.id is not None
        ):
            evaluation_signal_ids.add(
                candidate_result.signal.id
            )

        atr_evaluations = tuple(
            self.services.atr_evaluation_service.evaluate_and_persist(
                signal_id=signal_id,
                as_of=runtime_as_of,
                trading_date_et=context.trading_date_et,
                calendar=context.calendar,
                minute_bars=stock_bars_result.bars,
                captured_at=runtime_as_of,
            )
            for signal_id in sorted(evaluation_signal_ids)
        )

        signal_by_id = {
            signal.id: signal
            for signal in resolvable_signals
            if signal.id is not None
        }

        if (
            candidate_result is not None
            and candidate_result.created is True
            and candidate_result.signal is not None
            and candidate_result.signal.id is not None
        ):
            signal_by_id[
                candidate_result.signal.id
            ] = candidate_result.signal

        market_regime_evaluations = tuple(
            self.services.market_regime_evaluation_service
            .evaluate_and_persist(
                signal_id=signal_id,
                direction=signal_by_id[signal_id].direction,
                as_of=runtime_as_of,
                trading_date_et=context.trading_date_et,
                calendar=context.calendar,
                minute_bars=stock_bars_result.bars,
                captured_at=runtime_as_of,
            )
            for signal_id in sorted(evaluation_signal_ids)
        )

        atr_by_signal_id = {
            evaluation.feature.signal_id: evaluation
            for evaluation in atr_evaluations
        }

        price_action_evaluations_list = []

        for signal_id in sorted(evaluation_signal_ids):
            signal = signal_by_id[signal_id]
            atr_evaluation = atr_by_signal_id[signal_id]

            existing_features = (
                self.services.feature_repository
                .get_all_for_signal(signal_id)
            )

            price_action_inputs = (
                self.services.price_action_input_service
                .prepare_inputs(
                    candidate_at=signal.candidate_at,
                    confirmation_deadline_at=(
                        signal.confirmation_deadline_at
                    ),
                    calendar=context.calendar,
                    fifteen_minute_bars=(
                        atr_evaluation.result
                        .fifteen_minute_bars
                    ),
                    existing_features=existing_features,
                )
            )

            for price_action_input in price_action_inputs:
                price_action_evaluations_list.append(
                    self.services
                    .price_action_evaluation_service
                    .evaluate_and_persist(
                        signal_id=signal_id,
                        direction=signal.direction,
                        candidate_at=signal.candidate_at,
                        confirmation_deadline_at=(
                            signal.confirmation_deadline_at
                        ),
                        captured_at=(
                            runtime_as_of
                        ),
                        trigger_bar=(
                            price_action_input.trigger_bar
                        ),
                        prior_bars=(
                            price_action_input.prior_bars
                        ),
                        atr_15m=(
                            atr_evaluation.result.atr_15m
                        ),
                        historical_same_slot_volumes=(
                            price_action_input
                            .historical_same_slot_volumes
                        ),
                        atr_1h=(
                            atr_evaluation.result.atr_1h
                        ),
                    )
                )

        price_action_evaluations = tuple(
            price_action_evaluations_list
        )

        market_regime_by_signal_id = {
            evaluation.feature.signal_id: evaluation
            for evaluation in market_regime_evaluations
        }

        term_structure_rows = None

        if evaluation_signal_ids:
            try:
                term_structure_rows = (
                    self.providers.unusual_whales
                    .fetch_volatility_term_structure(
                        ticker=ticker
                    )
                )
            except UnusualWhalesError:
                term_structure_rows = None

        option_candidates_result = None
        atm_iv_result = None

        expected_move_evaluations_list = []

        for signal_id in sorted(evaluation_signal_ids):
            underlying_price = (
                market_regime_by_signal_id[
                    signal_id
                ].feature.underlying_price
            )

            primary_probe = (
                self.services.expected_move_service.evaluate(
                    trading_date=context.trading_date_et,
                    target_expiry=target_expiry,
                    underlying_price=underlying_price,
                    term_structure_rows=term_structure_rows,
                    atm_iv=None,
                )
            )

            atm_iv = None

            if (
                primary_probe.source
                != self.services.expected_move_service.PRIMARY_SOURCE
                and primary_probe.reason
                != "UNDERLYING_PRICE_UNAVAILABLE"
            ):
                if option_candidates_result is None:
                    try:
                        option_candidates_result = (
                            self.providers.options
                            .get_contract_candidates(
                                ticker=ticker,
                                target_expiry=target_expiry,
                            )
                        )
                    except AlpacaOptionsProviderError:
                        option_candidates_result = None

                    if option_candidates_result is not None:
                        for provenance_signal_id in sorted(
                            evaluation_signal_ids
                        ):
                            self.services.signal_repository.update_market_data_provenance(
                                signal_id=provenance_signal_id,
                                options_data_provider=(
                                    option_candidates_result.provider
                                ),
                                options_data_feed=(
                                    option_candidates_result.feed
                                ),
                            )

                if option_candidates_result is not None:
                    atm_iv_result = (
                        self.services.atm_iv_resolver.resolve(
                            underlying_price=underlying_price,
                            contracts=(
                                option_candidates_result.candidates
                            ),
                        )
                    )

                    atm_iv = atm_iv_result.atm_iv

            expected_move_evaluations_list.append(
                self.services
                .expected_move_evaluation_service
                .evaluate_and_persist(
                    signal_id=signal_id,
                    trading_date=context.trading_date_et,
                    target_expiry=target_expiry,
                    underlying_price=underlying_price,
                    term_structure_rows=term_structure_rows,
                    atm_iv=atm_iv,
                    captured_at=(
                            runtime_as_of
                        ),
                )
            )

        expected_move_evaluations = tuple(
            expected_move_evaluations_list
        )

        # Eligible Contract always needs the option chain.
        # Reuse the chain if ATM-IV fallback already fetched it.
        if (
            evaluation_signal_ids
            and option_candidates_result is None
        ):
            try:
                option_candidates_result = (
                    self.providers.options
                    .get_contract_candidates(
                        ticker=ticker,
                        target_expiry=target_expiry,
                    )
                )
            except AlpacaOptionsProviderError:
                option_candidates_result = None

            if option_candidates_result is not None:
                for provenance_signal_id in sorted(
                    evaluation_signal_ids
                ):
                    self.services.signal_repository.update_market_data_provenance(
                        signal_id=provenance_signal_id,
                        options_data_provider=(
                            option_candidates_result.provider
                        ),
                        options_data_feed=(
                            option_candidates_result.feed
                        ),
                    )

        eligible_contract_evaluations = tuple(
            self.services
            .eligible_contract_evaluation_service
            .evaluate_and_persist(
                signal_id=signal_id,
                direction=signal_by_id[signal_id].direction,
                target_expiry=target_expiry,
                as_of=runtime_as_of,
                contracts=(
                    option_candidates_result.candidates
                    if option_candidates_result is not None
                    else None
                ),
                captured_at=runtime_as_of,
            )
            for signal_id in sorted(evaluation_signal_ids)
        )

        earnings_snapshot = None

        if evaluation_signal_ids:
            try:
                earnings_snapshot = (
                    self.providers.unusual_whales
                    .fetch_earnings_snapshot(
                        ticker=ticker
                    )
                )
            except UnusualWhalesError:
                earnings_snapshot = None

        earnings_event_risk_evaluations = tuple(
            self.services
            .earnings_event_risk_evaluation_service
            .evaluate_and_persist(
                signal_id=signal_id,
                trading_date_et=context.trading_date_et,
                target_expiry=target_expiry,
                next_earnings_date=(
                    earnings_snapshot.next_earnings_date
                    if earnings_snapshot is not None
                    else None
                ),
                earnings_time=(
                    earnings_snapshot.earnings_time
                    if earnings_snapshot is not None
                    else None
                ),
                captured_at=runtime_as_of,
            )
            for signal_id in sorted(evaluation_signal_ids)
        )

        greek_exposure_snapshot = None

        if evaluation_signal_ids:
            try:
                greek_exposure_snapshot = (
                    self.providers.unusual_whales
                    .fetch_greek_exposure(
                        ticker=ticker,
                        trading_date=context.trading_date_et,
                    )
                )
            except UnusualWhalesError:
                greek_exposure_snapshot = None

        quality_evidence_evaluations = tuple(
            self.services
            .quality_evidence_evaluation_service
            .evaluate_and_persist(
                signal_id=signal_id,
                captured_at=runtime_as_of,
                total_gex=(
                    greek_exposure_snapshot.total_gex
                    if greek_exposure_snapshot is not None
                    else None
                ),
            )
            for signal_id in sorted(evaluation_signal_ids)
        )

        quality_scoring_evaluations = tuple(
            self.services
            .quality_scoring_evaluation_service
            .evaluate_and_persist(
                signal_id=signal_id,
                captured_at=runtime_as_of,
            )
            for signal_id in sorted(evaluation_signal_ids)
        )

        invalidated_by_signal_id = {
            record.signal_id: record.result.invalidated
            for record in invalidations
            if record.signal_id is not None
        }

        resolution_signal_ids = {
            signal.id
            for signal in resolvable_signals
            if signal.id is not None
        }

        if (
            candidate_result is not None
            and candidate_result.created is True
            and candidate_result.signal is not None
            and candidate_result.signal.id is not None
        ):
            resolution_signal_ids.add(
                candidate_result.signal.id
            )

        resolution_results = tuple(
            self.services
            .resolution_orchestrator
            .resolve_and_persist(
                signal_id=signal_id,
                as_of=runtime_as_of,
                invalidated=bool(
                    invalidated_by_signal_id.get(
                        signal_id,
                        False,
                    )
                ),
                net_flow_at_confirmation=(
                    persisted_snapshot.net_flow
                ),
            )
            for signal_id in sorted(resolution_signal_ids)
        )

        return TickerRuntimeCycleResult(
            ticker=ticker,
            target_expiry=target_expiry,
            target_expiry_sessions=(
                target_expiry_sessions
            ),
            flow_snapshot=persisted_snapshot,
            market_data_window=market_data_window,
            stock_bars_result=stock_bars_result,
            atr_evaluations=atr_evaluations,
            market_regime_evaluations=market_regime_evaluations,
            price_action_evaluations=price_action_evaluations,
            expected_move_evaluations=expected_move_evaluations,
            eligible_contract_evaluations=eligible_contract_evaluations,
            earnings_event_risk_evaluations=(
                earnings_event_risk_evaluations
            ),
            quality_evidence_evaluations=(
                quality_evidence_evaluations
            ),
            quality_scoring_evaluations=(
                quality_scoring_evaluations
            ),
            resolution_results=resolution_results,
            option_candidates_result=option_candidates_result,
            invalidations=invalidations,
            candidate_result=candidate_result,
            rearm_result=rearm_result,
            reason="TICKER_FLOW_STAGE_COMPLETED",
        )
