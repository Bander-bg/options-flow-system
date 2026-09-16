from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import load_weekly_config

from weekly.domain.enums import (
    Direction,
    GateStatus,
)

from weekly.services.price_action_service import (
    PriceActionError,
    PriceActionService,
    PriceBar,
)


ET = ZoneInfo("America/New_York")


def bar(
    start_at: datetime,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> PriceBar:
    return PriceBar(
        start_at=start_at,
        end_at=start_at + timedelta(minutes=15),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def build_bullish_prior_bars(
    trigger_start: datetime,
) -> list[PriceBar]:
    bars: list[PriceBar] = []

    first_start = (
        trigger_start
        - timedelta(minutes=150)
    )

    for i in range(9):
        start = (
            first_start
            + timedelta(minutes=15 * i)
        )

        bars.append(
            bar(
                start,
                open_=100.00,
                high=100.40,
                low=99.80,
                close=100.20,
                volume=100.0,
            )
        )

    # Last prior candle is bearish.
    # This allows the bullish trigger to also
    # qualify as directional engulfing.
    bars.append(
        bar(
            trigger_start
            - timedelta(minutes=15),
            open_=100.30,
            high=100.40,
            low=99.90,
            close=100.10,
            volume=100.0,
        )
    )

    return bars


def build_bearish_prior_bars(
    trigger_start: datetime,
) -> list[PriceBar]:
    bars: list[PriceBar] = []

    first_start = (
        trigger_start
        - timedelta(minutes=150)
    )

    for i in range(9):
        start = (
            first_start
            + timedelta(minutes=15 * i)
        )

        bars.append(
            bar(
                start,
                open_=100.20,
                high=100.40,
                low=99.60,
                close=100.00,
                volume=100.0,
            )
        )

    # Last prior candle is bullish.
    bars.append(
        bar(
            trigger_start
            - timedelta(minutes=15),
            open_=99.80,
            high=100.20,
            low=99.60,
            close=100.10,
            volume=100.0,
        )
    )

    return bars


def expect_error(
    fn,
    expected_text: str,
) -> None:
    try:
        fn()

    except PriceActionError as exc:
        assert expected_text in str(exc)
        return

    raise AssertionError(
        "Expected PriceActionError "
        f"containing: {expected_text!r}"
    )


def main() -> None:
    config = load_weekly_config()

    service = (
        PriceActionService.from_weekly_config(
            config
        )
    )

    # ==================================================
    # 1. CONFIG CONTRACT
    # ==================================================

    settings = service.settings

    assert settings.confirmation_minutes == 30

    assert (
        settings.structure_lookback_bars
        == 8
    )

    assert (
        settings.structure_atr_break
        == 0.10
    )

    assert (
        settings.impulse_body_lookback_bars
        == 10
    )

    assert (
        settings
        .impulse_body_expansion_multiplier
        == 1.5
    )

    assert (
        settings.impulse_body_min_atr
        == 0.50
    )

    assert (
        settings.participation_rvol_min
        == 1.5
    )

    assert (
        settings
        .participation_rvol_lookback_sessions
        == 20
    )

    print(
        "1. weekly_config contract: PASS"
    )

    # Common evaluation window.
    trigger_start = datetime(
        2026,
        9,
        11,
        12,
        0,
        tzinfo=ET,
    )

    candidate_at = trigger_start

    deadline = (
        candidate_at
        + timedelta(minutes=30)
    )

    historical_volumes = [
        100.0
        for _ in range(20)
    ]

    # ==================================================
    # 2. BULLISH — 3/3 PASS
    # ==================================================

    bullish_prior = (
        build_bullish_prior_bars(
            trigger_start
        )
    )

    bullish_trigger = bar(
        trigger_start,
        open_=100.00,
        high=101.10,
        low=99.90,
        close=101.00,
        volume=200.0,
    )

    bullish = service.evaluate_bar(
        direction=Direction.BULLISH,
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        trigger_bar=bullish_trigger,
        prior_bars=bullish_prior,
        atr_15m=1.0,
        historical_same_slot_volumes=(
            historical_volumes
        ),
    )

    assert (
        bullish.structure_status
        == GateStatus.PASS
    )

    assert (
        bullish.impulse_status
        == GateStatus.PASS
    )

    assert (
        bullish.participation_status
        == GateStatus.PASS
    )

    assert (
        bullish.price_action_pass_count
        == 3
    )

    assert (
        bullish.price_action_status
        == GateStatus.PASS
    )

    assert (
        bullish.impulse_engulfing_match
        is True
    )

    assert (
        bullish.impulse_expansion_match
        is True
    )

    assert (
        bullish.structure_reference_level
        == 100.40
    )

    assert (
        round(
            bullish.structure_break_level,
            6,
        )
        == 100.50
    )

    assert (
        bullish.participation_reference_sessions
        == 20
    )

    assert (
        bullish.participation_median_slot_volume
        == 100.0
    )

    assert (
        bullish.participation_rvol
        == 2.0
    )

    print(
        "2. bullish 3/3 confirmation: PASS"
    )

    # ==================================================
    # 3. BEARISH — 3/3 PASS
    # ==================================================

    bearish_prior = (
        build_bearish_prior_bars(
            trigger_start
        )
    )

    bearish_trigger = bar(
        trigger_start,
        open_=100.20,
        high=100.30,
        low=98.90,
        close=99.00,
        volume=200.0,
    )

    bearish = service.evaluate_bar(
        direction=Direction.BEARISH,
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        trigger_bar=bearish_trigger,
        prior_bars=bearish_prior,
        atr_15m=1.0,
        historical_same_slot_volumes=(
            historical_volumes
        ),
    )

    assert (
        bearish.structure_status
        == GateStatus.PASS
    )

    assert (
        bearish.impulse_status
        == GateStatus.PASS
    )

    assert (
        bearish.participation_status
        == GateStatus.PASS
    )

    assert (
        bearish.price_action_pass_count
        == 3
    )

    assert (
        bearish.price_action_status
        == GateStatus.PASS
    )

    assert (
        bearish.impulse_engulfing_match
        is True
    )

    assert (
        bearish.impulse_expansion_match
        is True
    )

    print(
        "3. bearish 3/3 confirmation: PASS"
    )

    # ==================================================
    # 4. EXACT 2/3 PASS
    #
    # Structure: PASS
    # Impulse: FAIL
    # Participation: PASS
    # Overall: PASS
    # ==================================================

    two_of_three_trigger = bar(
        trigger_start,
        open_=100.55,
        high=100.70,
        low=100.50,
        close=100.60,
        volume=200.0,
    )

    two_of_three = service.evaluate_bar(
        direction=Direction.BULLISH,
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        trigger_bar=two_of_three_trigger,
        prior_bars=bullish_prior,
        atr_15m=1.0,
        historical_same_slot_volumes=(
            historical_volumes
        ),
    )

    assert (
        two_of_three.structure_status
        == GateStatus.PASS
    )

    assert (
        two_of_three.impulse_status
        == GateStatus.FAIL
    )

    assert (
        two_of_three.participation_status
        == GateStatus.PASS
    )

    assert (
        two_of_three.price_action_pass_count
        == 2
    )

    assert (
        two_of_three.price_action_status
        == GateStatus.PASS
    )

    print(
        "4. 2-of-3 PASS rule: PASS"
    )

    # ==================================================
    # 5. TWO FAILS → BAR FAIL
    #
    # Structure: FAIL
    # Impulse: FAIL
    # Participation: PASS
    # Overall: FAIL
    # ==================================================

    fail_trigger = bar(
        trigger_start,
        open_=100.00,
        high=100.20,
        low=99.90,
        close=100.05,
        volume=200.0,
    )

    failed = service.evaluate_bar(
        direction=Direction.BULLISH,
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        trigger_bar=fail_trigger,
        prior_bars=bullish_prior,
        atr_15m=1.0,
        historical_same_slot_volumes=(
            historical_volumes
        ),
    )

    assert (
        failed.structure_status
        == GateStatus.FAIL
    )

    assert (
        failed.impulse_status
        == GateStatus.FAIL
    )

    assert (
        failed.participation_status
        == GateStatus.PASS
    )

    assert (
        failed.price_action_pass_count
        == 1
    )

    assert (
        failed.price_action_status
        == GateStatus.FAIL
    )

    print(
        "5. 2-of-3 FAIL rule: PASS"
    )

    # ==================================================
    # 6. INSUFFICIENT DATA → UNKNOWN
    # ==================================================

    unknown_trigger = bar(
        trigger_start,
        open_=100.00,
        high=100.20,
        low=99.90,
        close=100.10,
        volume=100.0,
    )

    unknown = service.evaluate_bar(
        direction=Direction.BULLISH,
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        trigger_bar=unknown_trigger,
        prior_bars=[],
        atr_15m=None,
        historical_same_slot_volumes=[
            100.0
            for _ in range(5)
        ],
    )

    assert (
        unknown.structure_status
        == GateStatus.UNKNOWN
    )

    assert (
        unknown.impulse_status
        == GateStatus.UNKNOWN
    )

    assert (
        unknown.participation_status
        == GateStatus.UNKNOWN
    )

    assert (
        unknown.price_action_pass_count
        == 0
    )

    assert (
        unknown.price_action_status
        == GateStatus.UNKNOWN
    )

    assert (
        unknown.participation_reference_sessions
        == 5
    )

    print(
        "6. insufficient-data UNKNOWN: PASS"
    )

    # ==================================================
    # 7. FRESH BAR RULE
    #
    # Trigger begins before candidate.
    # It must NOT be accepted.
    # ==================================================

    late_candidate = (
        trigger_start
        + timedelta(minutes=1)
    )

    expect_error(
        lambda: service.evaluate_bar(
            direction=Direction.BULLISH,
            candidate_at=late_candidate,
            confirmation_deadline_at=(
                late_candidate
                + timedelta(minutes=30)
            ),
            trigger_bar=bullish_trigger,
            prior_bars=bullish_prior,
            atr_15m=1.0,
            historical_same_slot_volumes=(
                historical_volumes
            ),
        ),
        "Trigger bar must start at or after",
    )

    print(
        "7. fresh post-candidate bar rule: PASS"
    )

    # ==================================================
    # 8. CONFIRMATION DEADLINE RULE
    #
    # Trigger closes after the deadline.
    # ==================================================

    short_deadline = (
        candidate_at
        + timedelta(minutes=10)
    )

    expect_error(
        lambda: service.evaluate_bar(
            direction=Direction.BULLISH,
            candidate_at=candidate_at,
            confirmation_deadline_at=(
                short_deadline
            ),
            trigger_bar=bullish_trigger,
            prior_bars=bullish_prior,
            atr_15m=1.0,
            historical_same_slot_volumes=(
                historical_volumes
            ),
        ),
        "Trigger bar ends after",
    )

    print(
        "8. confirmation deadline rule: PASS"
    )

    # ==================================================
    # 9. BAR MUST BE EXACTLY 15 MINUTES
    # ==================================================

    expect_error(
        lambda: PriceBar(
            start_at=trigger_start,
            end_at=(
                trigger_start
                + timedelta(minutes=14)
            ),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=100.0,
        ),
        "exactly 15 minutes",
    )

    print(
        "9. completed 15m bar contract: PASS"
    )

    print()
    print("=" * 70)
    print(
        "PRICE ACTION SERVICE: PASS 9/9"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()