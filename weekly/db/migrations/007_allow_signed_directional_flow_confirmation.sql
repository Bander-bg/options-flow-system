ALTER TABLE signal_features RENAME TO signal_features_old;

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
        ), price_action_bar_at TEXT, trigger_open REAL
CHECK (
    trigger_open IS NULL
    OR trigger_open >= 0
), trigger_high REAL
CHECK (
    trigger_high IS NULL
    OR trigger_high >= 0
), trigger_low REAL
CHECK (
    trigger_low IS NULL
    OR trigger_low >= 0
), trigger_close REAL
CHECK (
    trigger_close IS NULL
    OR trigger_close >= 0
), trigger_volume REAL
CHECK (
    trigger_volume IS NULL
    OR trigger_volume >= 0
), structure_reference_level REAL
CHECK (
    structure_reference_level IS NULL
    OR structure_reference_level >= 0
), structure_break_level REAL
CHECK (
    structure_break_level IS NULL
    OR structure_break_level >= 0
), impulse_body REAL
CHECK (
    impulse_body IS NULL
    OR impulse_body >= 0
), impulse_median_body REAL
CHECK (
    impulse_median_body IS NULL
    OR impulse_median_body >= 0
), impulse_body_atr_ratio REAL
CHECK (
    impulse_body_atr_ratio IS NULL
    OR impulse_body_atr_ratio >= 0
), participation_avg_slot_volume REAL
CHECK (
    participation_avg_slot_volume IS NULL
    OR participation_avg_slot_volume >= 0
), participation_rvol REAL
CHECK (
    participation_rvol IS NULL
    OR participation_rvol >= 0
), impulse_engulfing_match INTEGER
CHECK (
    impulse_engulfing_match IS NULL
    OR impulse_engulfing_match IN (0, 1)
), impulse_expansion_match INTEGER
CHECK (
    impulse_expansion_match IS NULL
    OR impulse_expansion_match IN (0, 1)
), participation_median_slot_volume REAL
CHECK (
    participation_median_slot_volume IS NULL
    OR participation_median_slot_volume >= 0
), participation_reference_sessions INTEGER
CHECK (
    participation_reference_sessions IS NULL
    OR participation_reference_sessions >= 0
), absolute_flow_strength REAL
CHECK (
    absolute_flow_strength IS NULL
    OR absolute_flow_strength >= 0
), relative_flow_strength REAL
CHECK (
    relative_flow_strength IS NULL
    OR relative_flow_strength >= 0
), vwap_distance_atr REAL
CHECK (
    vwap_distance_atr IS NULL
    OR vwap_distance_atr >= 0
), sweep_ratio REAL
CHECK (
    sweep_ratio IS NULL
    OR (
        sweep_ratio >= 0
        AND sweep_ratio <= 1
    )
), opening_evidence REAL
CHECK (
    opening_evidence IS NULL
    OR (
        opening_evidence >= 0
        AND opening_evidence <= 10
    )
), risk_reversal REAL, target_expiry_gex_alignment INTEGER
CHECK (
    target_expiry_gex_alignment IS NULL
    OR target_expiry_gex_alignment IN (0, 1)
), negative_gamma_regime INTEGER
CHECK (
    negative_gamma_regime IS NULL
    OR negative_gamma_regime IN (0, 1)
), off_exchange_cluster_score REAL
CHECK (
    off_exchange_cluster_score IS NULL
    OR off_exchange_cluster_score >= 0
), directional_flow_confirmation REAL, term_structure_inversion INTEGER
CHECK (
    term_structure_inversion IS NULL
    OR term_structure_inversion IN (0, 1)
), iv_vs_realized_vol REAL
CHECK (
    iv_vs_realized_vol IS NULL
    OR iv_vs_realized_vol >= 0
), target_expiry_iv REAL
CHECK (
    target_expiry_iv IS NULL
    OR target_expiry_iv >= 0
), iv_30d REAL
CHECK (
    iv_30d IS NULL
    OR iv_30d >= 0
), term_structure_ratio REAL
CHECK (
    term_structure_ratio IS NULL
    OR term_structure_ratio >= 0
), absolute_flow_strength_status TEXT
CHECK (
    absolute_flow_strength_status IS NULL
    OR absolute_flow_strength_status IN ('PASS', 'FAIL', 'UNKNOWN')
), relative_flow_strength_status TEXT
CHECK (
    relative_flow_strength_status IS NULL
    OR relative_flow_strength_status IN ('PASS', 'FAIL', 'UNKNOWN')
), vwap_distance_atr_status TEXT
CHECK (
    vwap_distance_atr_status IS NULL
    OR vwap_distance_atr_status IN ('PASS', 'FAIL', 'UNKNOWN')
), sweep_ratio_status TEXT
CHECK (
    sweep_ratio_status IS NULL
    OR sweep_ratio_status IN ('PASS', 'FAIL', 'UNKNOWN')
), opening_evidence_status TEXT
CHECK (
    opening_evidence_status IS NULL
    OR opening_evidence_status IN ('PASS', 'FAIL', 'UNKNOWN')
), risk_reversal_status TEXT
CHECK (
    risk_reversal_status IS NULL
    OR risk_reversal_status IN ('PASS', 'FAIL', 'UNKNOWN')
), target_expiry_gex_alignment_status TEXT
CHECK (
    target_expiry_gex_alignment_status IS NULL
    OR target_expiry_gex_alignment_status IN ('PASS', 'FAIL', 'UNKNOWN')
), negative_gamma_regime_status TEXT
CHECK (
    negative_gamma_regime_status IS NULL
    OR negative_gamma_regime_status IN ('PASS', 'FAIL', 'UNKNOWN')
), off_exchange_cluster_score_status TEXT
CHECK (
    off_exchange_cluster_score_status IS NULL
    OR off_exchange_cluster_score_status IN ('PASS', 'FAIL', 'UNKNOWN')
), directional_flow_confirmation_status TEXT
CHECK (
    directional_flow_confirmation_status IS NULL
    OR directional_flow_confirmation_status IN ('PASS', 'FAIL', 'UNKNOWN')
), iv_percentile_status TEXT
CHECK (
    iv_percentile_status IS NULL
    OR iv_percentile_status IN ('PASS', 'FAIL', 'UNKNOWN')
), term_structure_inversion_status TEXT
CHECK (
    term_structure_inversion_status IS NULL
    OR term_structure_inversion_status IN ('PASS', 'FAIL', 'UNKNOWN')
), iv_vs_realized_vol_status TEXT
CHECK (
    iv_vs_realized_vol_status IS NULL
    OR iv_vs_realized_vol_status IN ('PASS', 'FAIL', 'UNKNOWN')
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

INSERT INTO signal_features SELECT * FROM signal_features_old;

DROP TABLE signal_features_old;

CREATE INDEX idx_signal_features_signal
ON signal_features (
    signal_id,
    evaluation_sequence
);
