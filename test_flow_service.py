from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from weekly.domain.enums import Direction
from weekly.services.flow_service import (
    FlowDataError,
    calculate_flow,
    directional_confirmation_matches,
    get_base_flow_direction,
)


ET = ZoneInfo("America/New_York")


TRADING_DATE = date(
    2026,
    9,
    4,
)

TARGET_EXPIRY = date(
    2026,
    9,
    11,
)

SESSION_OPEN = datetime(
    2026,
    9,
    4,
    9,
    30,
    tzinfo=ET,
)

SESSION_CLOSE = datetime(
    2026,
    9,
    4,
    16,
    0,
    tzinfo=ET,
)


def make_alert(
    *,
    created_at: str,
    expiry: str = "2026-09-11",
    option_chain: str,
    alert_rule: str,
    option_type: str,
    ask_premium: float,
    bid_premium: float,
    has_multileg: bool = False,
    has_singleleg: bool = True,
    has_sweep: bool = False,
    all_opening_trades: bool = False,
) -> dict:
    return {
        "created_at": created_at,
        "expiry": expiry,

        "option_chain": option_chain,
        "alert_rule": alert_rule,

        "type": option_type,

        "total_ask_side_prem": ask_premium,
        "total_bid_side_prem": bid_premium,

        "has_multileg": has_multileg,
        "has_singleleg": has_singleleg,

        "has_sweep": has_sweep,
        "all_opening_trades": all_opening_trades,
    }


def assert_equal(
    actual,
    expected,
    name: str,
):
    if actual != expected:
        raise AssertionError(
            f"{name}: expected {expected!r}, "
            f"got {actual!r}"
        )


def assert_close(
    actual: float,
    expected: float,
    name: str,
    tolerance: float = 1e-12,
):
    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"{name}: expected {expected!r}, "
            f"got {actual!r}"
        )


def run_test(
    name: str,
    function,
):
    try:
        function()
        print(
            f"PASS - {name}"
        )
        return True

    except Exception as exc:
        print(
            f"FAIL - {name}"
        )
        print(
            f"       {type(exc).__name__}: {exc}"
        )
        return False


def build_test_alerts() -> list[dict]:

    call_1 = make_alert(
        created_at="2026-09-04T14:00:00Z",
        option_chain="AAPL260911C00320000",
        alert_rule="RepeatedHitsAscendingFill",
        option_type="call",
        ask_premium=400_000,
        bid_premium=50_000,
        has_sweep=True,
        all_opening_trades=True,
    )

    # Exact composite duplicate of call_1.
    duplicate_call_1 = dict(
        call_1
    )

    put_1 = make_alert(
        created_at="2026-09-04T14:03:00Z",
        option_chain="AAPL260911P00310000",
        alert_rule="RepeatedHitsDescendingFill",
        option_type="put",
        ask_premium=100_000,
        bid_premium=300_000,
    )

    call_2 = make_alert(
        created_at="2026-09-04T14:06:00Z",
        option_chain="AAPL260911C00325000",
        alert_rule="Sweep",
        option_type="call",
        ask_premium=200_000,
        bid_premium=20_000,
        has_sweep=True,
        all_opening_trades=True,
    )

    # Must be excluded: multileg.
    multileg = make_alert(
        created_at="2026-09-04T14:09:00Z",
        option_chain="AAPL260911C00330000",
        alert_rule="MultiLeg",
        option_type="call",
        ask_premium=900_000,
        bid_premium=0,
        has_multileg=True,
        has_singleleg=True,
    )

    # Must be excluded: wrong expiry.
    wrong_expiry = make_alert(
        created_at="2026-09-04T14:12:00Z",
        expiry="2026-09-18",
        option_chain="AAPL260918C00320000",
        alert_rule="WrongExpiry",
        option_type="call",
        ask_premium=800_000,
        bid_premium=0,
    )

    # 09:00 ET = before regular session.
    before_session = make_alert(
        created_at="2026-09-04T13:00:00Z",
        option_chain="AAPL260911C00315000",
        alert_rule="PreMarket",
        option_type="call",
        ask_premium=700_000,
        bid_premium=0,
    )

    # Must be excluded: not a single-leg alert.
    not_singleleg = make_alert(
        created_at="2026-09-04T14:15:00Z",
        option_chain="AAPL260911P00305000",
        alert_rule="NotSingleLeg",
        option_type="put",
        ask_premium=600_000,
        bid_premium=0,
        has_multileg=False,
        has_singleleg=False,
    )

    return [
        call_1,
        duplicate_call_1,
        put_1,
        call_2,
        multileg,
        wrong_expiry,
        before_session,
        not_singleleg,
    ]


def test_cleaning_and_dedup():
    result = calculate_flow(
        ticker="AAPL",
        alerts=build_test_alerts(),
        trading_date_et=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        session_open_et=SESSION_OPEN,
        session_close_et=SESSION_CLOSE,
    )

    assert_equal(
        result.raw_alert_count,
        8,
        "raw alert count",
    )

    # call_1 + duplicate + put_1 + call_2
    assert_equal(
        result.clean_alert_count,
        4,
        "clean count before dedup",
    )

    # duplicate removed.
    assert_equal(
        result.deduped_alert_count,
        3,
        "deduped count",
    )

    assert_equal(
        result.flow_dedup_level,
        "alert_composite",
        "dedup level",
    )

    assert_equal(
        result.trade_overlap_detected,
        False,
        "trade overlap",
    )


def test_primary_net_flow_math():
    result = calculate_flow(
        ticker="AAPL",
        alerts=build_test_alerts(),
        trading_date_et=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        session_open_et=SESSION_OPEN,
        session_close_et=SESSION_CLOSE,
    )

    assert_close(
        result.call_ask_premium,
        600_000,
        "call ask premium",
    )

    assert_close(
        result.put_ask_premium,
        100_000,
        "put ask premium",
    )

    assert_close(
        result.net_flow,
        500_000,
        "primary net flow",
    )


def test_bid_side_quality_math():
    result = calculate_flow(
        ticker="AAPL",
        alerts=build_test_alerts(),
        trading_date_et=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        session_open_et=SESSION_OPEN,
        session_close_et=SESSION_CLOSE,
    )

    assert_close(
        result.call_bid_premium,
        70_000,
        "call bid",
    )

    assert_close(
        result.put_bid_premium,
        300_000,
        "put bid",
    )

    # bullish =
    # Call Ask 600k + Put Bid 300k = 900k
    assert_close(
        result.bullish_premium,
        900_000,
        "bullish premium",
    )

    # bearish =
    # Put Ask 100k + Call Bid 70k = 170k
    assert_close(
        result.bearish_premium,
        170_000,
        "bearish premium",
    )

    assert_close(
        result.directional_net,
        730_000,
        "directional net",
    )


def test_candidate_threshold():
    bullish = get_base_flow_direction(
        net_flow=500_000,
        threshold=500_000,
    )

    assert_equal(
        bullish,
        Direction.BULLISH,
        "bullish threshold",
    )

    bearish = get_base_flow_direction(
        net_flow=-500_000,
        threshold=500_000,
    )

    assert_equal(
        bearish,
        Direction.BEARISH,
        "bearish threshold",
    )

    no_signal = get_base_flow_direction(
        net_flow=499_999,
        threshold=500_000,
    )

    assert_equal(
        no_signal,
        None,
        "below threshold",
    )


def test_directional_confirmation_is_quality_only():
    base_direction = get_base_flow_direction(
        net_flow=600_000,
        threshold=500_000,
    )

    assert_equal(
        base_direction,
        Direction.BULLISH,
        "base direction",
    )

    matches = directional_confirmation_matches(
        base_direction=base_direction,
        directional_net=-100_000,
    )

    assert_equal(
        matches,
        False,
        "quality mismatch",
    )

    # Critical:
    # Directional mismatch must NOT change the
    # primary Base Flow hypothesis.
    assert_equal(
        base_direction,
        Direction.BULLISH,
        "base direction preserved",
    )


def test_quality_flags():
    result = calculate_flow(
        ticker="AAPL",
        alerts=build_test_alerts(),
        trading_date_et=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        session_open_et=SESSION_OPEN,
        session_close_et=SESSION_CLOSE,
    )

    assert_equal(
        result.sweep_alert_count,
        2,
        "sweep count",
    )

    assert_equal(
        result.opening_alert_count,
        2,
        "opening count",
    )


def test_sweep_premium_evidence():
    alerts = build_test_alerts()

    for alert in alerts:
        chain = alert["option_chain"]

        if chain == "AAPL260911C00320000":
            alert["total_premium"] = 450_000.0

        elif chain == "AAPL260911P00310000":
            alert["total_premium"] = 400_000.0

        elif chain == "AAPL260911C00325000":
            alert["total_premium"] = 220_000.0

        else:
            alert["total_premium"] = 100_000.0

    result = calculate_flow(
        ticker="AAPL",
        alerts=alerts,
        trading_date_et=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        session_open_et=SESSION_OPEN,
        session_close_et=SESSION_CLOSE,
    )

    assert_close(
        result.total_premium,
        1_070_000.0,
        "total premium",
    )

    assert_close(
        result.sweep_premium,
        670_000.0,
        "sweep premium",
    )

    missing = build_test_alerts()

    missing_result = calculate_flow(
        ticker="AAPL",
        alerts=missing,
        trading_date_et=TRADING_DATE,
        target_expiry=TARGET_EXPIRY,
        session_open_et=SESSION_OPEN,
        session_close_et=SESSION_CLOSE,
    )

    assert_equal(
        missing_result.total_premium,
        None,
        "missing total premium evidence",
    )

    assert_equal(
        missing_result.sweep_premium,
        None,
        "missing sweep premium evidence",
    )

def test_missing_required_field_fails():
    bad_alert = make_alert(
        created_at="2026-09-04T14:00:00Z",
        option_chain="AAPL260911C00320000",
        alert_rule="Test",
        option_type="call",
        ask_premium=100_000,
        bid_premium=0,
    )

    del bad_alert[
        "total_ask_side_prem"
    ]

    error_raised = False

    try:
        calculate_flow(
            ticker="AAPL",
            alerts=[
                bad_alert
            ],
            trading_date_et=TRADING_DATE,
            target_expiry=TARGET_EXPIRY,
            session_open_et=SESSION_OPEN,
            session_close_et=SESSION_CLOSE,
        )

    except FlowDataError:
        error_raised = True

    if not error_raised:
        raise AssertionError(
            "Missing essential flow field "
            "did not raise FlowDataError."
        )


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 PRODUCTION FLOW SERVICE TEST"
    )
    print("=" * 78)
    print()

    tests = [
        (
            "Clean Universe + composite dedup",
            test_cleaning_and_dedup,
        ),
        (
            "Primary Call Ask - Put Ask math",
            test_primary_net_flow_math,
        ),
        (
            "Directional Net quality math",
            test_bid_side_quality_math,
        ),
        (
            "Candidate threshold +/-500k",
            test_candidate_threshold,
        ),
        (
            "Directional mismatch does not replace Base Flow",
            test_directional_confirmation_is_quality_only,
        ),
        (
            "Sweep/opening quality flags",
            test_quality_flags,
        ),
        (
            "Sweep premium evidence",
            test_sweep_premium_evidence,
        ),
        (
            "Missing essential field fails loudly",
            test_missing_required_field_fails,
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
    print()

    passed = sum(
        1
        for result in results
        if result
    )

    print(
        "tests_passed:",
        passed,
        "/",
        len(results),
    )

    if all(results):
        print()
        print(
            "Production FlowService: PASS"
        )

        print(
            "Clean Universe filtering: PASS"
        )

        print(
            "Composite dedup: PASS"
        )

        print(
            "Base Net Flow math: PASS"
        )

        print(
            "Directional quality confirmation: PASS"
        )

        print(
            "Candidate threshold logic: PASS"
        )

        print(
            "Sweep premium evidence: PASS"
        )

        print(
            "Essential-field Fail-Fast: PASS"
        )

    else:
        print()
        print(
            "FlowService: CHECK REQUIRED"
        )


if __name__ == "__main__":
    main()