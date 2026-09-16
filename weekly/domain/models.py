from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from weekly.domain.enums import (
    DataHealthStatus,
    Direction,
    ExecutionMode,
    GateStatus,
    OptionRight,
    OutcomeScope,
    OutcomeStatus,
    PositionStatus,
    SignalState,
    TradeIntent,
    TradeSide,
    TradeStatus,
)


# ==================================================
# SIGNAL
# ==================================================


@dataclass(frozen=True)
class Signal:
    strategy_version: str
    config_hash: str

    ticker: str
    trading_date_et: date
    target_expiry: date

    direction: Direction
    candidate_sequence: int

    state: SignalState
    candidate_at: datetime

    requested_confirmation_deadline_at: datetime | None = None
    confirmation_deadline_at: datetime | None = None

    confirmed_at: datetime | None = None
    terminal_at: datetime | None = None

    terminal_reason: str | None = None

    net_flow_at_candidate: float | None = None
    net_flow_at_confirmation: float | None = None

    flow_dedup_level: str | None = None

    stock_data_provider: str | None = None
    stock_data_feed: str | None = None

    options_data_provider: str | None = None
    options_data_feed: str | None = None

    theta_convention_status: str | None = None

    scenario_return_enabled: bool = False

    id: int | None = None

    @property
    def signal_sign(self) -> int:
        return self.direction.sign

    def __post_init__(self):
        if not self.strategy_version.strip():
            raise ValueError(
                "strategy_version cannot be empty"
            )

        if not self.config_hash.strip():
            raise ValueError(
                "config_hash cannot be empty"
            )

        if not self.ticker.strip():
            raise ValueError(
                "ticker cannot be empty"
            )

        if self.candidate_sequence < 1:
            raise ValueError(
                "candidate_sequence must be >= 1"
            )

        if self.target_expiry < self.trading_date_et:
            raise ValueError(
                "target_expiry cannot be before "
                "trading_date_et"
            )

        if self.candidate_at.tzinfo is None:
            raise ValueError(
                "candidate_at must be timezone-aware"
            )

        datetime_fields = (
            (
                "requested_confirmation_deadline_at",
                self.requested_confirmation_deadline_at,
            ),
            (
                "confirmation_deadline_at",
                self.confirmation_deadline_at,
            ),
            (
                "confirmed_at",
                self.confirmed_at,
            ),
            (
                "terminal_at",
                self.terminal_at,
            ),
        )

        for name, value in datetime_fields:
            if (
                value is not None
                and value.tzinfo is None
            ):
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

        if not isinstance(
            self.scenario_return_enabled,
            bool,
        ):
            raise ValueError(
                "scenario_return_enabled must be bool"
            )


# ==================================================
# SIGNAL FEATURE
# ==================================================


@dataclass(frozen=True)
class SignalFeature:
    signal_id: int
    evaluation_sequence: int
    captured_at: datetime

    # FLOW
    flow_net: float | None = None
    flow_threshold: float | None = None

    # VWAP / UNDERLYING
    weekly_vwap: float | None = None
    underlying_price: float | None = None

    vwap_status: GateStatus | None = None

    # EFFICIENCY RATIO
    efficiency_ratio: float | None = None
    efficiency_ratio_status: GateStatus | None = None

    # EARNINGS
    next_earnings_date: date | None = None
    earnings_event_risk_status: GateStatus | None = None

    # EXPECTED MOVE
    expected_move: float | None = None
    expected_move_perc: float | None = None

    # SELECTED OPTION CONTRACT
    selected_contract_symbol: str | None = None
    selected_contract_right: OptionRight | None = None
    selected_contract_strike: float | None = None

    selected_contract_bid: float | None = None
    selected_contract_ask: float | None = None
    selected_contract_mark: float | None = None

    selected_contract_delta: float | None = None
    selected_contract_gamma: float | None = None
    selected_contract_theta: float | None = None
    selected_contract_vega: float | None = None
    selected_contract_iv: float | None = None

    selected_contract_spread_pct: float | None = None
    selected_contract_quote_age_seconds: float | None = None

    eligible_contract_status: GateStatus | None = None

    # PRICE ACTION STATUS
    structure_status: GateStatus | None = None
    impulse_status: GateStatus | None = None
    participation_status: GateStatus | None = None

    price_action_pass_count: int | None = None
    price_action_status: GateStatus | None = None

    # TRIGGER BAR EVIDENCE
    price_action_bar_at: datetime | None = None

    trigger_open: float | None = None
    trigger_high: float | None = None
    trigger_low: float | None = None
    trigger_close: float | None = None
    trigger_volume: float | None = None

    # STRUCTURE EVIDENCE
    structure_reference_level: float | None = None
    structure_break_level: float | None = None

    # IMPULSE EVIDENCE
    impulse_body: float | None = None
    impulse_median_body: float | None = None
    impulse_body_atr_ratio: float | None = None

    impulse_engulfing_match: bool | None = None
    impulse_expansion_match: bool | None = None

    # PARTICIPATION EVIDENCE
    participation_avg_slot_volume: float | None = None

    participation_median_slot_volume: float | None = None
    participation_reference_sessions: int | None = None
    participation_rvol: float | None = None

    # ATR / VOLATILITY
    atr_1h: float | None = None
    atr_15m: float | None = None

    iv_percentile: float | None = None

    # QUALITY ATOMIC EVIDENCE
    absolute_flow_strength: float | None = None
    absolute_flow_strength_status: GateStatus | None = None

    relative_flow_strength: float | None = None
    relative_flow_strength_status: GateStatus | None = None

    vwap_distance_atr: float | None = None
    vwap_distance_atr_status: GateStatus | None = None

    sweep_ratio: float | None = None
    sweep_ratio_status: GateStatus | None = None

    opening_evidence: float | None = None
    opening_evidence_status: GateStatus | None = None

    risk_reversal: float | None = None
    risk_reversal_status: GateStatus | None = None

    target_expiry_gex_alignment: bool | None = None
    target_expiry_gex_alignment_status: GateStatus | None = None

    negative_gamma_regime: bool | None = None
    negative_gamma_regime_status: GateStatus | None = None

    off_exchange_cluster_score: float | None = None
    off_exchange_cluster_score_status: GateStatus | None = None

    directional_flow_confirmation: float | None = None
    directional_flow_confirmation_status: GateStatus | None = None

    iv_percentile_status: GateStatus | None = None

    term_structure_inversion: bool | None = None
    term_structure_inversion_status: GateStatus | None = None

    iv_vs_realized_vol: float | None = None
    iv_vs_realized_vol_status: GateStatus | None = None

    target_expiry_iv: float | None = None
    iv_30d: float | None = None
    term_structure_ratio: float | None = None

    # SCORING
    base_score: float | None = None
    volatility_penalty: float | None = None
    final_score: float | None = None

    coverage_points: float | None = None
    coverage_pct: float | None = None

    raw_grade: str | None = None
    final_grade: str | None = None

    id: int | None = None

    def __post_init__(self):
        if self.signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        if self.evaluation_sequence < 1:
            raise ValueError(
                "evaluation_sequence must be >= 1"
            )

        if self.captured_at.tzinfo is None:
            raise ValueError(
                "captured_at must be timezone-aware"
            )

        if (
            self.price_action_pass_count is not None
            and self.price_action_pass_count < 0
        ):
            raise ValueError(
                "price_action_pass_count cannot be negative"
            )

        if (
            self.price_action_pass_count is not None
            and self.price_action_pass_count > 3
        ):
            raise ValueError(
                "price_action_pass_count cannot exceed 3"
            )

        if (
            self.price_action_bar_at is not None
            and self.price_action_bar_at.tzinfo is None
        ):
            raise ValueError(
                "price_action_bar_at must be timezone-aware"
            )

        if (
            self.impulse_engulfing_match is not None
            and not isinstance(
                self.impulse_engulfing_match,
                bool,
            )
        ):
            raise ValueError(
                "impulse_engulfing_match "
                "must be bool or None"
            )

        if (
            self.impulse_expansion_match is not None
            and not isinstance(
                self.impulse_expansion_match,
                bool,
            )
        ):
            raise ValueError(
                "impulse_expansion_match "
                "must be bool or None"
            )

        if (
            self.participation_reference_sessions
            is not None
            and self.participation_reference_sessions < 0
        ):
            raise ValueError(
                "participation_reference_sessions "
                "cannot be negative"
            )

        nonnegative_values = (
            (
                "trigger_open",
                self.trigger_open,
            ),
            (
                "trigger_high",
                self.trigger_high,
            ),
            (
                "trigger_low",
                self.trigger_low,
            ),
            (
                "trigger_close",
                self.trigger_close,
            ),
            (
                "trigger_volume",
                self.trigger_volume,
            ),
            (
                "structure_reference_level",
                self.structure_reference_level,
            ),
            (
                "structure_break_level",
                self.structure_break_level,
            ),
            (
                "impulse_body",
                self.impulse_body,
            ),
            (
                "impulse_median_body",
                self.impulse_median_body,
            ),
            (
                "impulse_body_atr_ratio",
                self.impulse_body_atr_ratio,
            ),
            (
                "participation_avg_slot_volume",
                self.participation_avg_slot_volume,
            ),
            (
                "participation_median_slot_volume",
                self.participation_median_slot_volume,
            ),
            (
                "participation_rvol",
                self.participation_rvol,
            ),
        )

        for name, value in nonnegative_values:
            if (
                value is not None
                and value < 0
            ):
                raise ValueError(
                    f"{name} cannot be negative"
                )

        if (
            self.trigger_high is not None
            and self.trigger_low is not None
            and self.trigger_high < self.trigger_low
        ):
            raise ValueError(
                "trigger_high cannot be lower "
                "than trigger_low"
            )

        if (
            self.trigger_open is not None
            and self.trigger_high is not None
            and self.trigger_open > self.trigger_high
        ):
            raise ValueError(
                "trigger_open cannot exceed "
                "trigger_high"
            )

        if (
            self.trigger_open is not None
            and self.trigger_low is not None
            and self.trigger_open < self.trigger_low
        ):
            raise ValueError(
                "trigger_open cannot be below "
                "trigger_low"
            )

        if (
            self.trigger_close is not None
            and self.trigger_high is not None
            and self.trigger_close > self.trigger_high
        ):
            raise ValueError(
                "trigger_close cannot exceed "
                "trigger_high"
            )

        if (
            self.trigger_close is not None
            and self.trigger_low is not None
            and self.trigger_close < self.trigger_low
        ):
            raise ValueError(
                "trigger_close cannot be below "
                "trigger_low"
            )

        quality_nonnegative_values = (
            ("absolute_flow_strength", self.absolute_flow_strength),
            ("relative_flow_strength", self.relative_flow_strength),
            ("vwap_distance_atr", self.vwap_distance_atr),
            ("opening_evidence", self.opening_evidence),
            ("off_exchange_cluster_score", self.off_exchange_cluster_score),
            ("iv_vs_realized_vol", self.iv_vs_realized_vol),
            ("target_expiry_iv", self.target_expiry_iv),
            ("iv_30d", self.iv_30d),
            ("term_structure_ratio", self.term_structure_ratio),
        )

        for name, value in quality_nonnegative_values:
            if value is not None and value < 0:
                raise ValueError(
                    f"{name} cannot be negative"
                )

        if (
            self.sweep_ratio is not None
            and not 0 <= self.sweep_ratio <= 1
        ):
            raise ValueError(
                "sweep_ratio must be between 0 and 1"
            )

        if (
            self.opening_evidence is not None
            and self.opening_evidence > 10
        ):
            raise ValueError(
                "opening_evidence cannot exceed 10"
            )

        if (
            self.iv_percentile is not None
            and not 0 <= self.iv_percentile <= 100
        ):
            raise ValueError(
                "iv_percentile must be between 0 and 100"
            )

        for name, value in (
            (
                "target_expiry_gex_alignment",
                self.target_expiry_gex_alignment,
            ),
            (
                "negative_gamma_regime",
                self.negative_gamma_regime,
            ),
            (
                "term_structure_inversion",
                self.term_structure_inversion,
            ),
        ):
            if (
                value is not None
                and not isinstance(value, bool)
            ):
                raise ValueError(
                    f"{name} must be bool or None"
                )

        quality_statuses = (
            (
                "absolute_flow_strength_status",
                self.absolute_flow_strength_status,
            ),
            (
                "relative_flow_strength_status",
                self.relative_flow_strength_status,
            ),
            (
                "vwap_distance_atr_status",
                self.vwap_distance_atr_status,
            ),
            (
                "sweep_ratio_status",
                self.sweep_ratio_status,
            ),
            (
                "opening_evidence_status",
                self.opening_evidence_status,
            ),
            (
                "risk_reversal_status",
                self.risk_reversal_status,
            ),
            (
                "target_expiry_gex_alignment_status",
                self.target_expiry_gex_alignment_status,
            ),
            (
                "negative_gamma_regime_status",
                self.negative_gamma_regime_status,
            ),
            (
                "off_exchange_cluster_score_status",
                self.off_exchange_cluster_score_status,
            ),
            (
                "directional_flow_confirmation_status",
                self.directional_flow_confirmation_status,
            ),
            (
                "iv_percentile_status",
                self.iv_percentile_status,
            ),
            (
                "term_structure_inversion_status",
                self.term_structure_inversion_status,
            ),
            (
                "iv_vs_realized_vol_status",
                self.iv_vs_realized_vol_status,
            ),
        )

        for name, value in quality_statuses:
            if (
                value is not None
                and not isinstance(value, GateStatus)
            ):
                raise ValueError(
                    f"{name} must be GateStatus or None"
                )

# ==================================================
# FLOW SNAPSHOT
# ==================================================


@dataclass(frozen=True)
class FlowSnapshot:
    ticker: str
    trading_date_et: date
    captured_at: datetime
    target_expiry: date

    call_ask_premium: float
    put_ask_premium: float
    net_flow: float

    call_bid_premium: float
    put_bid_premium: float

    bullish_premium: float
    bearish_premium: float
    directional_net: float

    raw_alert_count: int
    clean_alert_count: int
    deduped_alert_count: int

    flow_dedup_level: str
    trade_overlap_detected: bool

    sweep_alert_count: int
    opening_alert_count: int

    provider: str
    feed: str

    source_timestamp: datetime | None
    fetched_at: datetime | None

    freshness_status: str

    total_premium: float | None = None
    sweep_premium: float | None = None

    id: int | None = None

    def __post_init__(self):
        if not self.ticker.strip():
            raise ValueError(
                "ticker cannot be empty"
            )

        if (
            self.target_expiry
            < self.trading_date_et
        ):
            raise ValueError(
                "target_expiry cannot be "
                "before trading_date_et"
            )

        for name, value in (
            (
                "call_ask_premium",
                self.call_ask_premium,
            ),
            (
                "put_ask_premium",
                self.put_ask_premium,
            ),
            (
                "call_bid_premium",
                self.call_bid_premium,
            ),
            (
                "put_bid_premium",
                self.put_bid_premium,
            ),
            (
                "bullish_premium",
                self.bullish_premium,
            ),
            (
                "bearish_premium",
                self.bearish_premium,
            ),
        ):
            if value < 0:
                raise ValueError(
                    f"{name} cannot be negative"
                )

        for name, value in (
            ("total_premium", self.total_premium),
            ("sweep_premium", self.sweep_premium),
        ):
            if value is not None and value < 0:
                raise ValueError(
                    f"{name} cannot be negative"
                )

        if (
            self.total_premium is not None
            and self.sweep_premium is not None
            and self.sweep_premium > self.total_premium
        ):
            raise ValueError(
                "sweep_premium cannot exceed total_premium"
            )

        for name, value in (
            (
                "raw_alert_count",
                self.raw_alert_count,
            ),
            (
                "clean_alert_count",
                self.clean_alert_count,
            ),
            (
                "deduped_alert_count",
                self.deduped_alert_count,
            ),
            (
                "sweep_alert_count",
                self.sweep_alert_count,
            ),
            (
                "opening_alert_count",
                self.opening_alert_count,
            ),
        ):
            if value < 0:
                raise ValueError(
                    f"{name} cannot be negative"
                )

        if (
            self.clean_alert_count
            > self.raw_alert_count
        ):
            raise ValueError(
                "clean_alert_count cannot exceed "
                "raw_alert_count"
            )

        if (
            self.deduped_alert_count
            > self.clean_alert_count
        ):
            raise ValueError(
                "deduped_alert_count cannot exceed "
                "clean_alert_count"
            )

        valid_dedup_levels = {
            "trade_level",
            "trade_overlap_flagged",
            "alert_uuid",
            "alert_composite",
        }

        if (
            self.flow_dedup_level
            not in valid_dedup_levels
        ):
            raise ValueError(
                "Unsupported flow_dedup_level: "
                f"{self.flow_dedup_level!r}"
            )

        if not isinstance(
            self.trade_overlap_detected,
            bool,
        ):
            raise ValueError(
                "trade_overlap_detected must be bool"
            )

        if not self.provider.strip():
            raise ValueError(
                "provider cannot be empty"
            )

        if not self.feed.strip():
            raise ValueError(
                "feed cannot be empty"
            )

        valid_freshness_statuses = {
            "PASS",
            "DEGRADED",
            "BLOCKED",
            "UNKNOWN",
        }

        if (
            self.freshness_status
            not in valid_freshness_statuses
        ):
            raise ValueError(
                "Unsupported freshness_status: "
                f"{self.freshness_status!r}"
            )

        for name, value in (
            (
                "captured_at",
                self.captured_at,
            ),
            (
                "source_timestamp",
                self.source_timestamp,
            ),
            (
                "fetched_at",
                self.fetched_at,
            ),
        ):
            if (
                value is not None
                and value.tzinfo is None
            ):
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

        if (
            self.source_timestamp is not None
            and self.fetched_at is not None
            and self.fetched_at
            < self.source_timestamp
        ):
            raise ValueError(
                "fetched_at cannot be earlier "
                "than source_timestamp"
            )


# ==================================================
# OUTCOME
# ==================================================


@dataclass(frozen=True)
class Outcome:
    signal_id: int
    outcome_scope: OutcomeScope
    checkpoint_name: str

    outcome_status: OutcomeStatus = OutcomeStatus.PENDING

    scheduled_at: datetime | None = None
    observed_at: datetime | None = None

    baseline_at: datetime | None = None

    baseline_underlying_price: float | None = None
    observed_underlying_price: float | None = None

    underlying_raw_return: float | None = None
    underlying_directional_return: float | None = None

    contract_symbol: str | None = None

    baseline_option_bid: float | None = None
    baseline_option_ask: float | None = None
    baseline_option_mark: float | None = None

    observed_option_bid: float | None = None
    observed_option_ask: float | None = None
    observed_option_mark: float | None = None

    option_executable_return: float | None = None
    option_mark_return: float | None = None

    settlement_value: float | None = None

    stock_data_provider: str | None = None
    stock_data_feed: str | None = None

    options_data_provider: str | None = None
    options_data_feed: str | None = None

    id: int | None = None

    def __post_init__(self):
        if self.signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        if not self.checkpoint_name.strip():
            raise ValueError(
                "checkpoint_name cannot be empty"
            )

        for name, value in (
            ("scheduled_at", self.scheduled_at),
            ("observed_at", self.observed_at),
            ("baseline_at", self.baseline_at),
        ):
            if (
                value is not None
                and value.tzinfo is None
            ):
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

        for name, value in (
            (
                "baseline_underlying_price",
                self.baseline_underlying_price,
            ),
            (
                "observed_underlying_price",
                self.observed_underlying_price,
            ),
            (
                "baseline_option_bid",
                self.baseline_option_bid,
            ),
            (
                "baseline_option_ask",
                self.baseline_option_ask,
            ),
            (
                "baseline_option_mark",
                self.baseline_option_mark,
            ),
            (
                "observed_option_bid",
                self.observed_option_bid,
            ),
            (
                "observed_option_ask",
                self.observed_option_ask,
            ),
            (
                "observed_option_mark",
                self.observed_option_mark,
            ),
            (
                "settlement_value",
                self.settlement_value,
            ),
        ):
            if (
                value is not None
                and value < 0
            ):
                raise ValueError(
                    f"{name} cannot be negative"
                )


# ==================================================
# POSITION
# ==================================================


@dataclass(frozen=True)
class Position:
    signal_id: int

    contract_symbol: str
    option_right: OptionRight

    strike: float
    expiry: date

    quantity: int
    status: PositionStatus

    execution_mode: ExecutionMode = ExecutionMode.PAPER

    opened_at: datetime | None = None
    closed_at: datetime | None = None

    entry_price: float | None = None
    exit_price: float | None = None

    entry_bid: float | None = None
    entry_ask: float | None = None
    entry_mark: float | None = None

    exit_bid: float | None = None
    exit_ask: float | None = None
    exit_mark: float | None = None

    id: int | None = None

    def __post_init__(self):
        if self.signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        if not self.contract_symbol.strip():
            raise ValueError(
                "contract_symbol cannot be empty"
            )

        if self.strike < 0:
            raise ValueError(
                "strike cannot be negative"
            )

        if self.quantity <= 0:
            raise ValueError(
                "quantity must be > 0"
            )

        if self.execution_mode != ExecutionMode.PAPER:
            raise ValueError(
                "weekly_v1 supports PAPER execution only"
            )

        for name, value in (
            ("opened_at", self.opened_at),
            ("closed_at", self.closed_at),
        ):
            if (
                value is not None
                and value.tzinfo is None
            ):
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

        for name, value in (
            ("entry_price", self.entry_price),
            ("exit_price", self.exit_price),
            ("entry_bid", self.entry_bid),
            ("entry_ask", self.entry_ask),
            ("entry_mark", self.entry_mark),
            ("exit_bid", self.exit_bid),
            ("exit_ask", self.exit_ask),
            ("exit_mark", self.exit_mark),
        ):
            if (
                value is not None
                and value < 0
            ):
                raise ValueError(
                    f"{name} cannot be negative"
                )

        if (
            self.opened_at is not None
            and self.closed_at is not None
            and self.closed_at < self.opened_at
        ):
            raise ValueError(
                "closed_at cannot be earlier than opened_at"
            )


# ==================================================
# TRADE
# ==================================================


@dataclass(frozen=True)
class Trade:
    position_id: int
    signal_id: int

    intent: TradeIntent
    side: TradeSide

    quantity: int

    requested_at: datetime
    status: TradeStatus

    execution_mode: ExecutionMode = ExecutionMode.PAPER

    filled_at: datetime | None = None
    fill_price: float | None = None

    bid_at_action: float | None = None
    ask_at_action: float | None = None
    mark_at_action: float | None = None

    options_data_provider: str | None = None
    options_data_feed: str | None = None

    broker_order_id: str | None = None

    id: int | None = None

    def __post_init__(self):
        if self.position_id < 1:
            raise ValueError(
                "position_id must be >= 1"
            )

        if self.signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        if self.quantity <= 0:
            raise ValueError(
                "quantity must be > 0"
            )

        if self.execution_mode != ExecutionMode.PAPER:
            raise ValueError(
                "weekly_v1 supports PAPER execution only"
            )

        if self.requested_at.tzinfo is None:
            raise ValueError(
                "requested_at must be timezone-aware"
            )

        if (
            self.filled_at is not None
            and self.filled_at.tzinfo is None
        ):
            raise ValueError(
                "filled_at must be timezone-aware"
            )

        if (
            self.filled_at is not None
            and self.filled_at < self.requested_at
        ):
            raise ValueError(
                "filled_at cannot be earlier than requested_at"
            )

        for name, value in (
            ("fill_price", self.fill_price),
            ("bid_at_action", self.bid_at_action),
            ("ask_at_action", self.ask_at_action),
            ("mark_at_action", self.mark_at_action),
        ):
            if (
                value is not None
                and value < 0
            ):
                raise ValueError(
                    f"{name} cannot be negative"
                )


# ==================================================
# DATA HEALTH
# ==================================================


@dataclass(frozen=True)
class DataHealth:
    captured_at: datetime
    component: str
    status: DataHealthStatus

    trading_date_et: date | None = None
    ticker: str | None = None

    provider: str | None = None
    feed: str | None = None

    message: str | None = None

    id: int | None = None

    def __post_init__(self):
        if self.captured_at.tzinfo is None:
            raise ValueError(
                "captured_at must be timezone-aware"
            )

        if not self.component.strip():
            raise ValueError(
                "component cannot be empty"
            )

        if (
            self.ticker is not None
            and not self.ticker.strip()
        ):
            raise ValueError(
                "ticker cannot be empty when provided"
            )

        if (
            self.provider is not None
            and not self.provider.strip()
        ):
            raise ValueError(
                "provider cannot be empty when provided"
            )

        if (
            self.feed is not None
            and not self.feed.strip()
        ):
            raise ValueError(
                "feed cannot be empty when provided"
            )
