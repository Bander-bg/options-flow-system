ALTER TABLE signal_features
ADD COLUMN impulse_engulfing_match INTEGER
CHECK (
    impulse_engulfing_match IS NULL
    OR impulse_engulfing_match IN (0, 1)
);


ALTER TABLE signal_features
ADD COLUMN impulse_expansion_match INTEGER
CHECK (
    impulse_expansion_match IS NULL
    OR impulse_expansion_match IN (0, 1)
);


ALTER TABLE signal_features
ADD COLUMN participation_median_slot_volume REAL
CHECK (
    participation_median_slot_volume IS NULL
    OR participation_median_slot_volume >= 0
);


ALTER TABLE signal_features
ADD COLUMN participation_reference_sessions INTEGER
CHECK (
    participation_reference_sessions IS NULL
    OR participation_reference_sessions >= 0
);