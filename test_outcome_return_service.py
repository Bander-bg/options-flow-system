from __future__ import annotations

from weekly.services.outcome_return_service import (
    OutcomeReturnService,
)


def assert_close(
    actual: float,
    expected: float,
    name: str,
    tolerance: float = 1e-12,
) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"{name}: expected {expected}, got {actual}"
        )


def main() -> None:
    service = OutcomeReturnService()

    assert_close(
        service.underlying_raw_return(
            baseline_price=100.0,
            observed_price=105.0,
        ),
        0.05,
        "underlying raw return",
    )

    assert_close(
        service.underlying_directional_return(
            baseline_price=100.0,
            observed_price=95.0,
            signal_sign=-1,
        ),
        0.05,
        "bearish directional return",
    )

    assert_close(
        service.option_executable_return(
            baseline_option_ask=5.0,
            observed_option_bid=5.5,
        ),
        0.10,
        "option executable return",
    )

    assert_close(
        service.option_mark_return(
            baseline_mark=4.75,
            observed_mark=5.75,
        ),
        1.0 / 4.75,
        "option mark return",
    )

    settlement, executable = (
        service.expiry_executable_return(
            baseline_option_ask=4.0,
            option_right="call",
            underlying_price_at_expiry=110.0,
            strike=105.0,
        )
    )

    assert_close(
        settlement,
        5.0,
        "ITM call settlement",
    )
    assert_close(
        executable,
        0.25,
        "ITM call expiry return",
    )

    settlement, executable = (
        service.expiry_executable_return(
            baseline_option_ask=2.0,
            option_right="call",
            underlying_price_at_expiry=95.0,
            strike=100.0,
        )
    )

    assert_close(
        settlement,
        0.0,
        "OTM call settlement",
    )
    assert_close(
        executable,
        -1.0,
        "OTM call expiry return",
    )

    try:
        service.option_executable_return(
            baseline_option_ask=0.0,
            observed_option_bid=1.0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "zero baseline Ask must be rejected"
        )

    print("OUTCOME RETURN SERVICE: PASS 7/7")


if __name__ == "__main__":
    main()
