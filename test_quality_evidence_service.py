from datetime import date, datetime, timezone

from weekly.domain.enums import Direction, GateStatus
from weekly.domain.models import FlowSnapshot, SignalFeature
from weekly.services.quality_evidence_service import (
    QualityEvidenceService,
)


NOW = datetime(
    2099, 1, 5, 16, 0,
    tzinfo=timezone.utc,
)


def make_flow(
    *,
    net_flow=800_000.0,
    bullish_premium=900_000.0,
    bearish_premium=300_000.0,
    directional_net=600_000.0,
    total_premium=2_000_000.0,
    sweep_premium=1_200_000.0,
    opening_alert_count=0,
):
    return FlowSnapshot(
        ticker="AAPL",
        trading_date_et=date(2099, 1, 5),
        captured_at=NOW,
        target_expiry=date(2099, 1, 9),

        call_ask_premium=900_000.0,
        put_ask_premium=100_000.0,
        net_flow=net_flow,

        call_bid_premium=200_000.0,
        put_bid_premium=300_000.0,

        bullish_premium=bullish_premium,
        bearish_premium=bearish_premium,
        directional_net=directional_net,

        raw_alert_count=10,
        clean_alert_count=10,
        deduped_alert_count=10,

        flow_dedup_level="alert_uuid",
        trade_overlap_detected=False,

        sweep_alert_count=3,
        opening_alert_count=opening_alert_count,

        provider="UNUSUAL_WHALES",
        feed="UNKNOWN",

        source_timestamp=NOW,
        fetched_at=NOW,
        freshness_status="PASS",

        total_premium=total_premium,
        sweep_premium=sweep_premium,
    )


def make_feature(
    *,
    underlying_price=204.0,
    weekly_vwap=200.0,
    atr_1h=8.0,
    vwap_status=GateStatus.PASS,
):
    return SignalFeature(
        signal_id=1,
        evaluation_sequence=1,
        captured_at=NOW,

        underlying_price=underlying_price,
        weekly_vwap=weekly_vwap,
        atr_1h=atr_1h,
        vwap_status=vwap_status,
    )


def main():
    service = QualityEvidenceService()

    result = service.evaluate(
        direction=Direction.BULLISH,
        flow_snapshot=make_flow(),
        feature=make_feature(),
    )

    assert result.absolute_flow_strength == 800_000.0
    assert (
        result.absolute_flow_strength_status
        is GateStatus.PASS
    )
    print("1. absolute flow strength: PASS")

    assert result.vwap_distance_atr == 0.5
    assert (
        result.vwap_distance_atr_status
        is GateStatus.PASS
    )
    print("2. VWAP distance / ATR: PASS")

    assert result.sweep_ratio == 0.6
    assert result.sweep_ratio_status is GateStatus.PASS
    print("3. sweep premium ratio: PASS")

    assert result.directional_flow_confirmation == 0.5
    assert (
        result.directional_flow_confirmation_status
        is GateStatus.PASS
    )
    print("4. bullish directional strength: PASS")

    bearish = service.evaluate(
        direction=Direction.BEARISH,
        flow_snapshot=make_flow(
            net_flow=-800_000.0,
            bullish_premium=300_000.0,
            bearish_premium=900_000.0,
            directional_net=-600_000.0,
        ),
        feature=make_feature(),
    )

    assert bearish.absolute_flow_strength == 800_000.0
    assert bearish.directional_flow_confirmation == 0.5
    assert (
        bearish.directional_flow_confirmation_status
        is GateStatus.PASS
    )
    print("5. bearish sign normalization: PASS")

    conflict = service.evaluate(
        direction=Direction.BULLISH,
        flow_snapshot=make_flow(
            directional_net=-300_000.0,
        ),
        feature=make_feature(),
    )

    assert conflict.directional_flow_confirmation == -0.25
    assert (
        conflict.directional_flow_confirmation_status
        is GateStatus.FAIL
    )
    print("6. directional conflict evidence: PASS")

    missing_sweep = service.evaluate(
        direction=Direction.BULLISH,
        flow_snapshot=make_flow(
            total_premium=None,
            sweep_premium=None,
        ),
        feature=make_feature(),
    )

    assert missing_sweep.sweep_ratio is None
    assert (
        missing_sweep.sweep_ratio_status
        is GateStatus.UNKNOWN
    )
    print("7. missing sweep evidence -> UNKNOWN: PASS")

    missing_vwap = service.evaluate(
        direction=Direction.BULLISH,
        flow_snapshot=make_flow(),
        feature=make_feature(
            atr_1h=None,
        ),
    )

    assert missing_vwap.vwap_distance_atr is None
    assert (
        missing_vwap.vwap_distance_atr_status
        is GateStatus.UNKNOWN
    )
    print("8. missing VWAP/ATR evidence -> UNKNOWN: PASS")

    zero_directional = service.evaluate(
        direction=Direction.BULLISH,
        flow_snapshot=make_flow(
            bullish_premium=0.0,
            bearish_premium=0.0,
            directional_net=0.0,
        ),
        feature=make_feature(),
    )

    assert (
        zero_directional.directional_flow_confirmation
        is None
    )
    assert (
        zero_directional.directional_flow_confirmation_status
        is GateStatus.UNKNOWN
    )
    print("9. zero directional denominator -> UNKNOWN: PASS")

    assert result.opening_evidence is None
    assert (
        result.opening_evidence_status
        is GateStatus.UNKNOWN
    )
    print("10. incomplete opening evidence -> UNKNOWN: PASS")

    all_opening = service.evaluate(
        direction=Direction.BULLISH,
        flow_snapshot=make_flow(
            opening_alert_count=10,
        ),
        feature=make_feature(),
    )

    assert all_opening.opening_evidence == 10.0
    assert (
        all_opening.opening_evidence_status
        is GateStatus.PASS
    )
    print("11. all opening trades evidence: PASS")

    negative_gamma = service.evaluate(
        direction=Direction.BULLISH,
        flow_snapshot=make_flow(),
        feature=make_feature(),
        total_gex=-25_000.0,
    )

    assert negative_gamma.negative_gamma_regime is True
    assert (
        negative_gamma.negative_gamma_regime_status
        is GateStatus.PASS
    )
    print("12. negative GEX regime: PASS")

    non_negative_gamma = service.evaluate(
        direction=Direction.BULLISH,
        flow_snapshot=make_flow(),
        feature=make_feature(),
        total_gex=25_000.0,
    )

    assert non_negative_gamma.negative_gamma_regime is False
    assert (
        non_negative_gamma.negative_gamma_regime_status
        is GateStatus.PASS
    )
    print("13. non-negative GEX regime: PASS")

    missing_gamma = service.evaluate(
        direction=Direction.BULLISH,
        flow_snapshot=make_flow(),
        feature=make_feature(),
        total_gex=None,
    )

    assert missing_gamma.negative_gamma_regime is None
    assert (
        missing_gamma.negative_gamma_regime_status
        is GateStatus.UNKNOWN
    )
    print("14. missing GEX -> UNKNOWN: PASS")

    print()
    print("=" * 70)
    print("QUALITY EVIDENCE SERVICE: PASS 14/14")
    print("=" * 70)


if __name__ == "__main__":
    main()
