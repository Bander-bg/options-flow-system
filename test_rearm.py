from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")


@dataclass
class PreviousSignal:
    ticker: str
    direction: str
    target_expiry: date
    trading_date_et: date

    confirmed_at: datetime
    cooldown_until: datetime

    net_flow_at_confirmation: float


def direction_sign(direction: str) -> int:
    normalized = direction.lower()

    if normalized == "bullish":
        return 1

    if normalized == "bearish":
        return -1

    raise ValueError(
        "direction must be bullish or bearish"
    )


def calculate_rearm_aligned_flow(
    *,
    direction: str,
    current_net_flow: float,
    previous_confirmed_net_flow: float,
) -> float:
    """
    weekly_v1:

    rearm_aligned_flow =
        signal_sign *
        (
            current_net_flow
            - previous_confirmed_net_flow
        )
    """

    sign = direction_sign(
        direction
    )

    return sign * (
        current_net_flow
        - previous_confirmed_net_flow
    )


def evaluate_rearm(
    *,
    previous_signal: PreviousSignal,
    current_trading_date_et: date,
    now: datetime,
    current_net_flow: float,
    rearm_aligned_flow_min: float,
    new_trigger_bar_close: datetime | None,
) -> tuple[bool, str]:

    # --------------------------------------------------
    # Rule 1:
    # Never compare Session-to-Date flow
    # across different trading sessions.
    # --------------------------------------------------

    if (
        current_trading_date_et
        != previous_signal.trading_date_et
    ):
        return (
            False,
            "different_trading_date_et",
        )

    # --------------------------------------------------
    # Rule 2:
    # Cooldown must have elapsed.
    # --------------------------------------------------

    if now < previous_signal.cooldown_until:
        return (
            False,
            "cooldown_active",
        )

    # --------------------------------------------------
    # Rule 3:
    # Additional aligned flow must meet threshold.
    # --------------------------------------------------

    aligned_flow = (
        calculate_rearm_aligned_flow(
            direction=previous_signal.direction,
            current_net_flow=current_net_flow,
            previous_confirmed_net_flow=(
                previous_signal
                .net_flow_at_confirmation
            ),
        )
    )

    if (
        aligned_flow
        < rearm_aligned_flow_min
    ):
        return (
            False,
            "insufficient_aligned_flow",
        )

    # --------------------------------------------------
    # Rule 4:
    # A completely new Price Action trigger
    # must close AFTER previous confirmed_at.
    # --------------------------------------------------

    if new_trigger_bar_close is None:
        return (
            False,
            "no_new_price_trigger",
        )

    if (
        new_trigger_bar_close
        <= previous_signal.confirmed_at
    ):
        return (
            False,
            "stale_price_trigger",
        )

    return (
        True,
        "rearm_allowed",
    )


def dt(
    hour: int,
    minute: int = 0,
    *,
    day: int = 4,
) -> datetime:
    return datetime(
        2026,
        9,
        day,
        hour,
        minute,
        tzinfo=ET,
    )


def make_bullish_signal():
    return PreviousSignal(
        ticker="AAPL",
        direction="bullish",
        target_expiry=date(
            2026,
            9,
            11,
        ),
        trading_date_et=date(
            2026,
            9,
            4,
        ),
        confirmed_at=dt(
            10,
            0,
        ),
        cooldown_until=dt(
            11,
            0,
        ),
        net_flow_at_confirmation=600_000,
    )


def make_bearish_signal():
    return PreviousSignal(
        ticker="TSLA",
        direction="bearish",
        target_expiry=date(
            2026,
            9,
            11,
        ),
        trading_date_et=date(
            2026,
            9,
            4,
        ),
        confirmed_at=dt(
            10,
            0,
        ),
        cooldown_until=dt(
            11,
            0,
        ),
        net_flow_at_confirmation=-600_000,
    )


def assert_equal(
    actual,
    expected,
    name: str,
):
    if actual != expected:
        raise AssertionError(
            f"{name}: expected "
            f"{expected!r}, got {actual!r}"
        )


def run_test(
    name: str,
    function,
):
    try:
        function()
        print(f"PASS - {name}")
        return True

    except Exception as exc:
        print(f"FAIL - {name}")
        print(
            f"       "
            f"{type(exc).__name__}: {exc}"
        )
        return False


def test_bullish_rearm_success():
    previous = make_bullish_signal()

    allowed, reason = evaluate_rearm(
        previous_signal=previous,
        current_trading_date_et=date(
            2026,
            9,
            4,
        ),
        now=dt(
            11,
            5,
        ),
        current_net_flow=1_100_000,
        rearm_aligned_flow_min=500_000,
        new_trigger_bar_close=dt(
            11,
            15,
        ),
    )

    assert_equal(
        allowed,
        True,
        "allowed",
    )

    assert_equal(
        reason,
        "rearm_allowed",
        "reason",
    )


def test_bearish_rearm_success():
    previous = make_bearish_signal()

    aligned = (
        calculate_rearm_aligned_flow(
            direction="bearish",
            current_net_flow=-1_100_000,
            previous_confirmed_net_flow=-600_000,
        )
    )

    assert_equal(
        aligned,
        500_000,
        "bearish aligned flow",
    )

    allowed, reason = evaluate_rearm(
        previous_signal=previous,
        current_trading_date_et=date(
            2026,
            9,
            4,
        ),
        now=dt(
            11,
            5,
        ),
        current_net_flow=-1_100_000,
        rearm_aligned_flow_min=500_000,
        new_trigger_bar_close=dt(
            11,
            15,
        ),
    )

    assert_equal(
        allowed,
        True,
        "allowed",
    )


def test_cross_session_comparison_blocked():
    previous = make_bullish_signal()

    allowed, reason = evaluate_rearm(
        previous_signal=previous,
        current_trading_date_et=date(
            2026,
            9,
            8,
        ),
        now=dt(
            10,
            30,
            day=8,
        ),
        current_net_flow=2_000_000,
        rearm_aligned_flow_min=500_000,
        new_trigger_bar_close=dt(
            10,
            15,
            day=8,
        ),
    )

    assert_equal(
        allowed,
        False,
        "allowed",
    )

    assert_equal(
        reason,
        "different_trading_date_et",
        "reason",
    )


def test_cooldown_required():
    previous = make_bullish_signal()

    allowed, reason = evaluate_rearm(
        previous_signal=previous,
        current_trading_date_et=date(
            2026,
            9,
            4,
        ),
        now=dt(
            10,
            45,
        ),
        current_net_flow=1_500_000,
        rearm_aligned_flow_min=500_000,
        new_trigger_bar_close=dt(
            10,
            45,
        ),
    )

    assert_equal(
        allowed,
        False,
        "allowed",
    )

    assert_equal(
        reason,
        "cooldown_active",
        "reason",
    )


def test_additional_flow_required():
    previous = make_bullish_signal()

    allowed, reason = evaluate_rearm(
        previous_signal=previous,
        current_trading_date_et=date(
            2026,
            9,
            4,
        ),
        now=dt(
            11,
            5,
        ),
        current_net_flow=900_000,
        rearm_aligned_flow_min=500_000,
        new_trigger_bar_close=dt(
            11,
            15,
        ),
    )

    assert_equal(
        allowed,
        False,
        "allowed",
    )

    assert_equal(
        reason,
        "insufficient_aligned_flow",
        "reason",
    )


def test_old_trigger_cannot_be_reused():
    previous = make_bullish_signal()

    allowed, reason = evaluate_rearm(
        previous_signal=previous,
        current_trading_date_et=date(
            2026,
            9,
            4,
        ),
        now=dt(
            11,
            5,
        ),
        current_net_flow=1_200_000,
        rearm_aligned_flow_min=500_000,
        new_trigger_bar_close=dt(
            10,
            0,
        ),
    )

    assert_equal(
        allowed,
        False,
        "allowed",
    )

    assert_equal(
        reason,
        "stale_price_trigger",
        "reason",
    )


def test_trigger_after_previous_confirmation():
    previous = make_bullish_signal()

    allowed, reason = evaluate_rearm(
        previous_signal=previous,
        current_trading_date_et=date(
            2026,
            9,
            4,
        ),
        now=dt(
            11,
            5,
        ),
        current_net_flow=1_200_000,
        rearm_aligned_flow_min=500_000,
        new_trigger_bar_close=dt(
            10,
            15,
        ),
    )

    assert_equal(
        allowed,
        True,
        "allowed",
    )


def test_direction_reversal_not_aligned():
    previous = make_bullish_signal()

    aligned = (
        calculate_rearm_aligned_flow(
            direction="bullish",
            current_net_flow=100_000,
            previous_confirmed_net_flow=600_000,
        )
    )

    assert_equal(
        aligned,
        -500_000,
        "aligned flow",
    )

    allowed, reason = evaluate_rearm(
        previous_signal=previous,
        current_trading_date_et=date(
            2026,
            9,
            4,
        ),
        now=dt(
            11,
            5,
        ),
        current_net_flow=100_000,
        rearm_aligned_flow_min=500_000,
        new_trigger_bar_close=dt(
            11,
            15,
        ),
    )

    assert_equal(
        allowed,
        False,
        "allowed",
    )

    assert_equal(
        reason,
        "insufficient_aligned_flow",
        "reason",
    )


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 RE-ARM LOGIC TEST"
    )
    print("=" * 78)
    print()

    tests = [
        (
            "Bullish re-arm succeeds with all 3 conditions",
            test_bullish_rearm_success,
        ),
        (
            "Bearish aligned-flow math is symmetric",
            test_bearish_rearm_success,
        ),
        (
            "Flow is never compared across trading_date_et",
            test_cross_session_comparison_blocked,
        ),
        (
            "Cooldown must expire",
            test_cooldown_required,
        ),
        (
            "Additional aligned flow >= threshold required",
            test_additional_flow_required,
        ),
        (
            "Old Price Action trigger cannot be reused",
            test_old_trigger_cannot_be_reused,
        ),
        (
            "New bar after previous confirmed_at is valid",
            test_trigger_after_previous_confirmation,
        ),
        (
            "Opposite/reversing flow cannot satisfy re-arm",
            test_direction_reversal_not_aligned,
        ),
    ]

    results = []

    for name, function in tests:
        results.append(
            run_test(
                name,
                function,
            )
        )

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)

    passed = sum(results)

    print(
        "tests_passed:",
        passed,
        "/",
        len(results),
    )

    if all(results):
        print()
        print(
            "Same-session Re-arm: PASS"
        )

        print(
            "Cross-session Flow comparison blocked: PASS"
        )

        print(
            "Bullish/Bearish alignment symmetry: PASS"
        )

        print(
            "Fresh Price Action trigger requirement: PASS"
        )

    else:
        print()
        print(
            "Re-arm logic: CHECK REQUIRED"
        )


if __name__ == "__main__":
    main()