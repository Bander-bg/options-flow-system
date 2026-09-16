from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class SignalState(str, Enum):
    CANDIDATE = "CANDIDATE"
    DATA_BLOCKED = "DATA_BLOCKED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    INVALIDATED = "INVALIDATED"
    DATA_UNRESOLVED = "DATA_UNRESOLVED"


LOCKED_STATES = {
    SignalState.CONFIRMED,
    SignalState.REJECTED,
    SignalState.INVALIDATED,
    SignalState.DATA_UNRESOLVED,
}


@dataclass
class EvaluationResult:
    state: SignalState
    reason: str | None = None
    rejection_reasons: list[str] | None = None


def evaluate_candidate(
    *,
    current_state: SignalState,
    hypothesis_flow_valid: bool,
    hypothesis_direction_same: bool,
    hard_gates: dict[str, GateStatus],
    price_action_pass_seen: bool,
    price_action_data_complete: bool,
    now: datetime,
    requested_confirmation_deadline_at: datetime,
    confirmation_deadline_at: datetime,
    official_session_close: datetime,
) -> EvaluationResult:
    """
    weekly_v1 state precedence:

    1) Hypothesis disappeared/reversed -> INVALIDATED
    2) Any confirmed Hard FAIL -> REJECTED
    3) Before deadline:
       - Hard UNKNOWN -> DATA_BLOCKED
       - all Hard PASS + Price Action PASS -> CONFIRMED
       - otherwise remain CANDIDATE
    4) At/after deadline:
       - valid PASS already seen -> CONFIRMED
       - if session cut full window -> INVALIDATED: session_closed
       - natural deadline + UNKNOWN -> DATA_UNRESOLVED
       - natural deadline + incomplete price data -> DATA_UNRESOLVED
       - natural deadline + complete data + no PA PASS
         -> REJECTED: price_action_timeout
    """

    # A terminal/locked candidate cannot later be resurrected.
    if current_state in LOCKED_STATES:
        return EvaluationResult(
            state=current_state,
            reason="terminal_state_locked",
        )

    # --------------------------------------------------
    # 1. INVALIDATION has highest precedence.
    # --------------------------------------------------

    if (
        not hypothesis_flow_valid
        or not hypothesis_direction_same
    ):
        return EvaluationResult(
            state=SignalState.INVALIDATED,
            reason="hypothesis_invalidated",
        )

    # --------------------------------------------------
    # 2. Confirmed Hard FAIL beats UNKNOWN.
    # --------------------------------------------------

    fail_reasons = sorted(
        gate_name
        for gate_name, status in hard_gates.items()
        if status == GateStatus.FAIL
    )

    if fail_reasons:
        return EvaluationResult(
            state=SignalState.REJECTED,
            reason="hard_gate_fail",
            rejection_reasons=fail_reasons,
        )

    unknown_gates = sorted(
        gate_name
        for gate_name, status in hard_gates.items()
        if status == GateStatus.UNKNOWN
    )

    deadline_reached = (
        now >= confirmation_deadline_at
    )

    # --------------------------------------------------
    # 3. Before deadline.
    # --------------------------------------------------

    if not deadline_reached:

        if unknown_gates:
            return EvaluationResult(
                state=SignalState.DATA_BLOCKED,
                reason="hard_gate_unknown",
            )

        if price_action_pass_seen:
            return EvaluationResult(
                state=SignalState.CONFIRMED,
                reason="all_hard_gates_passed",
            )

        return EvaluationResult(
            state=SignalState.CANDIDATE,
            reason="awaiting_price_action",
        )

    # --------------------------------------------------
    # 4. At / after deadline.
    #
    # A valid Price Action PASS that happened inside
    # the window may be processed by the allowed grace
    # poll. Its event-time validity is checked separately.
    # --------------------------------------------------

    if (
        price_action_pass_seen
        and not unknown_gates
    ):
        return EvaluationResult(
            state=SignalState.CONFIRMED,
            reason="valid_in_window_pass_processed",
        )

    # Full requested confirmation window did NOT fit
    # inside the session.
    session_cut_window = (
        requested_confirmation_deadline_at
        > official_session_close
    )

    if session_cut_window:
        return EvaluationResult(
            state=SignalState.INVALIDATED,
            reason="session_closed",
        )

    # Natural full deadline completed.
    if unknown_gates:
        return EvaluationResult(
            state=SignalState.DATA_UNRESOLVED,
            reason="hard_data_unknown_at_deadline",
        )

    if not price_action_data_complete:
        return EvaluationResult(
            state=SignalState.DATA_UNRESOLVED,
            reason="price_action_data_incomplete_at_deadline",
        )

    return EvaluationResult(
        state=SignalState.REJECTED,
        reason="price_action_timeout",
        rejection_reasons=[
            "price_action_timeout"
        ],
    )


def event_is_usable(
    *,
    event_timestamp: datetime,
    candidate_at: datetime,
    confirmation_deadline_at: datetime,
    processing_at: datetime,
    grace_poll_number: int,
    deadline_processing_grace_polls: int = 1,
) -> bool:
    """
    Event Time != Processing Time.

    The evidence itself must occur inside:
        candidate_at < event_timestamp <= deadline

    If processing happens after deadline, only the
    configured number of grace polls may consume that
    already-valid evidence.
    """

    event_inside_window = (
        candidate_at
        < event_timestamp
        <= confirmation_deadline_at
    )

    if not event_inside_window:
        return False

    # Processed before or exactly at deadline:
    # normal evaluation.
    if processing_at <= confirmation_deadline_at:
        return True

    # Processed after deadline:
    # only grace poll(s) may consume pre-deadline evidence.
    return (
        1
        <= grace_poll_number
        <= deadline_processing_grace_polls
    )


def dt(
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        2026,
        9,
        4,
        hour,
        minute,
        tzinfo=ET,
    )


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


def test_invalidation_beats_fail_and_unknown():
    result = evaluate_candidate(
        current_state=SignalState.CANDIDATE,
        hypothesis_flow_valid=False,
        hypothesis_direction_same=True,
        hard_gates={
            "vwap_mismatch": GateStatus.FAIL,
            "eligible_contract": GateStatus.UNKNOWN,
        },
        price_action_pass_seen=False,
        price_action_data_complete=False,
        now=dt(10, 5),
        requested_confirmation_deadline_at=dt(10, 30),
        confirmation_deadline_at=dt(10, 30),
        official_session_close=dt(16, 0),
    )

    assert_equal(
        result.state,
        SignalState.INVALIDATED,
        "state",
    )


def test_fail_beats_unknown():
    result = evaluate_candidate(
        current_state=SignalState.CANDIDATE,
        hypothesis_flow_valid=True,
        hypothesis_direction_same=True,
        hard_gates={
            "vwap_mismatch": GateStatus.FAIL,
            "eligible_contract": GateStatus.UNKNOWN,
        },
        price_action_pass_seen=False,
        price_action_data_complete=False,
        now=dt(10, 5),
        requested_confirmation_deadline_at=dt(10, 30),
        confirmation_deadline_at=dt(10, 30),
        official_session_close=dt(16, 0),
    )

    assert_equal(
        result.state,
        SignalState.REJECTED,
        "state",
    )

    assert_equal(
        result.rejection_reasons,
        ["vwap_mismatch"],
        "rejection_reasons",
    )


def test_unknown_before_deadline_data_blocked():
    result = evaluate_candidate(
        current_state=SignalState.CANDIDATE,
        hypothesis_flow_valid=True,
        hypothesis_direction_same=True,
        hard_gates={
            "vwap_alignment": GateStatus.PASS,
            "efficiency_ratio": GateStatus.PASS,
            "eligible_contract": GateStatus.UNKNOWN,
            "earnings_event_risk": GateStatus.PASS,
        },
        price_action_pass_seen=False,
        price_action_data_complete=False,
        now=dt(10, 10),
        requested_confirmation_deadline_at=dt(10, 30),
        confirmation_deadline_at=dt(10, 30),
        official_session_close=dt(16, 0),
    )

    assert_equal(
        result.state,
        SignalState.DATA_BLOCKED,
        "state",
    )


def test_all_pass_confirms():
    result = evaluate_candidate(
        current_state=SignalState.CANDIDATE,
        hypothesis_flow_valid=True,
        hypothesis_direction_same=True,
        hard_gates={
            "vwap_alignment": GateStatus.PASS,
            "efficiency_ratio": GateStatus.PASS,
            "eligible_contract": GateStatus.PASS,
            "earnings_event_risk": GateStatus.PASS,
        },
        price_action_pass_seen=True,
        price_action_data_complete=True,
        now=dt(10, 20),
        requested_confirmation_deadline_at=dt(10, 30),
        confirmation_deadline_at=dt(10, 30),
        official_session_close=dt(16, 0),
    )

    assert_equal(
        result.state,
        SignalState.CONFIRMED,
        "state",
    )


def test_natural_deadline_unknown_becomes_unresolved():
    result = evaluate_candidate(
        current_state=SignalState.DATA_BLOCKED,
        hypothesis_flow_valid=True,
        hypothesis_direction_same=True,
        hard_gates={
            "vwap_alignment": GateStatus.PASS,
            "efficiency_ratio": GateStatus.PASS,
            "eligible_contract": GateStatus.UNKNOWN,
            "earnings_event_risk": GateStatus.PASS,
        },
        price_action_pass_seen=False,
        price_action_data_complete=True,
        now=dt(10, 32),
        requested_confirmation_deadline_at=dt(10, 30),
        confirmation_deadline_at=dt(10, 30),
        official_session_close=dt(16, 0),
    )

    assert_equal(
        result.state,
        SignalState.DATA_UNRESOLVED,
        "state",
    )


def test_session_cut_becomes_invalidated():
    result = evaluate_candidate(
        current_state=SignalState.CANDIDATE,
        hypothesis_flow_valid=True,
        hypothesis_direction_same=True,
        hard_gates={
            "vwap_alignment": GateStatus.PASS,
            "efficiency_ratio": GateStatus.PASS,
            "eligible_contract": GateStatus.PASS,
            "earnings_event_risk": GateStatus.PASS,
        },
        price_action_pass_seen=False,
        price_action_data_complete=True,
        now=dt(16, 0),
        requested_confirmation_deadline_at=dt(9, 50).replace(
            day=8
        ),
        confirmation_deadline_at=dt(16, 0),
        official_session_close=dt(16, 0),
    )

    assert_equal(
        result.state,
        SignalState.INVALIDATED,
        "state",
    )

    assert_equal(
        result.reason,
        "session_closed",
        "reason",
    )


def test_price_action_timeout():
    result = evaluate_candidate(
        current_state=SignalState.CANDIDATE,
        hypothesis_flow_valid=True,
        hypothesis_direction_same=True,
        hard_gates={
            "vwap_alignment": GateStatus.PASS,
            "efficiency_ratio": GateStatus.PASS,
            "eligible_contract": GateStatus.PASS,
            "earnings_event_risk": GateStatus.PASS,
        },
        price_action_pass_seen=False,
        price_action_data_complete=True,
        now=dt(10, 31),
        requested_confirmation_deadline_at=dt(10, 30),
        confirmation_deadline_at=dt(10, 30),
        official_session_close=dt(16, 0),
    )

    assert_equal(
        result.state,
        SignalState.REJECTED,
        "state",
    )

    assert_equal(
        result.reason,
        "price_action_timeout",
        "reason",
    )


def test_grace_poll_accepts_in_window_event():
    usable = event_is_usable(
        event_timestamp=dt(10, 30),
        candidate_at=dt(10, 0),
        confirmation_deadline_at=dt(10, 30),
        processing_at=dt(10, 32),
        grace_poll_number=1,
        deadline_processing_grace_polls=1,
    )

    assert_equal(
        usable,
        True,
        "usable",
    )


def test_grace_poll_rejects_post_deadline_event():
    usable = event_is_usable(
        event_timestamp=dt(10, 31),
        candidate_at=dt(10, 0),
        confirmation_deadline_at=dt(10, 30),
        processing_at=dt(10, 32),
        grace_poll_number=1,
        deadline_processing_grace_polls=1,
    )

    assert_equal(
        usable,
        False,
        "usable",
    )


def test_second_grace_poll_is_not_allowed():
    usable = event_is_usable(
        event_timestamp=dt(10, 29),
        candidate_at=dt(10, 0),
        confirmation_deadline_at=dt(10, 30),
        processing_at=dt(10, 35),
        grace_poll_number=2,
        deadline_processing_grace_polls=1,
    )

    assert_equal(
        usable,
        False,
        "usable",
    )


def test_terminal_state_cannot_resurrect():
    result = evaluate_candidate(
        current_state=SignalState.DATA_UNRESOLVED,
        hypothesis_flow_valid=True,
        hypothesis_direction_same=True,
        hard_gates={
            "vwap_alignment": GateStatus.PASS,
            "efficiency_ratio": GateStatus.PASS,
            "eligible_contract": GateStatus.PASS,
            "earnings_event_risk": GateStatus.PASS,
        },
        price_action_pass_seen=True,
        price_action_data_complete=True,
        now=dt(10, 40),
        requested_confirmation_deadline_at=dt(10, 30),
        confirmation_deadline_at=dt(10, 30),
        official_session_close=dt(16, 0),
    )

    assert_equal(
        result.state,
        SignalState.DATA_UNRESOLVED,
        "state",
    )


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 STATE MACHINE + DEADLINE GRACE TEST"
    )
    print("=" * 78)
    print()

    tests = [
        (
            "Invalidation beats FAIL + UNKNOWN",
            test_invalidation_beats_fail_and_unknown,
        ),
        (
            "Hard FAIL beats Hard UNKNOWN",
            test_fail_beats_unknown,
        ),
        (
            "Hard UNKNOWN before deadline -> DATA_BLOCKED",
            test_unknown_before_deadline_data_blocked,
        ),
        (
            "All Hard PASS + Price Action PASS -> CONFIRMED",
            test_all_pass_confirms,
        ),
        (
            "Natural deadline + Hard UNKNOWN -> DATA_UNRESOLVED",
            test_natural_deadline_unknown_becomes_unresolved,
        ),
        (
            "Session cuts full window -> INVALIDATED: session_closed",
            test_session_cut_becomes_invalidated,
        ),
        (
            "Natural deadline + complete data + no PA PASS -> REJECTED",
            test_price_action_timeout,
        ),
        (
            "Grace poll accepts valid event inside deadline",
            test_grace_poll_accepts_in_window_event,
        ),
        (
            "Grace poll rejects event after deadline",
            test_grace_poll_rejects_post_deadline_event,
        ),
        (
            "Only one deadline grace poll is allowed",
            test_second_grace_poll_is_not_allowed,
        ),
        (
            "Terminal DATA_UNRESOLVED cannot resurrect",
            test_terminal_state_cannot_resurrect,
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
            "State precedence: PASS"
        )
        print(
            "Deadline event-time/grace semantics: PASS"
        )
        print(
            "Terminal-state locking: PASS"
        )
    else:
        print()
        print(
            "State-machine logic: CHECK REQUIRED"
        )


if __name__ == "__main__":
    main()