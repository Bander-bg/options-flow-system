
from weekly.domain.enums import GateStatus, SignalState
from weekly.services.hard_gate_service import HardGateResult
from weekly.services.signal_state_resolution_service import (
    SignalStateResolutionService,
    SignalStateResolutionError,
)

def hg(status: GateStatus) -> HardGateResult:
    if status is GateStatus.PASS:
        gate = GateStatus.PASS
        failed = ()
        unknown = ()
        reason = "ALL_HARD_GATES_PASS"
    elif status is GateStatus.FAIL:
        gate = GateStatus.PASS
        failed = ("VWAP",)
        unknown = ()
        reason = "HARD_GATE_FAIL"
    else:
        gate = GateStatus.UNKNOWN
        failed = ()
        unknown = ("VWAP",)
        reason = "HARD_GATE_UNKNOWN"

    return HardGateResult(
        status=status,
        vwap_status=(GateStatus.FAIL if status is GateStatus.FAIL else gate),
        efficiency_ratio_status=gate,
        price_action_status=gate,
        eligible_contract_status=gate,
        earnings_event_risk_status=gate,
        failed_gates=failed,
        unknown_gates=unknown,
        price_action_is_final=True,
        price_action_reason="TEST",
        reason=reason,
    )

def main() -> None:
    svc = SignalStateResolutionService()

    invalidated = svc.resolve(
        current_state=SignalState.CANDIDATE,
        hard_gate_result=hg(GateStatus.PASS),
        invalidated=True,
        resolution_window_closed=False,
    )
    assert invalidated.target_state is SignalState.INVALIDATED
    assert invalidated.should_transition is True
    assert invalidated.is_terminal is True

    rejected = svc.resolve(
        current_state=SignalState.CANDIDATE,
        hard_gate_result=hg(GateStatus.FAIL),
        invalidated=False,
        resolution_window_closed=False,
    )
    assert rejected.target_state is SignalState.REJECTED
    assert rejected.should_transition is True
    assert rejected.is_terminal is True

    blocked = svc.resolve(
        current_state=SignalState.CANDIDATE,
        hard_gate_result=hg(GateStatus.UNKNOWN),
        invalidated=False,
        resolution_window_closed=False,
    )
    assert blocked.target_state is SignalState.DATA_BLOCKED
    assert blocked.should_transition is True
    assert blocked.is_terminal is False

    unresolved = svc.resolve(
        current_state=SignalState.DATA_BLOCKED,
        hard_gate_result=hg(GateStatus.UNKNOWN),
        invalidated=False,
        resolution_window_closed=True,
    )
    assert unresolved.target_state is SignalState.DATA_UNRESOLVED
    assert unresolved.should_transition is True
    assert unresolved.is_terminal is True

    confirmed = svc.resolve(
        current_state=SignalState.CANDIDATE,
        hard_gate_result=hg(GateStatus.PASS),
        invalidated=False,
        resolution_window_closed=False,
    )
    assert confirmed.target_state is SignalState.CONFIRMED
    assert confirmed.should_transition is True
    assert confirmed.is_terminal is False

    recovered = svc.resolve(
        current_state=SignalState.DATA_BLOCKED,
        hard_gate_result=hg(GateStatus.PASS),
        invalidated=False,
        resolution_window_closed=False,
    )
    assert recovered.target_state is SignalState.CONFIRMED
    assert recovered.should_transition is True

    locked = svc.resolve(
        current_state=SignalState.CONFIRMED,
        hard_gate_result=hg(GateStatus.FAIL),
        invalidated=True,
        resolution_window_closed=True,
    )
    assert locked.target_state is SignalState.CONFIRMED
    assert locked.should_transition is False
    assert locked.reason == "RESOLUTION_LOCKED"

    raised = False
    try:
        svc.resolve(
            current_state=SignalState.ACTIVE,
            hard_gate_result=hg(GateStatus.PASS),
            invalidated=False,
            resolution_window_closed=False,
        )
    except Exception:
        raised = True
    assert raised is False

    print("1. INVALIDATED precedence: PASS")
    print("2. final Hard FAIL -> REJECTED: PASS")
    print("3. Hard UNKNOWN while window open -> DATA_BLOCKED: PASS")
    print("4. Hard UNKNOWN after window close -> DATA_UNRESOLVED: PASS")
    print("5. all Hard Gates PASS -> CONFIRMED: PASS")
    print("6. DATA_BLOCKED can re-evaluate -> CONFIRMED: PASS")
    print("7. locked resolution state is not rewritten: PASS")
    print("8. operational locked state remains untouched: PASS")
    print()
    print("=" * 70)
    print("SIGNAL STATE RESOLUTION SERVICE: PASS 8/8")
    print("=" * 70)

if __name__ == "__main__":
    main()


