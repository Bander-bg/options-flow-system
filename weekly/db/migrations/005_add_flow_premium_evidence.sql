ALTER TABLE flow_snapshots
ADD COLUMN total_premium REAL
CHECK (
    total_premium IS NULL
    OR total_premium >= 0
);

ALTER TABLE flow_snapshots
ADD COLUMN sweep_premium REAL
CHECK (
    sweep_premium IS NULL
    OR sweep_premium >= 0
);
