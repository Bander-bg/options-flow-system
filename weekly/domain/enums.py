from __future__ import annotations

from enum import Enum


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class SignalState(str, Enum):
    CANDIDATE = "CANDIDATE"
    INVALIDATED = "INVALIDATED"
    REJECTED = "REJECTED"
    DATA_BLOCKED = "DATA_BLOCKED"
    DATA_UNRESOLVED = "DATA_UNRESOLVED"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    ACCELERATED = "ACCELERATED"
    EXPIRED = "EXPIRED"


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"

    @property
    def sign(self) -> int:
        if self is Direction.BULLISH:
            return 1

        return -1


class OptionRight(str, Enum):
    CALL = "call"
    PUT = "put"


class OutcomeScope(str, Enum):
    CANDIDATE = "CANDIDATE"
    RESOLUTION = "RESOLUTION"


class OutcomeStatus(str, Enum):
    PENDING = "PENDING"
    OBSERVED = "OBSERVED"
    UNAVAILABLE = "UNAVAILABLE"
    EXPIRED = "EXPIRED"


class ExecutionMode(str, Enum):
    PAPER = "PAPER"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class TradeIntent(str, Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(str, Enum):
    REQUESTED = "REQUESTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class DataHealthStatus(str, Enum):
    PASS = "PASS"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


TERMINAL_SIGNAL_STATES = frozenset(
    {
        SignalState.INVALIDATED,
        SignalState.REJECTED,
        SignalState.DATA_UNRESOLVED,
        SignalState.EXPIRED,
    }
)


LOCKED_RESOLUTION_STATES = frozenset(
    {
        SignalState.INVALIDATED,
        SignalState.REJECTED,
        SignalState.DATA_UNRESOLVED,
        SignalState.CONFIRMED,
        SignalState.ACTIVE,
        SignalState.ACCELERATED,
        SignalState.EXPIRED,
    }
)


def is_terminal_signal_state(
    state: SignalState,
) -> bool:
    return state in TERMINAL_SIGNAL_STATES


def is_locked_resolution_state(
    state: SignalState,
) -> bool:
    return state in LOCKED_RESOLUTION_STATES