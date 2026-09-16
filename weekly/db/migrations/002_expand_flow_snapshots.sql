ALTER TABLE flow_snapshots
ADD COLUMN call_bid_premium REAL NOT NULL DEFAULT 0
CHECK (call_bid_premium >= 0);

ALTER TABLE flow_snapshots
ADD COLUMN put_bid_premium REAL NOT NULL DEFAULT 0
CHECK (put_bid_premium >= 0);

ALTER TABLE flow_snapshots
ADD COLUMN bullish_premium REAL NOT NULL DEFAULT 0
CHECK (bullish_premium >= 0);

ALTER TABLE flow_snapshots
ADD COLUMN bearish_premium REAL NOT NULL DEFAULT 0
CHECK (bearish_premium >= 0);

ALTER TABLE flow_snapshots
ADD COLUMN directional_net REAL NOT NULL DEFAULT 0;

ALTER TABLE flow_snapshots
ADD COLUMN raw_alert_count INTEGER NOT NULL DEFAULT 0
CHECK (raw_alert_count >= 0);

ALTER TABLE flow_snapshots
ADD COLUMN clean_alert_count INTEGER NOT NULL DEFAULT 0
CHECK (clean_alert_count >= 0);

ALTER TABLE flow_snapshots
ADD COLUMN deduped_alert_count INTEGER NOT NULL DEFAULT 0
CHECK (deduped_alert_count >= 0);

ALTER TABLE flow_snapshots
ADD COLUMN trade_overlap_detected INTEGER NOT NULL DEFAULT 0
CHECK (trade_overlap_detected IN (0, 1));

ALTER TABLE flow_snapshots
ADD COLUMN sweep_alert_count INTEGER NOT NULL DEFAULT 0
CHECK (sweep_alert_count >= 0);

ALTER TABLE flow_snapshots
ADD COLUMN opening_alert_count INTEGER NOT NULL DEFAULT 0
CHECK (opening_alert_count >= 0);

ALTER TABLE flow_snapshots
ADD COLUMN provider TEXT NOT NULL DEFAULT 'UNKNOWN';

ALTER TABLE flow_snapshots
ADD COLUMN feed TEXT NOT NULL DEFAULT 'UNKNOWN';

ALTER TABLE flow_snapshots
ADD COLUMN source_timestamp TEXT;

ALTER TABLE flow_snapshots
ADD COLUMN fetched_at TEXT;

ALTER TABLE flow_snapshots
ADD COLUMN freshness_status TEXT NOT NULL DEFAULT 'UNKNOWN'
CHECK (
    freshness_status IN (
        'PASS',
        'DEGRADED',
        'BLOCKED',
        'UNKNOWN'
    )
);

UPDATE flow_snapshots
SET provider = source_provider
WHERE
    source_provider IS NOT NULL
    AND TRIM(source_provider) != '';

UPDATE flow_snapshots
SET deduped_alert_count = alert_count
WHERE alert_count IS NOT NULL;