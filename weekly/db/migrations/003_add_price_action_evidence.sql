ALTER TABLE signal_features
ADD COLUMN price_action_bar_at TEXT;


ALTER TABLE signal_features
ADD COLUMN trigger_open REAL
CHECK (
    trigger_open IS NULL
    OR trigger_open >= 0
);


ALTER TABLE signal_features
ADD COLUMN trigger_high REAL
CHECK (
    trigger_high IS NULL
    OR trigger_high >= 0
);


ALTER TABLE signal_features
ADD COLUMN trigger_low REAL
CHECK (
    trigger_low IS NULL
    OR trigger_low >= 0
);


ALTER TABLE signal_features
ADD COLUMN trigger_close REAL
CHECK (
    trigger_close IS NULL
    OR trigger_close >= 0
);


ALTER TABLE signal_features
ADD COLUMN trigger_volume REAL
CHECK (
    trigger_volume IS NULL
    OR trigger_volume >= 0
);


ALTER TABLE signal_features
ADD COLUMN structure_reference_level REAL
CHECK (
    structure_reference_level IS NULL
    OR structure_reference_level >= 0
);


ALTER TABLE signal_features
ADD COLUMN structure_break_level REAL
CHECK (
    structure_break_level IS NULL
    OR structure_break_level >= 0
);


ALTER TABLE signal_features
ADD COLUMN impulse_body REAL
CHECK (
    impulse_body IS NULL
    OR impulse_body >= 0
);


ALTER TABLE signal_features
ADD COLUMN impulse_median_body REAL
CHECK (
    impulse_median_body IS NULL
    OR impulse_median_body >= 0
);


ALTER TABLE signal_features
ADD COLUMN impulse_body_atr_ratio REAL
CHECK (
    impulse_body_atr_ratio IS NULL
    OR impulse_body_atr_ratio >= 0
);


ALTER TABLE signal_features
ADD COLUMN participation_avg_slot_volume REAL
CHECK (
    participation_avg_slot_volume IS NULL
    OR participation_avg_slot_volume >= 0
);


ALTER TABLE signal_features
ADD COLUMN participation_rvol REAL
CHECK (
    participation_rvol IS NULL
    OR participation_rvol >= 0
);