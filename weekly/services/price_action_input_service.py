from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from weekly.domain.models import SignalFeature
from weekly.services.atr_service import ATR15MinuteBar
from weekly.services.calendar_service import (
    as_et,
    find_session,
    session_open,
)
from weekly.services.price_action_service import PriceBar


class PriceActionInputError(ValueError):
    """Invalid Price Action input-preparation data."""


@dataclass(frozen=True)
class PriceActionInput:
    trigger_bar: PriceBar
    prior_bars: tuple[PriceBar, ...]
    historical_same_slot_volumes: tuple[float, ...]


class PriceActionInputService:
    """
    Prepare runtime inputs for PriceActionEvaluationService.

    Frozen weekly_v1 rules:
    - Trigger must be a completed 15m bar.
    - Trigger starts at/after candidate_at.
    - Trigger ends at/before confirmation_deadline_at.
    - Prior Structure/Impulse bars come from the same
      trading session as the trigger.
    - Participation history uses the same 15m slot from
      previous trading sessions only.
    - Previously evaluated trigger timestamps are skipped.
    """

    def __init__(
        self,
        *,
        participation_lookback_sessions: int,
    ) -> None:
        if participation_lookback_sessions < 1:
            raise PriceActionInputError(
                "participation_lookback_sessions "
                "must be >= 1."
            )

        self.participation_lookback_sessions = (
            participation_lookback_sessions
        )

    def prepare_inputs(
        self,
        *,
        candidate_at: datetime,
        confirmation_deadline_at: datetime,
        calendar,
        fifteen_minute_bars: Sequence[
            ATR15MinuteBar
        ],
        existing_features: Sequence[
            SignalFeature
        ],
    ) -> tuple[PriceActionInput, ...]:
        self._validate_window(
            candidate_at=candidate_at,
            confirmation_deadline_at=(
                confirmation_deadline_at
            ),
        )

        candidate_at_et = as_et(
            candidate_at
        )

        deadline_et = as_et(
            confirmation_deadline_at
        )

        bars = sorted(
            fifteen_minute_bars,
            key=lambda bar: as_et(
                bar.start_at
            ),
        )

        evaluated_bar_ats = {
            as_et(feature.price_action_bar_at)
            for feature in existing_features
            if feature.price_action_bar_at
            is not None
        }

        prepared: list[
            PriceActionInput
        ] = []

        for trigger in bars:
            trigger_start = as_et(
                trigger.start_at
            )

            trigger_end = as_et(
                trigger.end_at
            )

            if (
                trigger_start
                < candidate_at_et
            ):
                continue

            if (
                trigger_end
                > deadline_et
            ):
                continue

            if (
                trigger_end
                in evaluated_bar_ats
            ):
                continue

            trigger_session = find_session(
                trading_date_et=(
                    trigger_start.date()
                ),
                calendar=calendar,
            )

            if trigger_session is None:
                raise PriceActionInputError(
                    "No calendar session found "
                    "for trigger bar."
                )

            current_open = session_open(
                trigger_session
            )

            slot_delta = (
                trigger_start
                - current_open
            )

            slot_seconds = (
                slot_delta.total_seconds()
            )

            if (
                slot_seconds < 0
                or slot_seconds % (15 * 60)
                != 0
            ):
                raise PriceActionInputError(
                    "Trigger bar is not aligned "
                    "to a 15-minute session slot."
                )

            slot_index = int(
                slot_seconds
                // (15 * 60)
            )

            prior_bars = (
                self._same_session_prior_bars(
                    trigger=trigger,
                    bars=bars,
                )
            )

            historical_volumes = (
                self._historical_same_slot_volumes(
                    trigger_start=trigger_start,
                    slot_index=slot_index,
                    calendar=calendar,
                    bars=bars,
                )
            )

            prepared.append(
                PriceActionInput(
                    trigger_bar=(
                        self._to_price_bar(
                            trigger
                        )
                    ),
                    prior_bars=tuple(
                        self._to_price_bar(
                            bar
                        )
                        for bar in prior_bars
                    ),
                    historical_same_slot_volumes=(
                        historical_volumes
                    ),
                )
            )

        return tuple(
            prepared
        )

    def prepare_rearm_inputs(
        self,
        *,
        confirmed_at: datetime,
        as_of: datetime,
        calendar,
        fifteen_minute_bars: Sequence[
            ATR15MinuteBar
        ],
    ) -> tuple[PriceActionInput, ...]:
        """
        Prepare fresh completed 15m bars for ReArm.

        Frozen weekly_v1 ReArm rule:
        - trigger bar CLOSE must be strictly after
          previous confirmed_at.
        - trigger must already be completed by as_of.

        This method does NOT:
        - create a new confirmation window,
        - persist SignalFeature snapshots,
        - create Candidate #2+,
        - transition Signal state.
        """

        if confirmed_at.tzinfo is None:
            raise PriceActionInputError(
                "confirmed_at must be timezone-aware."
            )

        if as_of.tzinfo is None:
            raise PriceActionInputError(
                "as_of must be timezone-aware."
            )

        if as_of < confirmed_at:
            raise PriceActionInputError(
                "as_of cannot precede confirmed_at."
            )

        confirmed_at_et = as_et(
            confirmed_at
        )

        as_of_et = as_et(
            as_of
        )

        bars = sorted(
            fifteen_minute_bars,
            key=lambda bar: as_et(
                bar.start_at
            ),
        )

        prepared: list[
            PriceActionInput
        ] = []

        for trigger in bars:
            trigger_start = as_et(
                trigger.start_at
            )

            trigger_end = as_et(
                trigger.end_at
            )

            if trigger_end <= confirmed_at_et:
                continue

            if trigger_end > as_of_et:
                continue

            trigger_session = find_session(
                trading_date_et=(
                    trigger_start.date()
                ),
                calendar=calendar,
            )

            if trigger_session is None:
                raise PriceActionInputError(
                    "No calendar session found "
                    "for ReArm trigger bar."
                )

            current_open = session_open(
                trigger_session
            )

            slot_delta = (
                trigger_start
                - current_open
            )

            slot_seconds = (
                slot_delta.total_seconds()
            )

            if (
                slot_seconds < 0
                or slot_seconds % (15 * 60)
                != 0
            ):
                raise PriceActionInputError(
                    "ReArm trigger bar is not "
                    "aligned to a 15-minute "
                    "session slot."
                )

            slot_index = int(
                slot_seconds
                // (15 * 60)
            )

            prior_bars = (
                self._same_session_prior_bars(
                    trigger=trigger,
                    bars=bars,
                )
            )

            historical_volumes = (
                self._historical_same_slot_volumes(
                    trigger_start=trigger_start,
                    slot_index=slot_index,
                    calendar=calendar,
                    bars=bars,
                )
            )

            prepared.append(
                PriceActionInput(
                    trigger_bar=(
                        self._to_price_bar(
                            trigger
                        )
                    ),
                    prior_bars=tuple(
                        self._to_price_bar(
                            bar
                        )
                        for bar in prior_bars
                    ),
                    historical_same_slot_volumes=(
                        historical_volumes
                    ),
                )
            )

        return tuple(
            prepared
        )

    @staticmethod
    def _same_session_prior_bars(
        *,
        trigger: ATR15MinuteBar,
        bars: Sequence[ATR15MinuteBar],
    ) -> tuple[ATR15MinuteBar, ...]:
        trigger_start = as_et(
            trigger.start_at
        )

        trigger_date = (
            trigger_start.date()
        )

        prior = [
            bar
            for bar in bars
            if (
                as_et(
                    bar.start_at
                ).date()
                == trigger_date
                and as_et(
                    bar.end_at
                )
                <= trigger_start
            )
        ]

        prior.sort(
            key=lambda bar: as_et(
                bar.start_at
            )
        )

        return tuple(
            prior
        )

    def _historical_same_slot_volumes(
        self,
        *,
        trigger_start: datetime,
        slot_index: int,
        calendar,
        bars: Sequence[ATR15MinuteBar],
    ) -> tuple[float, ...]:
        previous_sessions = [
            session
            for session in calendar
            if session.date
            < trigger_start.date()
        ]

        previous_sessions.sort(
            key=lambda session: (
                session.date
            )
        )

        volumes: list[float] = []

        for session in previous_sessions:
            expected_start = (
                session_open(session)
                + timedelta(
                    minutes=(
                        slot_index * 15
                    )
                )
            )

            matching = [
                bar
                for bar in bars
                if (
                    as_et(
                        bar.start_at
                    )
                    == expected_start
                )
            ]

            if len(matching) > 1:
                raise PriceActionInputError(
                    "Duplicate 15-minute bars "
                    "found for the same "
                    "historical session slot."
                )

            if not matching:
                continue

            volume = float(
                matching[0].volume
            )

            if volume < 0:
                raise PriceActionInputError(
                    "Historical slot volume "
                    "cannot be negative."
                )

            volumes.append(
                volume
            )

        return tuple(
            volumes[
                -self
                .participation_lookback_sessions:
            ]
        )

    @staticmethod
    def _to_price_bar(
        bar: ATR15MinuteBar,
    ) -> PriceBar:
        return PriceBar(
            start_at=bar.start_at,
            end_at=bar.end_at,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
        )

    @staticmethod
    def _validate_window(
        *,
        candidate_at: datetime,
        confirmation_deadline_at: datetime,
    ) -> None:
        if candidate_at.tzinfo is None:
            raise PriceActionInputError(
                "candidate_at must be "
                "timezone-aware."
            )

        if (
            confirmation_deadline_at.tzinfo
            is None
        ):
            raise PriceActionInputError(
                "confirmation_deadline_at "
                "must be timezone-aware."
            )

        if (
            confirmation_deadline_at
            < candidate_at
        ):
            raise PriceActionInputError(
                "confirmation_deadline_at "
                "cannot precede candidate_at."
            )
