from __future__ import annotations

import math
from datetime import date

from weekly.domain.enums import GateStatus
from weekly.services.expected_move_service import (
    ExpectedMoveError,
    ExpectedMoveService,
)


TRADING_DATE = date(2026, 9, 14)
TA = TARGET_EXPIRY = date(2026, 9, 18)
PRICE = 200.0


def main() -> None:
    svc = ExpectedMoveService()

    primary = svc.evaluate(
        trading_date=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        underlying_price=PRICE,
        term_structure_rows=(
            {
                "expiry": "2026-09-25",
                "implied_move": 12.0,
                "volatility": 0.50,
                "implied_move_perc": 6.0,
            },
            {
                "expiry": "2026-09-18",
                "implied_move": 8.0,
                "volatility": 0.40,
                "implied_move_perc": 4.0,
            },
        ),
        atm_iv=0.99,
    )
    assert primary.status is GateStatus.PASS
    assert primary.source == "UW_TERM_STRUCTURE"
    assert primary.expected_move == 8.0
    assert math.isclose(primary.expected_move_perc, 0.04)
    assert primary.atm_iv is None
    print("1. exact-expiry UW primary source: PASS")

    exact_only = svc.evaluate(
        trading_date=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        underlying_price=PRICE,
        term_structure_rows=(
            {
                "expiry": "2026-09-17",
                "implied_move": 99.0,
                "volatility": 0.99,
                "implied_move_perc": 99.0,
            },
            {
                "expiry": "2026-09-18",
                "implied_move": 7.5,
                "volatility": 0.35,
                "implied_move_perc": 3.75,
            },
        ),
        atm_iv=None,
    )
    assert exact_only.status is GateStatus.PASS
    assert exact_only.expected_move == 7.5
    print("2. neighboring expiry rows are not substituted: PASS")

    canonical_pct = svc.evaluate(
        trading_date=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        underlying_price=320.0,
        term_structure_rows=(
            {
                "expiry": "2026-09-18",
                "implied_move": 8.0,
                "volatility": 0.30,
                "implied_move_perc": 2.5,
            },
        ),
        atm_iv=None,
    )
    assert canonical_pct.status is GateStatus.PASS
    assert math.isclose(canonical_pct.expected_move_perc, 0.025)
    print("3. canonical expected_move_perc uses decimal fraction: PASS")

    invalid_exact_fallback = svc.evaluate(
        trading_date=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        underlying_price=PRICE,
        term_structure_rows=(
            {
                "expiry": "2026-09-18",
                "implied_move": 0,
                "volatility": 0.40,
                "implied_move_perc": 4.0,
            },
        ),
        atm_iv=0.40,
    )
    expected = PRICE * 0.40 * math.sqrt(4 / 365.0)
    assert invalid_exact_fallback.status is GateStatus.PASS
    assert invalid_exact_fallback.source == "ATM_IV_FALLBACK"
    assert math.isclose(invalid_exact_fallback.expected_move, expected)
    assert math.isclose(
        invalid_exact_fallback.expected_move_perc,
        expected / PRICE,
    )
    assert invalid_exact_fallback.dte_calendar_days == 4
    print("4. invalid exact UW row -> ATM-IV fallback: PASS")

    missing_exact_fallback = svc.evaluate(
        trading_date=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        underlying_price=PRICE,
        term_structure_rows=(
            {
                "expiry": "2026-09-25",
                "implied_move": 12.0,
                "volatility": 0.50,
                "implied_move_perc": 6.0,
            },
        ),
        atm_iv=0.35,
    )
    assert missing_exact_fallback.status is GateStatus.PASS
    assert missing_exact_fallback.source == "ATM_IV_FALLBACK"
    print("5. missing exact UW expiry -> ATM-IV fallback: PASS")

    unavailable = svc.evaluate(
        trading_date=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        underlying_price=PRICE,
        term_structure_rows=None,
        atm_iv=None,
    )
    assert unavailable.status is GateStatus.UNKNOWN
    assert unavailable.expected_move is None
    assert unavailable.reason == "EXPECTED_MOVE_SOURCES_UNAVAILABLE"
    print("6. both sources unavailable -> UNKNOWN: PASS")

    missing_price = svc.evaluate(
        trading_date=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        underlying_price=None,
        term_structure_rows=(
            {
                "expiry": "2026-09-18",
                "implied_move": 8.0,
                "volatility": 0.40,
                "implied_move_perc": 4.0,
            },
        ),
        atm_iv=0.40,
    )
    assert missing_price.status is GateStatus.UNKNOWN
    assert missing_price.reason == "UNDERLYING_PRICE_UNAVAILABLE"
    print("7. missing underlying price -> UNKNOWN: PASS")

    malformed_rows = svc.evaluate(
        trading_date=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        underlying_price=PRICE,
        term_structure_rows=(
            {"expiry": "2026-09-18", "implied_move": "bad"},
            {"not_expiry": "2026-09-18"},
            "bad-row",
        ),
        atm_iv=0.30,
    )
    assert malformed_rows.status is GateStatus.PASS
    assert malformed_rows.source == "ATM_IV_FALLBACK"
    print("8. malformed/invalid UW data safely falls back: PASS")

    invalid_iv = svc.evaluate(
        trading_date=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        underlying_price=PRICE,
        term_structure_rows=None,
        atm_iv=-0.10,
    )
    assert invalid_iv.status is GateStatus.UNKNOWN
    assert invalid_iv.reason == "EXPECTED_MOVE_SOURCES_UNAVAILABLE"
    print("9. invalid ATM IV does not produce an expected move: PASS")

    raised = False
    try:
        svc.evaluate(
            trading_date=TRADING_DATE,
            target_expiry=TRADING_DATE,
            underlying_price=PRICE,
            term_structure_rows=None,
            atm_iv=0.40,
        )
    except ExpectedMoveError:
        raised = True
    assert raised
    print("10. non-future target expiry rejected: PASS")

    print()
    print("=" * 70)
    print("EXPECTED MOVE SERVICE: PASS 10/10")
    print("=" * 70)


if __name__ == "__main__":
    main()
