from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from weekly.db.signal_repository import (
    SignalRepository,
)
from weekly.domain.enums import (
    Direction,
    SignalState,
)
from weekly.domain.models import (
    FlowSnapshot,
    Signal,
)
from weekly.services.calendar_service import (
    as_et,
    confirmation_deadline,
    find_session,
    session_close,
    session_open,
)
from weekly.services.flow_service import (
    get_base_flow_direction,
)


@dataclass(frozen=True)
class CandidateResult:
    created: bool
    reason: str
    direction: Direction | None
    signal: Signal | None


class CandidateService:
    """
    weekly_v1 initial Candidate creation.

    Responsibilities:
    - evaluate Base Net Flow threshold
    - determine bullish/bearish direction
    - validate Candidate time
    - prevent duplicate initial Candidates
    - allocate candidate_sequence
    - calculate confirmation deadlines
    - persist Signal(state=CANDIDATE)

    Explicitly NOT responsible for:
    - re-arm
    - Price Action confirmation
    - Hard Gates
    - CONFIRMED transition
    - contract selection
    - scoring
    - execution
    """

    def __init__(
        self,
        repository: SignalRepository | None = None,
    ):
        self.repository = (
            repository
            or SignalRepository()
        )

    def create_initial_candidate(
        self,
        *,
        snapshot: FlowSnapshot,
        candidate_at: datetime,
        calendar,
        strategy_version: str,
        config_hash: str,
        flow_threshold: float,
        confirmation_minutes: int,
        theta_convention_status: str,
        scenario_return_enabled: bool,
    ) -> CandidateResult:

        # --------------------------------------------------
        # BASIC INPUT VALIDATION
        # --------------------------------------------------

        if not strategy_version.strip():
            raise ValueError(
                "strategy_version cannot be empty"
            )

        if not config_hash.strip():
            raise ValueError(
                "config_hash cannot be empty"
            )

        if flow_threshold <= 0:
            raise ValueError(
                "flow_threshold must be > 0"
            )

        if confirmation_minutes <= 0:
            raise ValueError(
                "confirmation_minutes must be > 0"
            )

        if candidate_at.tzinfo is None:
            raise ValueError(
                "candidate_at must be timezone-aware"
            )

        if not theta_convention_status.strip():
            raise ValueError(
                "theta_convention_status "
                "cannot be empty"
            )

        if not isinstance(
            scenario_return_enabled,
            bool,
        ):
            raise ValueError(
                "scenario_return_enabled "
                "must be bool"
            )

        # --------------------------------------------------
        # NORMALIZE TIMES TO ET
        # --------------------------------------------------

        candidate_at_et = as_et(
            candidate_at
        )

        snapshot_captured_at_et = as_et(
            snapshot.captured_at
        )

        # --------------------------------------------------
        # TRADING DATE MUST MATCH
        # --------------------------------------------------

        if (
            candidate_at_et.date()
            != snapshot.trading_date_et
        ):
            raise ValueError(
                "candidate_at ET date must match "
                "snapshot.trading_date_et"
            )

        # --------------------------------------------------
        # CANDIDATE CANNOT PRECEDE FLOW SNAPSHOT
        # --------------------------------------------------

        if (
            candidate_at_et
            < snapshot_captured_at_et
        ):
            raise ValueError(
                "candidate_at cannot be earlier "
                "than snapshot.captured_at"
            )

        # --------------------------------------------------
        # CANDIDATE MUST BE INSIDE OFFICIAL RTH SESSION
        # --------------------------------------------------

        current_session = find_session(
            trading_date_et=(
                snapshot.trading_date_et
            ),
            calendar=calendar,
        )

        if current_session is None:
            raise ValueError(
                "No official trading session "
                "found for snapshot trading date"
            )

        current_session_open = (
            session_open(
                current_session
            )
        )

        current_session_close = (
            session_close(
                current_session
            )
        )

        if not (
            current_session_open
            <= candidate_at_et
            <= current_session_close
        ):
            raise ValueError(
                "candidate_at must be inside "
                "the official RTH session"
            )

        # --------------------------------------------------
        # DETERMINE BASE FLOW DIRECTION
        # --------------------------------------------------

        direction = (
            get_base_flow_direction(
                net_flow=snapshot.net_flow,
                threshold=flow_threshold,
            )
        )

        # --------------------------------------------------
        # BELOW THRESHOLD -> NO CANDIDATE
        # --------------------------------------------------

        if direction is None:
            return CandidateResult(
                created=False,
                reason="BELOW_FLOW_THRESHOLD",
                direction=None,
                signal=None,
            )

        # --------------------------------------------------
        # DUPLICATE INITIAL CANDIDATE PROTECTION
        # --------------------------------------------------
        #
        # Any later Candidate for the same logical
        # scope must go through the dedicated re-arm
        # rules. Scanner polling alone must never
        # create Candidate #2.
        # --------------------------------------------------

        existing = (
            self.repository.get_latest(
                strategy_version=(
                    strategy_version
                ),
                ticker=(
                    snapshot.ticker
                ),
                trading_date_et=(
                    snapshot.trading_date_et
                ),
                target_expiry=(
                    snapshot.target_expiry
                ),
                direction=(
                    direction
                ),
            )
        )

        if existing is not None:
            return CandidateResult(
                created=False,
                reason=(
                    "EXISTING_SIGNAL_REQUIRES_REARM"
                ),
                direction=direction,
                signal=existing,
            )

        # --------------------------------------------------
        # CANDIDATE SEQUENCE
        # --------------------------------------------------

        candidate_sequence = (
            self.repository
            .next_candidate_sequence(
                strategy_version=(
                    strategy_version
                ),
                ticker=(
                    snapshot.ticker
                ),
                trading_date_et=(
                    snapshot.trading_date_et
                ),
                target_expiry=(
                    snapshot.target_expiry
                ),
                direction=(
                    direction
                ),
            )
        )

        # Initial Candidate creation owns sequence 1 only.
        # Sequence >= 2 belongs to Re-armService.
        if candidate_sequence != 1:
            return CandidateResult(
                created=False,
                reason=(
                    "REARM_REQUIRED_FOR_NEXT_SEQUENCE"
                ),
                direction=direction,
                signal=None,
            )

        # --------------------------------------------------
        # CONFIRMATION WINDOW
        # --------------------------------------------------

        (
            requested_deadline,
            actual_deadline,
        ) = confirmation_deadline(
            candidate_at=(
                candidate_at_et
            ),
            confirmation_minutes=(
                confirmation_minutes
            ),
            trading_date_et=(
                snapshot.trading_date_et
            ),
            calendar=calendar,
        )

        # Safety invariant:
        # actual deadline must never precede Candidate.
        if actual_deadline < candidate_at_et:
            raise RuntimeError(
                "confirmation_deadline cannot be "
                "earlier than candidate_at"
            )

        # --------------------------------------------------
        # CREATE DOMAIN SIGNAL
        # --------------------------------------------------

        signal = Signal(
            strategy_version=(
                strategy_version
            ),

            config_hash=(
                config_hash
            ),

            ticker=(
                snapshot.ticker
            ),

            trading_date_et=(
                snapshot.trading_date_et
            ),

            target_expiry=(
                snapshot.target_expiry
            ),

            direction=(
                direction
            ),

            candidate_sequence=(
                candidate_sequence
            ),

            state=(
                SignalState.CANDIDATE
            ),

            candidate_at=(
                candidate_at_et
            ),

            requested_confirmation_deadline_at=(
                requested_deadline
            ),

            confirmation_deadline_at=(
                actual_deadline
            ),

            confirmed_at=None,

            terminal_at=None,

            terminal_reason=None,

            net_flow_at_candidate=(
                snapshot.net_flow
            ),

            net_flow_at_confirmation=None,

            flow_dedup_level=(
                snapshot.flow_dedup_level
            ),

            # These are Stock/Options market-data
            # provenance fields.
            #
            # UW is the Flow provider, so we must
            # NOT incorrectly place UNUSUAL_WHALES
            # in these fields.
            stock_data_provider=None,
            stock_data_feed=None,

            options_data_provider=None,
            options_data_feed=None,

            theta_convention_status=(
                theta_convention_status
            ),

            scenario_return_enabled=(
                scenario_return_enabled
            ),
        )

        # --------------------------------------------------
        # PERSIST SIGNAL
        # --------------------------------------------------

        created_signal = (
            self.repository.create(
                signal
            )
        )

        # --------------------------------------------------
        # RESULT
        # --------------------------------------------------

        return CandidateResult(
            created=True,
            reason="CANDIDATE_CREATED",
            direction=direction,
            signal=created_signal,
        )