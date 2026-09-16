
from datetime import date

from weekly.domain.enums import GateStatus
from weekly.services.earnings_event_risk_service import (
    EarningsEventRiskError,
    EarningsEventRiskService,
)


def main() -> None:
    svc = EarningsEventRiskService()

    trading_date = date(2026, 9, 14)
    expiry = date(2026, 9, 18)

    missing = svc.evaluate(
        trading_date_et=trading_date,
        target_expiry=expiry,
        next_earnings_date=None,
        earnings_time=None,
    )
    assert missing.status is GateStatus.UNKNOWN
    assert missing.reason == "NEXT_EARNINGS_UNAVAILABLE"

    stale = svc.evaluate(
        trading_date_et=trading_date,
        target_expiry=expiry,
        next_earnings_date=date(2026, 9, 11),
        earnings_time="AMC",
    )
    assert stale.status is GateStatus.UNKNOWN
    assert stale.reason == "NEXT_EARNINGS_DATE_STALE"

    before_expiry = svc.evaluate(
        trading_date_et=trading_date,
        target_expiry=expiry,
        next_earnings_date=date(2026, 9, 17),
        earnings_time="AMC",
    )
    assert before_expiry.status is GateStatus.FAIL
    assert before_expiry.reason == "EARNINGS_BEFORE_TARGET_EXPIRY"

    after_expiry = svc.evaluate(
        trading_date_et=trading_date,
        target_expiry=expiry,
        next_earnings_date=date(2026, 9, 21),
        earnings_time=None,
    )
    assert after_expiry.status is GateStatus.PASS
    assert after_expiry.reason == "EARNINGS_AFTER_TARGET_EXPIRY"

    same_day_bmo = svc.evaluate(
        trading_date_et=trading_date,
        target_expiry=expiry,
        next_earnings_date=expiry,
        earnings_time="before market open",
    )
    assert same_day_bmo.status is GateStatus.FAIL
    assert same_day_bmo.earnings_time_normalized == "BMO"
    assert same_day_bmo.reason == "EARNINGS_ON_EXPIRY_BMO"

    same_day_amc = svc.evaluate(
        trading_date_et=trading_date,
        target_expiry=expiry,
        next_earnings_date=expiry,
        earnings_time="postmarket",
    )
    assert same_day_amc.status is GateStatus.PASS
    assert same_day_amc.earnings_time_normalized == "AMC"
    assert same_day_amc.reason == "EARNINGS_ON_EXPIRY_AMC"

    same_day_unknown = svc.evaluate(
        trading_date_et=trading_date,
        target_expiry=expiry,
        next_earnings_date=expiry,
        earnings_time="during market",
    )
    assert same_day_unknown.status is GateStatus.UNKNOWN
    assert same_day_unknown.earnings_time_normalized is None
    assert same_day_unknown.reason == "EARNINGS_ON_EXPIRY_TIME_UNKNOWN"

    raised = False
    try:
        svc.evaluate(
            trading_date_et=trading_date,
            target_expiry=date(2026, 9, 11),
            next_earnings_date=date(2026, 9, 21),
            earnings_time="AMC",
        )
    except EarningsEventRiskError:
        raised = True
    assert raised

    print("1. missing next earnings -> UNKNOWN: PASS")
    print("2. stale next earnings -> UNKNOWN: PASS")
    print("3. earnings before target expiry -> FAIL: PASS")
    print("4. earnings after target expiry -> PASS: PASS")
    print("5. earnings on expiry BMO -> FAIL: PASS")
    print("6. earnings on expiry AMC -> PASS: PASS")
    print("7. earnings on expiry unknown time -> UNKNOWN: PASS")
    print("8. invalid expiry before trading date rejected: PASS")
    print()
    print("=" * 70)
    print("EARNINGS EVENT RISK SERVICE: PASS 8/8")
    print("=" * 70)


if __name__ == "__main__":
    main()
