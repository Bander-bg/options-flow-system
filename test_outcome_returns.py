from __future__ import annotations


def underlying_raw_return(
    baseline_price: float,
    observed_price: float,
) -> float:
    if baseline_price <= 0:
        raise ValueError(
            "baseline_price must be > 0"
        )

    return (
        observed_price - baseline_price
    ) / baseline_price


def underlying_directional_return(
    baseline_price: float,
    observed_price: float,
    signal_sign: int,
) -> float:
    if signal_sign not in (-1, 1):
        raise ValueError(
            "signal_sign must be +1 or -1"
        )

    raw = underlying_raw_return(
        baseline_price,
        observed_price,
    )

    return signal_sign * raw


def option_executable_return(
    baseline_option_ask: float,
    observed_option_bid: float,
) -> float:
    """
    weekly_v1 executable research return:

    Entry = Ask
    Exit observation = Bid
    """

    if baseline_option_ask <= 0:
        raise ValueError(
            "baseline_option_ask must be > 0"
        )

    if observed_option_bid < 0:
        raise ValueError(
            "observed_option_bid must be >= 0"
        )

    return (
        observed_option_bid
        - baseline_option_ask
    ) / baseline_option_ask


def option_mark_return(
    baseline_mark: float,
    observed_mark: float,
) -> float:
    if baseline_mark <= 0:
        raise ValueError(
            "baseline_mark must be > 0"
        )

    return (
        observed_mark - baseline_mark
    ) / baseline_mark


def intrinsic_value(
    *,
    option_right: str,
    underlying_price: float,
    strike: float,
) -> float:
    right = option_right.lower()

    if right == "call":
        return max(
            0.0,
            underlying_price - strike,
        )

    if right == "put":
        return max(
            0.0,
            strike - underlying_price,
        )

    raise ValueError(
        "option_right must be call or put"
    )


def expiry_executable_return(
    *,
    baseline_option_ask: float,
    option_right: str,
    underlying_price_at_expiry: float,
    strike: float,
) -> float:
    settlement_value = intrinsic_value(
        option_right=option_right,
        underlying_price=underlying_price_at_expiry,
        strike=strike,
    )

    return option_executable_return(
        baseline_option_ask,
        settlement_value,
    )


def assert_close(
    actual: float,
    expected: float,
    name: str,
    tolerance: float = 1e-12,
):
    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"{name}: expected {expected}, got {actual}"
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
            f"       {type(exc).__name__}: {exc}"
        )
        return False


def test_call_ask_to_bid_return():
    result = option_executable_return(
        baseline_option_ask=5.00,
        observed_option_bid=6.00,
    )

    assert_close(
        result,
        0.20,
        "call executable return",
    )


def test_spread_cost_is_not_hidden():
    result = option_executable_return(
        baseline_option_ask=5.00,
        observed_option_bid=4.50,
    )

    assert_close(
        result,
        -0.10,
        "spread-aware return",
    )


def test_mark_return_is_separate():
    executable = option_executable_return(
        baseline_option_ask=5.00,
        observed_option_bid=5.50,
    )

    mark = option_mark_return(
        baseline_mark=4.75,
        observed_mark=5.75,
    )

    assert_close(
        executable,
        0.10,
        "executable",
    )

    assert_close(
        mark,
        1.00 / 4.75,
        "mark",
    )

    if executable == mark:
        raise AssertionError(
            "Executable and mark return "
            "must remain separate."
        )


def test_bullish_underlying_return():
    result = underlying_directional_return(
        baseline_price=100.0,
        observed_price=105.0,
        signal_sign=1,
    )

    assert_close(
        result,
        0.05,
        "bullish directional return",
    )


def test_put_directional_return_on_drop():
    result = underlying_directional_return(
        baseline_price=100.0,
        observed_price=95.0,
        signal_sign=-1,
    )

    assert_close(
        result,
        0.05,
        "put directional return",
    )


def test_put_raw_return_stays_negative():
    raw = underlying_raw_return(
        baseline_price=100.0,
        observed_price=95.0,
    )

    assert_close(
        raw,
        -0.05,
        "raw underlying return",
    )


def test_call_expiry_intrinsic():
    result = expiry_executable_return(
        baseline_option_ask=4.00,
        option_right="call",
        underlying_price_at_expiry=110.0,
        strike=105.0,
    )

    # Intrinsic = 5
    # Return = (5 - 4) / 4 = 25%
    assert_close(
        result,
        0.25,
        "call expiry return",
    )


def test_put_expiry_intrinsic():
    result = expiry_executable_return(
        baseline_option_ask=3.00,
        option_right="put",
        underlying_price_at_expiry=90.0,
        strike=95.0,
    )

    # Intrinsic = 5
    # Return = (5 - 3) / 3 = 66.6667%
    assert_close(
        result,
        2.0 / 3.0,
        "put expiry return",
    )


def test_otm_expiry_zero_value():
    result = expiry_executable_return(
        baseline_option_ask=2.00,
        option_right="call",
        underlying_price_at_expiry=95.0,
        strike=100.0,
    )

    # Intrinsic = 0
    # Full premium loss = -100%
    assert_close(
        result,
        -1.0,
        "OTM expiry return",
    )


def test_invalid_baseline_ask_rejected():
    try:
        option_executable_return(
            baseline_option_ask=0.0,
            observed_option_bid=2.0,
        )

    except ValueError:
        return

    raise AssertionError(
        "Zero baseline ask must be rejected."
    )


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 OUTCOME RETURN MATH TEST"
    )
    print("=" * 78)
    print()

    tests = [
        (
            "Ask entry / Bid exit return",
            test_call_ask_to_bid_return,
        ),
        (
            "Spread cost is not hidden",
            test_spread_cost_is_not_hidden,
        ),
        (
            "Executable return separate from Mark return",
            test_mark_return_is_separate,
        ),
        (
            "Bullish underlying directional return",
            test_bullish_underlying_return,
        ),
        (
            "Put directional return becomes positive on drop",
            test_put_directional_return_on_drop,
        ),
        (
            "Raw underlying return remains negative on drop",
            test_put_raw_return_stays_negative,
        ),
        (
            "Call expiry uses intrinsic value",
            test_call_expiry_intrinsic,
        ),
        (
            "Put expiry uses intrinsic value",
            test_put_expiry_intrinsic,
        ),
        (
            "OTM expiry produces -100% executable return",
            test_otm_expiry_zero_value,
        ),
        (
            "Invalid zero Ask baseline is rejected",
            test_invalid_baseline_ask_rejected,
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
            "Executable option return Ask -> Bid: PASS"
        )
        print(
            "Theoretical Mark return separation: PASS"
        )
        print(
            "Put directional underlying return: PASS"
        )
        print(
            "Expiry intrinsic settlement logic: PASS"
        )

    else:
        print()
        print(
            "Outcome return math: CHECK REQUIRED"
        )


if __name__ == "__main__":
    main()