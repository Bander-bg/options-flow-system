from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from weekly.domain.enums import Direction, GateStatus, OptionRight
from weekly.services.eligible_contract_service import (
    ContractSelectorSettings,
    EligibleContractService,
    OptionContractCandidate,
)


EXPIRY = date(2026, 9, 18)
AS_OF = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)


def settings() -> ContractSelectorSettings:
    return ContractSelectorSettings(
        delta_min=0.35,
        delta_max=0.65,
        max_spread_pct=0.12,
        max_quote_age_seconds=60,
        standard_contract_size=100,
        require_standard_contract=True,
        require_tradable_contract=True,
        max_budget=5000.0,
        target_abs_delta=0.50,
    )


def candidate(
    symbol: str,
    *,
    right: OptionRight = OptionRight.CALL,
    expiry: date = EXPIRY,
    strike: float = 200.0,
    delta: float | None = 0.50,
    bid: float | None = 9.50,
    ask: float | None = 10.00,
    quote_age_seconds: int = 20,
    active: bool = True,
    tradable: bool = True,
    size: int | None = 100,
    root_symbol: str = "AAPL",
    underlying_symbol: str = "AAPL",
) -> OptionContractCandidate:
    return OptionContractCandidate(
        symbol=symbol,
        underlying_symbol=underlying_symbol,
        root_symbol=root_symbol,
        expiry=expiry,
        right=right,
        strike=strike,
        active=active,
        tradable=tradable,
        size=size,
        bid=bid,
        ask=ask,
        quote_at=AS_OF - timedelta(seconds=quote_age_seconds),
        delta=delta,
        gamma=0.05,
        theta=-0.12,
        vega=0.20,
        iv=0.40,
    )


def main() -> None:
    svc = EligibleContractService(settings=settings())

    loaded = ContractSelectorSettings.from_config()
    assert loaded.delta_min == 0.35
    assert loaded.delta_max == 0.65
    assert loaded.max_spread_pct == 0.12
    assert loaded.max_quote_age_seconds == 60
    assert loaded.standard_contract_size == 100
    assert loaded.max_budget == 5000.0
    assert loaded.target_abs_delta == 0.50
    print("1. weekly config contract-selector settings: PASS")

    result = svc.evaluate(
        direction=Direction.BULLISH,
        target_expiry=EXPIRY,
        underlying_price=200.0,
        expected_move=10.0,
        as_of=AS_OF,
        contracts=(
            candidate(
                "AAPL260918C00200000",
                delta=0.50,
                bid=9.50,
                ask=10.00,
            ),
            candidate(
                "AAPL260918C00201000",
                strike=201.0,
                delta=0.48,
                bid=9.70,
                ask=9.90,
            ),
        ),
    )
    assert result.status is GateStatus.PASS
    assert result.expected_right is OptionRight.CALL
    assert result.selected is not None
    assert result.selected.symbol == "AAPL260918C00200000"
    assert result.eligible_count == 2
    print("2. bullish -> CALL + closest |Delta| 0.50 ranking: PASS")

    bearish = svc.evaluate(
        direction=Direction.BEARISH,
        target_expiry=EXPIRY,
        underlying_price=200.0,
        expected_move=10.0,
        as_of=AS_OF,
        contracts=(
            candidate(
                "AAPL260918P00200000",
                right=OptionRight.PUT,
                delta=-0.51,
            ),
            candidate(
                "AAPL260918C00200000",
                right=OptionRight.CALL,
                delta=0.50,
            ),
        ),
    )
    assert bearish.status is GateStatus.PASS
    assert bearish.expected_right is OptionRight.PUT
    assert bearish.selected is not None
    assert bearish.selected.right is OptionRight.PUT
    print("3. bearish -> PUT and wrong right rejected: PASS")

    metadata = svc.evaluate(
        direction=Direction.BULLISH,
        target_expiry=EXPIRY,
        underlying_price=200.0,
        expected_move=10.0,
        as_of=AS_OF,
        contracts=(
            candidate(
                "BAD_EXPIRY",
                expiry=date(2026, 9, 25),
            ),
            candidate(
                "INACTIVE",
                active=False,
            ),
            candidate(
                "NOT_TRADABLE",
                tradable=False,
            ),
            candidate(
                "NONSTANDARD_SIZE",
                size=10,
            ),
            candidate(
                "NONSTANDARD_ROOT",
                root_symbol="AAPL1",
            ),
            candidate(
                "ROOT_MISMATCH",
                root_symbol="AAPLX",
            ),
        ),
    )
    assert metadata.status is GateStatus.FAIL
    assert metadata.eligible_count == 0
    print("4. expiry/active/tradable/standard metadata filters: PASS")

    delta_bounds = svc.evaluate(
        direction=Direction.BULLISH,
        target_expiry=EXPIRY,
        underlying_price=200.0,
        expected_move=10.0,
        as_of=AS_OF,
        contracts=(
            candidate("DELTA_MIN", delta=0.35),
            candidate("DELTA_MAX", delta=0.65),
            candidate("DELTA_LOW", delta=0.34),
            candidate("DELTA_HIGH", delta=0.66),
        ),
    )
    assert delta_bounds.status is GateStatus.PASS
    assert delta_bounds.eligible_count == 2
    print("5. inclusive Delta 0.35-0.65 filter: PASS")

    market_quality = svc.evaluate(
        direction=Direction.BULLISH,
        target_expiry=EXPIRY,
        underlying_price=200.0,
        expected_move=10.0,
        as_of=AS_OF,
        contracts=(
            candidate(
                "WIDE_SPREAD",
                bid=8.0,
                ask=10.0,
            ),
            candidate(
                "STALE_QUOTE",
                quote_age_seconds=61,
            ),
            candidate(
                "OVER_BUDGET",
                bid=50.0,
                ask=51.0,
            ),
            candidate(
                "GOOD",
                bid=9.50,
                ask=10.00,
            ),
        ),
    )
    assert market_quality.status is GateStatus.PASS
    assert market_quality.eligible_count == 1
    assert market_quality.selected is not None
    assert market_quality.selected.symbol == "GOOD"
    assert market_quality.selected.quote_age_seconds == 20.0
    print("6. spread/freshness/budget filters: PASS")

    strike_range = svc.evaluate(
        direction=Direction.BULLISH,
        target_expiry=EXPIRY,
        underlying_price=200.0,
        expected_move=10.0,
        as_of=AS_OF,
        contracts=(
            candidate("LOW_BOUND", strike=190.0, delta=0.50),
            candidate("HIGH_BOUND", strike=210.0, delta=0.51),
            candidate("OUTSIDE_LOW", strike=189.0, delta=0.49),
            candidate("OUTSIDE_HIGH", strike=211.0, delta=0.48),
        ),
    )
    assert strike_range.status is GateStatus.PASS
    assert strike_range.eligible_count == 2
    assert strike_range.range_low == 190.0
    assert strike_range.range_high == 210.0
    print("7. exact expected-move strike range filter: PASS")

    unavailable_move = svc.evaluate(
        direction=Direction.BULLISH,
        target_expiry=EXPIRY,
        underlying_price=200.0,
        expected_move=None,
        as_of=AS_OF,
        contracts=(candidate("GOOD"),),
    )
    assert unavailable_move.status is GateStatus.UNKNOWN
    assert unavailable_move.reason == "EXPECTED_MOVE_OR_UNDERLYING_UNAVAILABLE"
    print("8. missing expected move/underlying -> UNKNOWN: PASS")

    unavailable_contracts = svc.evaluate(
        direction=Direction.BULLISH,
        target_expiry=EXPIRY,
        underlying_price=200.0,
        expected_move=10.0,
        as_of=AS_OF,
        contracts=None,
    )
    assert unavailable_contracts.status is GateStatus.UNKNOWN
    assert unavailable_contracts.reason == "CONTRACT_DATA_UNAVAILABLE"
    print("9. unavailable contract data -> UNKNOWN: PASS")

    no_eligible = svc.evaluate(
        direction=Direction.BULLISH,
        target_expiry=EXPIRY,
        underlying_price=200.0,
        expected_move=10.0,
        as_of=AS_OF,
        contracts=(
            candidate(
                "BAD_DELTA",
                delta=0.20,
            ),
        ),
    )
    assert no_eligible.status is GateStatus.FAIL
    assert no_eligible.reason == "NO_ELIGIBLE_CONTRACT"
    print("10. available chain with no eligible contract -> FAIL: PASS")

    print()
    print("=" * 70)
    print("ELIGIBLE CONTRACT SERVICE: PASS 10/10")
    print("=" * 70)


if __name__ == "__main__":
    main()
