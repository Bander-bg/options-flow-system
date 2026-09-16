from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Any, Sequence

from weekly.domain.enums import (
    Direction,
    GateStatus,
)


class PriceActionError(ValueError):
    """Raised when Price Action inputs/configuration are invalid."""


@dataclass(frozen=True)
class PriceBar:
    """
    One completed 15-minute RTH price bar.

    start_at:
        Start timestamp of the 15m bar.

    end_at:
        End timestamp of the 15m bar.
    """

    start_at: datetime
    end_at: datetime

    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.start_at.tzinfo is None:
            raise PriceActionError(
                "PriceBar.start_at must be timezone-aware."
            )

        if self.end_at.tzinfo is None:
            raise PriceActionError(
                "PriceBar.end_at must be timezone-aware."
            )

        if self.end_at <= self.start_at:
            raise PriceActionError(
                "PriceBar.end_at must be after start_at."
            )

        if (
            self.end_at - self.start_at
            != timedelta(minutes=15)
        ):
            raise PriceActionError(
                "PriceBar must represent exactly 15 minutes."
            )

        for name, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
            ("volume", self.volume),
        ):
            if value < 0:
                raise PriceActionError(
                    f"PriceBar.{name} cannot be negative."
                )

        if self.high < self.low:
            raise PriceActionError(
                "PriceBar.high cannot be below low."
            )

        if not (
            self.low
            <= self.open
            <= self.high
        ):
            raise PriceActionError(
                "PriceBar.open must be within high/low."
            )

        if not (
            self.low
            <= self.close
            <= self.high
        ):
            raise PriceActionError(
                "PriceBar.close must be within high/low."
            )


@dataclass(frozen=True)
class PriceActionSettings:
    confirmation_minutes: int

    structure_lookback_bars: int
    structure_atr_break: float

    impulse_body_lookback_bars: int
    impulse_body_expansion_multiplier: float
    impulse_body_min_atr: float

    participation_rvol_min: float
    participation_rvol_lookback_sessions: int

    def __post_init__(self) -> None:
        if self.confirmation_minutes <= 0:
            raise PriceActionError(
                "confirmation_minutes must be > 0."
            )

        if self.structure_lookback_bars < 1:
            raise PriceActionError(
                "structure_lookback_bars must be >= 1."
            )

        if self.structure_atr_break < 0:
            raise PriceActionError(
                "structure_atr_break cannot be negative."
            )

        if self.impulse_body_lookback_bars < 1:
            raise PriceActionError(
                "impulse_body_lookback_bars must be >= 1."
            )

        if (
            self.impulse_body_expansion_multiplier
            <= 0
        ):
            raise PriceActionError(
                "impulse_body_expansion_multiplier "
                "must be > 0."
            )

        if self.impulse_body_min_atr < 0:
            raise PriceActionError(
                "impulse_body_min_atr cannot be negative."
            )

        if self.participation_rvol_min <= 0:
            raise PriceActionError(
                "participation_rvol_min must be > 0."
            )

        if (
            self.participation_rvol_lookback_sessions
            < 1
        ):
            raise PriceActionError(
                "participation_rvol_lookback_sessions "
                "must be >= 1."
            )


@dataclass(frozen=True)
class PriceActionResult:
    price_action_bar_at: datetime

    structure_status: GateStatus
    impulse_status: GateStatus
    participation_status: GateStatus

    price_action_pass_count: int
    price_action_status: GateStatus

    trigger_open: float
    trigger_high: float
    trigger_low: float
    trigger_close: float
    trigger_volume: float

    structure_reference_level: float | None
    structure_break_level: float | None

    impulse_body: float
    impulse_median_body: float | None
    impulse_body_atr_ratio: float | None

    impulse_engulfing_match: bool | None
    impulse_expansion_match: bool | None

    participation_median_slot_volume: float | None
    participation_reference_sessions: int
    participation_rvol: float | None


class PriceActionService:
    """
    Pure weekly_v1 Price Action evaluation logic.

    This class does not call Alpaca, Unusual Whales,
    SQLite, or any external provider.

    It evaluates ONE completed 15-minute trigger bar.
    """

    def __init__(
        self,
        settings: PriceActionSettings,
    ) -> None:
        self.settings = settings

    @classmethod
    def from_weekly_config(
        cls,
        config: dict[str, Any],
    ) -> "PriceActionService":
        """
        Build the service from weekly_config.yaml.

        Expected structure:

        price_action:
          price_action_confirmation_minutes: 30

          structure:
            lookback_bars: 8
            atr_break: 0.1

          impulse:
            body_lookback_bars: 10
            body_expansion_multiplier: 1.5
            body_min_atr: 0.5

          participation:
            rvol_min: 1.5
            rvol_lookback_sessions: 20
        """

        try:
            pa = config["price_action"]

            structure = pa["structure"]
            impulse = pa["impulse"]
            participation = pa["participation"]

            settings = PriceActionSettings(
                confirmation_minutes=int(
                    pa[
                        "price_action_confirmation_minutes"
                    ]
                ),
                structure_lookback_bars=int(
                    structure["lookback_bars"]
                ),
                structure_atr_break=float(
                    structure["atr_break"]
                ),
                impulse_body_lookback_bars=int(
                    impulse["body_lookback_bars"]
                ),
                impulse_body_expansion_multiplier=float(
                    impulse[
                        "body_expansion_multiplier"
                    ]
                ),
                impulse_body_min_atr=float(
                    impulse["body_min_atr"]
                ),
                participation_rvol_min=float(
                    participation["rvol_min"]
                ),
                participation_rvol_lookback_sessions=int(
                    participation[
                        "rvol_lookback_sessions"
                    ]
                ),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PriceActionError(
                "Invalid weekly_v1 price_action config."
            ) from exc

        return cls(settings)

    def evaluate_bar(
        self,
        *,
        direction: Direction,
        candidate_at: datetime,
        confirmation_deadline_at: datetime,
        trigger_bar: PriceBar,
        prior_bars: Sequence[PriceBar],
        atr_15m: float | None,
        historical_same_slot_volumes: Sequence[
            float
        ],
    ) -> PriceActionResult:
        """
        Evaluate one completed 15m bar.

        Fresh-bar rule:
        - trigger bar must start at or after candidate_at
        - trigger bar must finish no later than the
          confirmation deadline

        prior_bars:
        Completed 15m bars BEFORE trigger_bar,
        oldest -> newest.

        historical_same_slot_volumes:
        Volumes from the SAME 15m time slot across
        previous trading sessions, oldest -> newest.
        """

        self._validate_evaluation_window(
            candidate_at=candidate_at,
            confirmation_deadline_at=(
                confirmation_deadline_at
            ),
            trigger_bar=trigger_bar,
        )

        self._validate_prior_bars(
            trigger_bar=trigger_bar,
            prior_bars=prior_bars,
        )

        self._validate_slot_volumes(
            historical_same_slot_volumes
        )

        (
            structure_status,
            structure_reference_level,
            structure_break_level,
        ) = self._evaluate_structure(
            direction=direction,
            trigger_bar=trigger_bar,
            prior_bars=prior_bars,
            atr_15m=atr_15m,
        )

        (
            impulse_status,
            impulse_body,
            impulse_median_body,
            impulse_body_atr_ratio,
            impulse_engulfing_match,
            impulse_expansion_match,
        ) = self._evaluate_impulse(
            direction=direction,
            trigger_bar=trigger_bar,
            prior_bars=prior_bars,
            atr_15m=atr_15m,
        )

        (
            participation_status,
            participation_median_slot_volume,
            participation_reference_sessions,
            participation_rvol,
        ) = self._evaluate_participation(
            trigger_bar=trigger_bar,
            historical_same_slot_volumes=(
                historical_same_slot_volumes
            ),
        )

        statuses = (
            structure_status,
            impulse_status,
            participation_status,
        )

        pass_count = sum(
            status == GateStatus.PASS
            for status in statuses
        )

        fail_count = sum(
            status == GateStatus.FAIL
            for status in statuses
        )

        if pass_count >= 2:
            overall_status = GateStatus.PASS

        elif fail_count >= 2:
            overall_status = GateStatus.FAIL

        else:
            overall_status = GateStatus.UNKNOWN

        return PriceActionResult(
            price_action_bar_at=trigger_bar.end_at,

            structure_status=structure_status,
            impulse_status=impulse_status,
            participation_status=(
                participation_status
            ),

            price_action_pass_count=pass_count,
            price_action_status=overall_status,

            trigger_open=trigger_bar.open,
            trigger_high=trigger_bar.high,
            trigger_low=trigger_bar.low,
            trigger_close=trigger_bar.close,
            trigger_volume=trigger_bar.volume,

            structure_reference_level=(
                structure_reference_level
            ),
            structure_break_level=(
                structure_break_level
            ),

            impulse_body=impulse_body,
            impulse_median_body=(
                impulse_median_body
            ),
            impulse_body_atr_ratio=(
                impulse_body_atr_ratio
            ),

            impulse_engulfing_match=(
                impulse_engulfing_match
            ),
            impulse_expansion_match=(
                impulse_expansion_match
            ),

            participation_median_slot_volume=(
                participation_median_slot_volume
            ),
            participation_reference_sessions=(
                participation_reference_sessions
            ),
            participation_rvol=(
                participation_rvol
            ),
        )

    # ==================================================
    # STRUCTURE
    # ==================================================

    def _evaluate_structure(
        self,
        *,
        direction: Direction,
        trigger_bar: PriceBar,
        prior_bars: Sequence[PriceBar],
        atr_15m: float | None,
    ) -> tuple[
        GateStatus,
        float | None,
        float | None,
    ]:
        lookback = (
            self.settings.structure_lookback_bars
        )

        if len(prior_bars) < lookback:
            return (
                GateStatus.UNKNOWN,
                None,
                None,
            )

        if (
            atr_15m is None
            or atr_15m <= 0
        ):
            return (
                GateStatus.UNKNOWN,
                None,
                None,
            )

        recent = prior_bars[-lookback:]

        buffer = (
            atr_15m
            * self.settings.structure_atr_break
        )

        if direction == Direction.BULLISH:
            reference_level = max(
                bar.high
                for bar in recent
            )

            break_level = (
                reference_level
                + buffer
            )

            passed = (
                trigger_bar.close
                >= break_level
            )

        elif direction == Direction.BEARISH:
            reference_level = min(
                bar.low
                for bar in recent
            )

            break_level = (
                reference_level
                - buffer
            )

            passed = (
                trigger_bar.close
                <= break_level
            )

        else:
            raise PriceActionError(
                f"Unsupported direction: {direction!r}"
            )

        return (
            (
                GateStatus.PASS
                if passed
                else GateStatus.FAIL
            ),
            reference_level,
            break_level,
        )

    # ==================================================
    # IMPULSE
    # ==================================================

    def _evaluate_impulse(
        self,
        *,
        direction: Direction,
        trigger_bar: PriceBar,
        prior_bars: Sequence[PriceBar],
        atr_15m: float | None,
    ) -> tuple[
        GateStatus,
        float,
        float | None,
        float | None,
        bool | None,
        bool | None,
    ]:
        body = abs(
            trigger_bar.close
            - trigger_bar.open
        )

        atr_ratio: float | None = None

        if (
            atr_15m is not None
            and atr_15m > 0
        ):
            atr_ratio = body / atr_15m

        engulfing_match: bool | None = None

        if prior_bars:
            previous = prior_bars[-1]

            engulfing_match = (
                self._is_directional_engulfing(
                    direction=direction,
                    current=trigger_bar,
                    previous=previous,
                )
            )

        body_lookback = (
            self.settings
            .impulse_body_lookback_bars
        )

        median_body: float | None = None
        expansion_match: bool | None = None

        if (
            len(prior_bars) >= body_lookback
            and atr_15m is not None
            and atr_15m > 0
        ):
            recent = prior_bars[
                -body_lookback:
            ]

            bodies = [
                abs(
                    bar.close
                    - bar.open
                )
                for bar in recent
            ]

            median_body = float(
                median(bodies)
            )

            directional = (
                self._bar_matches_direction(
                    direction=direction,
                    bar=trigger_bar,
                )
            )

            expansion_threshold = (
                median_body
                * self.settings
                .impulse_body_expansion_multiplier
            )

            minimum_atr_body = (
                atr_15m
                * self.settings
                .impulse_body_min_atr
            )

            expansion_match = (
                directional
                and body >= expansion_threshold
                and body >= minimum_atr_body
            )

        if engulfing_match is True:
            status = GateStatus.PASS

        elif expansion_match is True:
            status = GateStatus.PASS

        elif (
            engulfing_match is not None
            and expansion_match is not None
        ):
            status = GateStatus.FAIL

        else:
            status = GateStatus.UNKNOWN

        return (
            status,
            body,
            median_body,
            atr_ratio,
            engulfing_match,
            expansion_match,
        )

    def _is_directional_engulfing(
        self,
        *,
        direction: Direction,
        current: PriceBar,
        previous: PriceBar,
    ) -> bool:
        """
        Conservative body-engulfing definition.

        Bullish:
        - previous candle bearish
        - current candle bullish
        - current real body fully engulfs previous body

        Bearish:
        - previous candle bullish
        - current candle bearish
        - current real body fully engulfs previous body
        """

        if direction == Direction.BULLISH:
            previous_opposite = (
                previous.close
                < previous.open
            )

            current_directional = (
                current.close
                > current.open
            )

            body_engulfs = (
                current.open
                <= previous.close
                and current.close
                >= previous.open
            )

        elif direction == Direction.BEARISH:
            previous_opposite = (
                previous.close
                > previous.open
            )

            current_directional = (
                current.close
                < current.open
            )

            body_engulfs = (
                current.open
                >= previous.close
                and current.close
                <= previous.open
            )

        else:
            raise PriceActionError(
                f"Unsupported direction: {direction!r}"
            )

        return (
            previous_opposite
            and current_directional
            and body_engulfs
        )

    # ==================================================
    # PARTICIPATION
    # ==================================================

    def _evaluate_participation(
        self,
        *,
        trigger_bar: PriceBar,
        historical_same_slot_volumes: Sequence[
            float
        ],
    ) -> tuple[
        GateStatus,
        float | None,
        int,
        float | None,
    ]:
        required = (
            self.settings
            .participation_rvol_lookback_sessions
        )

        available = len(
            historical_same_slot_volumes
        )

        reference_sessions = min(
            available,
            required,
        )

        if available < required:
            return (
                GateStatus.UNKNOWN,
                None,
                reference_sessions,
                None,
            )

        reference = list(
            historical_same_slot_volumes[
                -required:
            ]
        )

        median_volume = float(
            median(reference)
        )

        if median_volume <= 0:
            return (
                GateStatus.UNKNOWN,
                median_volume,
                required,
                None,
            )

        rvol = (
            trigger_bar.volume
            / median_volume
        )

        status = (
            GateStatus.PASS
            if (
                rvol
                >= self.settings
                .participation_rvol_min
            )
            else GateStatus.FAIL
        )

        return (
            status,
            median_volume,
            required,
            rvol,
        )

    # ==================================================
    # HELPERS / VALIDATION
    # ==================================================

    def _bar_matches_direction(
        self,
        *,
        direction: Direction,
        bar: PriceBar,
    ) -> bool:
        if direction == Direction.BULLISH:
            return bar.close > bar.open

        if direction == Direction.BEARISH:
            return bar.close < bar.open

        raise PriceActionError(
            f"Unsupported direction: {direction!r}"
        )

    def _validate_evaluation_window(
        self,
        *,
        candidate_at: datetime,
        confirmation_deadline_at: datetime,
        trigger_bar: PriceBar,
    ) -> None:
        if candidate_at.tzinfo is None:
            raise PriceActionError(
                "candidate_at must be timezone-aware."
            )

        if (
            confirmation_deadline_at.tzinfo
            is None
        ):
            raise PriceActionError(
                "confirmation_deadline_at "
                "must be timezone-aware."
            )

        if (
            confirmation_deadline_at
            < candidate_at
        ):
            raise PriceActionError(
                "confirmation_deadline_at cannot "
                "be before candidate_at."
            )

        if trigger_bar.start_at < candidate_at:
            raise PriceActionError(
                "Trigger bar must start at or after "
                "candidate_at."
            )

        if (
            trigger_bar.end_at
            > confirmation_deadline_at
        ):
            raise PriceActionError(
                "Trigger bar ends after the "
                "confirmation deadline."
            )

    def _validate_prior_bars(
        self,
        *,
        trigger_bar: PriceBar,
        prior_bars: Sequence[PriceBar],
    ) -> None:
        previous_end: datetime | None = None

        for bar in prior_bars:
            if bar.end_at > trigger_bar.start_at:
                raise PriceActionError(
                    "prior_bars must finish before "
                    "the trigger bar starts."
                )

            if (
                previous_end is not None
                and bar.start_at < previous_end
            ):
                raise PriceActionError(
                    "prior_bars must be ordered "
                    "oldest to newest."
                )

            previous_end = bar.end_at

    def _validate_slot_volumes(
        self,
        volumes: Sequence[float],
    ) -> None:
        for value in volumes:
            if value < 0:
                raise PriceActionError(
                    "Historical slot volumes "
                    "cannot be negative."
                )