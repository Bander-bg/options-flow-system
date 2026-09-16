from __future__ import annotations

from weekly.domain.models import FlowSnapshot
from weekly.providers.unusual_whales_provider import FlowAlertsBatch
from weekly.services.flow_service import FlowCalculation


class FlowSnapshotMappingError(ValueError):
    """Raised when a runtime FlowSnapshot cannot be mapped safely."""


def map_flow_snapshot(
    *,
    calculation: FlowCalculation,
    batch: FlowAlertsBatch,
) -> FlowSnapshot:
    """
    Map one completed UW fetch + FlowCalculation into the
    immutable runtime FlowSnapshot.

    captured_at represents when this snapshot was fetched.
    source_timestamp preserves the newest underlying UW
    alert timestamp and may legitimately be None when the
    session contains zero alerts.
    """

    if batch.fetched_at is None:
        raise FlowSnapshotMappingError(
            "batch.fetched_at is required for runtime snapshot capture."
        )

    if calculation.ticker != batch.ticker:
        raise FlowSnapshotMappingError(
            "Flow calculation ticker does not match provider batch ticker."
        )

    return FlowSnapshot(
        ticker=calculation.ticker,
        trading_date_et=calculation.trading_date_et,
        captured_at=batch.fetched_at,
        target_expiry=calculation.target_expiry,

        call_ask_premium=calculation.call_ask_premium,
        put_ask_premium=calculation.put_ask_premium,
        net_flow=calculation.net_flow,

        call_bid_premium=calculation.call_bid_premium,
        put_bid_premium=calculation.put_bid_premium,

        bullish_premium=calculation.bullish_premium,
        bearish_premium=calculation.bearish_premium,
        directional_net=calculation.directional_net,

        raw_alert_count=calculation.raw_alert_count,
        clean_alert_count=calculation.clean_alert_count,
        deduped_alert_count=calculation.deduped_alert_count,

        flow_dedup_level=calculation.flow_dedup_level,
        trade_overlap_detected=calculation.trade_overlap_detected,

        sweep_alert_count=calculation.sweep_alert_count,
        opening_alert_count=calculation.opening_alert_count,

        provider=batch.provider,
        feed=batch.feed,

        source_timestamp=batch.source_timestamp,
        fetched_at=batch.fetched_at,
        freshness_status=batch.freshness_status,

        total_premium=calculation.total_premium,
        sweep_premium=calculation.sweep_premium,
    )
