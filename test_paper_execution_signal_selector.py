from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from weekly.domain.enums import SignalState
from weekly.services.paper_execution_signal_selector import (
    PaperExecutionSignalSelector,
)

from test_trade_repository import make_signal


def resolution_for(signal):
    return SimpleNamespace(
        transition=SimpleNamespace(
            signal=signal,
        )
    )


def ticker_result(*signals):
    return SimpleNamespace(
        resolution_results=tuple(
            resolution_for(signal)
            for signal in signals
        )
    )


def main() -> None:
    confirmed_1 = replace(
        make_signal(),
        id=10,
        state=SignalState.CONFIRMED,
    )

    confirmed_2 = replace(
        make_signal(),
        id=20,
        state=SignalState.CONFIRMED,
        candidate_sequence=2,
    )

    active = replace(
        make_signal(),
        id=30,
        state=SignalState.ACTIVE,
        candidate_sequence=3,
    )

    rejected = replace(
        make_signal(),
        id=40,
        state=SignalState.REJECTED,
        candidate_sequence=4,
    )

    cycle_result = SimpleNamespace(
        ticker_results=(
            ticker_result(
                confirmed_1,
                active,
                confirmed_1,
            ),
            ticker_result(
                rejected,
                confirmed_2,
            ),
        )
    )

    selector = PaperExecutionSignalSelector()

    result = selector.select(
        cycle_result=cycle_result,
    )

    assert tuple(
        signal.id
        for signal in result.signals
    ) == (
        10,
        20,
    )

    assert all(
        signal.state is SignalState.CONFIRMED
        for signal in result.signals
    )

    print(
        "PAPER EXECUTION SIGNAL SELECTOR: PASS"
    )


if __name__ == "__main__":
    main()
