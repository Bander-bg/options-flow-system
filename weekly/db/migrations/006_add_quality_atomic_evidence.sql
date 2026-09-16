ALTER TABLE signal_features
ADD COLUMN absolute_flow_strength REAL
CHECK (
    absolute_flow_strength IS NULL
    OR absolute_flow_strength >= 0
);

ALTER TABLE signal_features
ADD COLUMN relative_flow_strength REAL
CHECK (
    relative_flow_strength IS NULL
    OR relative_flow_strength >= 0
);

ALTER TABLE signal_features
ADD COLUMN vwap_distance_atr REAL
CHECK (
    vwap_distance_atr IS NULL
    OR vwap_distance_atr >= 0
);

ALTER TABLE signal_features
ADD COLUMN sweep_ratio REAL
CHECK (
    sweep_ratio IS NULL
    OR (
        sweep_ratio >= 0
        AND sweep_ratio <= 1
    )
);

ALTER TABLE signal_features
ADD COLUMN opening_evidence REAL
CHECK (
    opening_evidence IS NULL
    OR (
        opening_evidence >= 0
        AND opening_evidence <= 10
    )
);

ALTER TABLE signal_features
ADD COLUMN risk_reversal REAL;

ALTER TABLE signal_features
ADD COLUMN target_expiry_gex_alignment INTEGER
CHECK (
    target_expiry_gex_alignment IS NULL
    OR target_expiry_gex_alignment IN (0, 1)
);

ALTER TABLE signal_features
ADD COLUMN negative_gamma_regime INTEGER
CHECK (
    negative_gamma_regime IS NULL
    OR negative_gamma_regime IN (0, 1)
);

ALTER TABLE signal_features
ADD COLUMN off_exchange_cluster_score REAL
CHECK (
    off_exchange_cluster_score IS NULL
    OR off_exchange_cluster_score >= 0
);

ALTER TABLE signal_features
ADD COLUMN directional_flow_confirmation REAL
CHECK (
    directional_flow_confirmation IS NULL
    OR directional_flow_confirmation >= 0
);

ALTER TABLE signal_features
ADD COLUMN term_structure_inversion INTEGER
CHECK (
    term_structure_inversion IS NULL
    OR term_structure_inversion IN (0, 1)
);

ALTER TABLE signal_features
ADD COLUMN iv_vs_realized_vol REAL
CHECK (
    iv_vs_realized_vol IS NULL
    OR iv_vs_realized_vol >= 0
);

ALTER TABLE signal_features
ADD COLUMN target_expiry_iv REAL
CHECK (
    target_expiry_iv IS NULL
    OR target_expiry_iv >= 0
);

ALTER TABLE signal_features
ADD COLUMN iv_30d REAL
CHECK (
    iv_30d IS NULL
    OR iv_30d >= 0
);

ALTER TABLE signal_features
ADD COLUMN term_structure_ratio REAL
CHECK (
    term_structure_ratio IS NULL
    OR term_structure_ratio >= 0
);

ALTER TABLE signal_features
ADD COLUMN absolute_flow_strength_status TEXT
CHECK (
    absolute_flow_strength_status IS NULL
    OR absolute_flow_strength_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN relative_flow_strength_status TEXT
CHECK (
    relative_flow_strength_status IS NULL
    OR relative_flow_strength_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN vwap_distance_atr_status TEXT
CHECK (
    vwap_distance_atr_status IS NULL
    OR vwap_distance_atr_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN sweep_ratio_status TEXT
CHECK (
    sweep_ratio_status IS NULL
    OR sweep_ratio_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN opening_evidence_status TEXT
CHECK (
    opening_evidence_status IS NULL
    OR opening_evidence_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN risk_reversal_status TEXT
CHECK (
    risk_reversal_status IS NULL
    OR risk_reversal_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN target_expiry_gex_alignment_status TEXT
CHECK (
    target_expiry_gex_alignment_status IS NULL
    OR target_expiry_gex_alignment_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN negative_gamma_regime_status TEXT
CHECK (
    negative_gamma_regime_status IS NULL
    OR negative_gamma_regime_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN off_exchange_cluster_score_status TEXT
CHECK (
    off_exchange_cluster_score_status IS NULL
    OR off_exchange_cluster_score_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN directional_flow_confirmation_status TEXT
CHECK (
    directional_flow_confirmation_status IS NULL
    OR directional_flow_confirmation_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN iv_percentile_status TEXT
CHECK (
    iv_percentile_status IS NULL
    OR iv_percentile_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN term_structure_inversion_status TEXT
CHECK (
    term_structure_inversion_status IS NULL
    OR term_structure_inversion_status IN ('PASS', 'FAIL', 'UNKNOWN')
);

ALTER TABLE signal_features
ADD COLUMN iv_vs_realized_vol_status TEXT
CHECK (
    iv_vs_realized_vol_status IS NULL
    OR iv_vs_realized_vol_status IN ('PASS', 'FAIL', 'UNKNOWN')
);
