-- weekly_v1
-- Initial persistence schema.
-- schema_migrations is created by migration_runner.py itself.

CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    strategy_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,

    ticker TEXT NOT NULL,
    trading_date_et TEXT NOT NULL,
    target_expiry TEXT NOT NULL,

    direction TEXT NOT NULL
        CHECK (
            direction IN (
                'bullish',
                'bearish'
            )
        ),

    signal_sign INTEGER NOT NULL
        CHECK (
            signal_sign IN (-1, 1)
        ),

    candidate_sequence INTEGER NOT NULL
        CHECK (
            candidate_sequence >= 1
        ),

    state TEXT NOT NULL
        CHECK (
            state IN (
                'CANDIDATE',
                'INVALIDATED',
                'REJECTED',
                'DATA_BLOCKED',
                'DATA_UNRESOLVED',
                'CONFIRMED',
                'ACTIVE',
                'ACCELERATED',
                'EXPIRED'
            )
        ),

    candidate_at TEXT NOT NULL,

    requested_confirmation_deadline_at TEXT,
    confirmation_deadline_at TEXT,

    confirmed_at TEXT,
    terminal_at TEXT,

    terminal_reason TEXT,

    net_flow_at_candidate REAL,
    net_flow_at_confirmation REAL,

    flow_dedup_level TEXT,

    stock_data_provider TEXT,
    stock_data_feed TEXT,

    options_data_provider TEXT,
    options_data_feed TEXT,

    theta_convention_status TEXT,

    scenario_return_enabled INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            scenario_return_enabled IN (0, 1)
        ),

    created_at TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    updated_at TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    UNIQUE (
        strategy_version,
        ticker,
        trading_date_et,
        target_expiry,
        direction,
        candidate_sequence
    )
);


CREATE TABLE signal_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    signal_id INTEGER NOT NULL,

    evaluation_sequence INTEGER NOT NULL
        CHECK (
            evaluation_sequence >= 1
        ),

    captured_at TEXT NOT NULL,

    flow_net REAL,
    flow_threshold REAL,

    weekly_vwap REAL,
    underlying_price REAL,

    vwap_status TEXT
        CHECK (
            vwap_status IS NULL
            OR vwap_status IN (
                'PASS',
                'FAIL',
                'UNKNOWN'
            )
        ),

    efficiency_ratio REAL,

    efficiency_ratio_status TEXT
        CHECK (
            efficiency_ratio_status IS NULL
            OR efficiency_ratio_status IN (
                'PASS',
                'FAIL',
                'UNKNOWN'
            )
        ),

    next_earnings_date TEXT,

    earnings_event_risk_status TEXT
        CHECK (
            earnings_event_risk_status IS NULL
            OR earnings_event_risk_status IN (
                'PASS',
                'FAIL',
                'UNKNOWN'
            )
        ),

    expected_move REAL,
    expected_move_perc REAL,

    selected_contract_symbol TEXT,
    selected_contract_right TEXT,
    selected_contract_strike REAL,

    selected_contract_bid REAL,
    selected_contract_ask REAL,
    selected_contract_mark REAL,

    selected_contract_delta REAL,
    selected_contract_gamma REAL,
    selected_contract_theta REAL,
    selected_contract_vega REAL,
    selected_contract_iv REAL,

    selected_contract_spread_pct REAL,
    selected_contract_quote_age_seconds REAL,

    eligible_contract_status TEXT
        CHECK (
            eligible_contract_status IS NULL
            OR eligible_contract_status IN (
                'PASS',
                'FAIL',
                'UNKNOWN'
            )
        ),

    structure_status TEXT
        CHECK (
            structure_status IS NULL
            OR structure_status IN (
                'PASS',
                'FAIL',
                'UNKNOWN'
            )
        ),

    impulse_status TEXT
        CHECK (
            impulse_status IS NULL
            OR impulse_status IN (
                'PASS',
                'FAIL',
                'UNKNOWN'
            )
        ),

    participation_status TEXT
        CHECK (
            participation_status IS NULL
            OR participation_status IN (
                'PASS',
                'FAIL',
                'UNKNOWN'
            )
        ),

    price_action_pass_count INTEGER,

    price_action_status TEXT
        CHECK (
            price_action_status IS NULL
            OR price_action_status IN (
                'PASS',
                'FAIL',
                'UNKNOWN'
            )
        ),

    atr_1h REAL,
    atr_15m REAL,

    iv_percentile REAL,

    base_score REAL,
    volatility_penalty REAL,
    final_score REAL,

    coverage_points REAL,
    coverage_pct REAL,

    raw_grade TEXT
        CHECK (
            raw_grade IS NULL
            OR raw_grade IN (
                'A',
                'B',
                'C'
            )
        ),

    final_grade TEXT
        CHECK (
            final_grade IS NULL
            OR final_grade IN (
                'A',
                'B',
                'C',
                'UNRATED'
            )
        ),

    FOREIGN KEY (
        signal_id
    )
        REFERENCES signals(id)
        ON DELETE CASCADE,

    UNIQUE (
        signal_id,
        evaluation_sequence
    )
);


CREATE TABLE flow_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    ticker TEXT NOT NULL,
    trading_date_et TEXT NOT NULL,
    captured_at TEXT NOT NULL,

    target_expiry TEXT NOT NULL,

    call_ask_premium REAL NOT NULL
        DEFAULT 0,

    put_ask_premium REAL NOT NULL
        DEFAULT 0,

    net_flow REAL NOT NULL,

    alert_count INTEGER NOT NULL
        DEFAULT 0,

    flow_dedup_level TEXT NOT NULL,

    source_provider TEXT NOT NULL
        DEFAULT 'UNUSUAL_WHALES',

    created_at TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    UNIQUE (
        ticker,
        trading_date_et,
        captured_at
    )
);


CREATE TABLE outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    signal_id INTEGER NOT NULL,

    outcome_scope TEXT NOT NULL
        CHECK (
            outcome_scope IN (
                'CANDIDATE',
                'RESOLUTION'
            )
        ),

    checkpoint_name TEXT NOT NULL,

    scheduled_at TEXT,
    observed_at TEXT,

    baseline_at TEXT,

    baseline_underlying_price REAL,
    observed_underlying_price REAL,

    underlying_raw_return REAL,
    underlying_directional_return REAL,

    contract_symbol TEXT,

    baseline_option_bid REAL,
    baseline_option_ask REAL,
    baseline_option_mark REAL,

    observed_option_bid REAL,
    observed_option_ask REAL,
    observed_option_mark REAL,

    option_executable_return REAL,
    option_mark_return REAL,

    settlement_value REAL,

    stock_data_provider TEXT,
    stock_data_feed TEXT,

    options_data_provider TEXT,
    options_data_feed TEXT,

    outcome_status TEXT NOT NULL
        DEFAULT 'PENDING'
        CHECK (
            outcome_status IN (
                'PENDING',
                'OBSERVED',
                'UNAVAILABLE',
                'EXPIRED'
            )
        ),

    created_at TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    updated_at TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    FOREIGN KEY (
        signal_id
    )
        REFERENCES signals(id)
        ON DELETE CASCADE,

    UNIQUE (
        signal_id,
        outcome_scope,
        checkpoint_name
    )
);


CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    signal_id INTEGER NOT NULL,

    execution_mode TEXT NOT NULL
        DEFAULT 'PAPER'
        CHECK (
            execution_mode = 'PAPER'
        ),

    contract_symbol TEXT NOT NULL,

    option_right TEXT NOT NULL
        CHECK (
            option_right IN (
                'call',
                'put'
            )
        ),

    strike REAL NOT NULL,
    expiry TEXT NOT NULL,

    quantity INTEGER NOT NULL
        CHECK (
            quantity > 0
        ),

    status TEXT NOT NULL
        CHECK (
            status IN (
                'OPEN',
                'CLOSED',
                'CANCELLED'
            )
        ),

    opened_at TEXT,
    closed_at TEXT,

    entry_price REAL,
    exit_price REAL,

    entry_bid REAL,
    entry_ask REAL,
    entry_mark REAL,

    exit_bid REAL,
    exit_ask REAL,
    exit_mark REAL,

    created_at TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    updated_at TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    FOREIGN KEY (
        signal_id
    )
        REFERENCES signals(id)
        ON DELETE RESTRICT
);


CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    position_id INTEGER NOT NULL,
    signal_id INTEGER NOT NULL,

    execution_mode TEXT NOT NULL
        DEFAULT 'PAPER'
        CHECK (
            execution_mode = 'PAPER'
        ),

    intent TEXT NOT NULL
        CHECK (
            intent IN (
                'OPEN',
                'CLOSE'
            )
        ),

    side TEXT NOT NULL
        CHECK (
            side IN (
                'BUY',
                'SELL'
            )
        ),

    quantity INTEGER NOT NULL
        CHECK (
            quantity > 0
        ),

    requested_at TEXT NOT NULL,
    filled_at TEXT,

    fill_price REAL,

    bid_at_action REAL,
    ask_at_action REAL,
    mark_at_action REAL,

    options_data_provider TEXT,
    options_data_feed TEXT,

    broker_order_id TEXT,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'REQUESTED',
                'FILLED',
                'PARTIALLY_FILLED',
                'CANCELLED',
                'REJECTED'
            )
        ),

    created_at TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        ),

    FOREIGN KEY (
        position_id
    )
        REFERENCES positions(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (
        signal_id
    )
        REFERENCES signals(id)
        ON DELETE RESTRICT,

    UNIQUE (
        broker_order_id
    )
);


CREATE TABLE data_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    captured_at TEXT NOT NULL,

    trading_date_et TEXT,

    ticker TEXT,

    component TEXT NOT NULL,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'PASS',
                'DEGRADED',
                'BLOCKED',
                'UNKNOWN'
            )
        ),

    provider TEXT,
    feed TEXT,

    message TEXT,

    created_at TEXT NOT NULL
        DEFAULT (
            strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        )
);


CREATE INDEX idx_signals_ticker_date
ON signals (
    ticker,
    trading_date_et
);


CREATE INDEX idx_signals_state
ON signals (
    state
);


CREATE INDEX idx_signals_target_expiry
ON signals (
    target_expiry
);


CREATE INDEX idx_signal_features_signal
ON signal_features (
    signal_id,
    evaluation_sequence
);


CREATE INDEX idx_flow_snapshots_ticker_date
ON flow_snapshots (
    ticker,
    trading_date_et
);


CREATE INDEX idx_outcomes_signal
ON outcomes (
    signal_id,
    outcome_scope
);


CREATE INDEX idx_outcomes_status
ON outcomes (
    outcome_status
);


CREATE INDEX idx_positions_signal
ON positions (
    signal_id
);


CREATE INDEX idx_positions_status
ON positions (
    status
);


CREATE INDEX idx_trades_position
ON trades (
    position_id
);


CREATE INDEX idx_data_health_time
ON data_health (
    captured_at
);


CREATE INDEX idx_data_health_component
ON data_health (
    component,
    status
);