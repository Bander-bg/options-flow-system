from __future__ import annotations

from datetime import date, datetime

from weekly.db.database import (
    database_connection,
    database_transaction,
)
from weekly.domain.enums import (
    GateStatus,
    OptionRight,
)
from weekly.domain.models import (
    SignalFeature,
)


# --------------------------------------------------
# SERIALIZATION HELPERS
# --------------------------------------------------


def _serialize_datetime(
    value: datetime,
) -> str:
    if value.tzinfo is None:
        raise ValueError(
            "datetime must be timezone-aware"
        )

    return value.isoformat()


def _serialize_optional_datetime(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return _serialize_datetime(
        value
    )


def _serialize_optional_date(
    value: date | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _serialize_optional_enum(
    value,
) -> str | None:
    if value is None:
        return None

    return value.value


def _serialize_optional_bool(
    value: bool | None,
) -> int | None:
    if value is None:
        return None

    return 1 if value else 0


# --------------------------------------------------
# PARSING HELPERS
# --------------------------------------------------


def _parse_datetime(
    value: str,
) -> datetime:
    parsed = datetime.fromisoformat(
        value
    )

    if parsed.tzinfo is None:
        raise ValueError(
            "Stored datetime must be "
            "timezone-aware"
        )

    return parsed


def _parse_optional_datetime(
    value: str | None,
) -> datetime | None:
    if value is None:
        return None

    return _parse_datetime(
        value
    )


def _parse_optional_date(
    value: str | None,
) -> date | None:
    if value is None:
        return None

    return date.fromisoformat(
        value
    )


def _parse_optional_gate_status(
    value: str | None,
) -> GateStatus | None:
    if value is None:
        return None

    return GateStatus(
        value
    )


def _parse_optional_option_right(
    value: str | None,
) -> OptionRight | None:
    if value is None:
        return None

    return OptionRight(
        value
    )


def _parse_optional_bool(
    value: int | None,
) -> bool | None:
    if value is None:
        return None

    if value not in (0, 1):
        raise ValueError(
            "Stored boolean must be 0, 1, or NULL"
        )

    return bool(value)


# --------------------------------------------------
# ROW -> DOMAIN MODEL
# --------------------------------------------------


def _row_to_model(
    row,
) -> SignalFeature:
    return SignalFeature(
        signal_id=int(
            row["signal_id"]
        ),

        evaluation_sequence=int(
            row["evaluation_sequence"]
        ),

        captured_at=_parse_datetime(
            row["captured_at"]
        ),

        # --------------------------------------------------
        # FLOW
        # --------------------------------------------------

        flow_net=row["flow_net"],

        flow_threshold=(
            row["flow_threshold"]
        ),

        # --------------------------------------------------
        # VWAP / UNDERLYING
        # --------------------------------------------------

        weekly_vwap=row["weekly_vwap"],

        underlying_price=(
            row["underlying_price"]
        ),

        vwap_status=(
            _parse_optional_gate_status(
                row["vwap_status"]
            )
        ),

        # --------------------------------------------------
        # EFFICIENCY RATIO
        # --------------------------------------------------

        efficiency_ratio=(
            row["efficiency_ratio"]
        ),

        efficiency_ratio_status=(
            _parse_optional_gate_status(
                row[
                    "efficiency_ratio_status"
                ]
            )
        ),

        # --------------------------------------------------
        # EARNINGS
        # --------------------------------------------------

        next_earnings_date=(
            _parse_optional_date(
                row["next_earnings_date"]
            )
        ),

        earnings_event_risk_status=(
            _parse_optional_gate_status(
                row[
                    "earnings_event_risk_status"
                ]
            )
        ),

        # --------------------------------------------------
        # EXPECTED MOVE
        # --------------------------------------------------

        expected_move=(
            row["expected_move"]
        ),

        expected_move_perc=(
            row["expected_move_perc"]
        ),

        # --------------------------------------------------
        # CONTRACT
        # --------------------------------------------------

        selected_contract_symbol=(
            row["selected_contract_symbol"]
        ),

        selected_contract_right=(
            _parse_optional_option_right(
                row[
                    "selected_contract_right"
                ]
            )
        ),

        selected_contract_strike=(
            row["selected_contract_strike"]
        ),

        selected_contract_bid=(
            row["selected_contract_bid"]
        ),

        selected_contract_ask=(
            row["selected_contract_ask"]
        ),

        selected_contract_mark=(
            row["selected_contract_mark"]
        ),

        selected_contract_delta=(
            row["selected_contract_delta"]
        ),

        selected_contract_gamma=(
            row["selected_contract_gamma"]
        ),

        selected_contract_theta=(
            row["selected_contract_theta"]
        ),

        selected_contract_vega=(
            row["selected_contract_vega"]
        ),

        selected_contract_iv=(
            row["selected_contract_iv"]
        ),

        selected_contract_spread_pct=(
            row[
                "selected_contract_spread_pct"
            ]
        ),

        selected_contract_quote_age_seconds=(
            row[
                "selected_contract_quote_age_seconds"
            ]
        ),

        eligible_contract_status=(
            _parse_optional_gate_status(
                row[
                    "eligible_contract_status"
                ]
            )
        ),

        # --------------------------------------------------
        # PRICE ACTION STATUS
        # --------------------------------------------------

        structure_status=(
            _parse_optional_gate_status(
                row["structure_status"]
            )
        ),

        impulse_status=(
            _parse_optional_gate_status(
                row["impulse_status"]
            )
        ),

        participation_status=(
            _parse_optional_gate_status(
                row["participation_status"]
            )
        ),

        price_action_pass_count=(
            row["price_action_pass_count"]
        ),

        price_action_status=(
            _parse_optional_gate_status(
                row["price_action_status"]
            )
        ),

        # --------------------------------------------------
        # PRICE ACTION EVIDENCE
        # --------------------------------------------------

        price_action_bar_at=(
            _parse_optional_datetime(
                row["price_action_bar_at"]
            )
        ),

        trigger_open=(
            row["trigger_open"]
        ),

        trigger_high=(
            row["trigger_high"]
        ),

        trigger_low=(
            row["trigger_low"]
        ),

        trigger_close=(
            row["trigger_close"]
        ),

        trigger_volume=(
            row["trigger_volume"]
        ),

        structure_reference_level=(
            row[
                "structure_reference_level"
            ]
        ),

        structure_break_level=(
            row[
                "structure_break_level"
            ]
        ),

        impulse_body=(
            row["impulse_body"]
        ),

        impulse_median_body=(
            row["impulse_median_body"]
        ),

        impulse_body_atr_ratio=(
            row[
                "impulse_body_atr_ratio"
            ]
        ),

        impulse_engulfing_match=(
            _parse_optional_bool(
                row[
                    "impulse_engulfing_match"
                ]
            )
        ),

        impulse_expansion_match=(
            _parse_optional_bool(
                row[
                    "impulse_expansion_match"
                ]
            )
        ),

        participation_avg_slot_volume=(
            row[
                "participation_avg_slot_volume"
            ]
        ),

        participation_median_slot_volume=(
            row[
                "participation_median_slot_volume"
            ]
        ),

        participation_reference_sessions=(
            row[
                "participation_reference_sessions"
            ]
        ),

        participation_rvol=(
            row["participation_rvol"]
        ),

        # --------------------------------------------------
        # ATR / VOLATILITY
        # --------------------------------------------------

        atr_1h=row["atr_1h"],

        atr_15m=row["atr_15m"],

        iv_percentile=(
            row["iv_percentile"]
        ),

        # --------------------------------------------------
        # QUALITY ATOMIC EVIDENCE
        # --------------------------------------------------

        absolute_flow_strength=(
            row["absolute_flow_strength"]
        ),

        absolute_flow_strength_status=(
            _parse_optional_gate_status(
                row["absolute_flow_strength_status"]
            )
        ),

        relative_flow_strength=(
            row["relative_flow_strength"]
        ),

        relative_flow_strength_status=(
            _parse_optional_gate_status(
                row["relative_flow_strength_status"]
            )
        ),

        vwap_distance_atr=(
            row["vwap_distance_atr"]
        ),

        vwap_distance_atr_status=(
            _parse_optional_gate_status(
                row["vwap_distance_atr_status"]
            )
        ),

        sweep_ratio=(
            row["sweep_ratio"]
        ),

        sweep_ratio_status=(
            _parse_optional_gate_status(
                row["sweep_ratio_status"]
            )
        ),

        opening_evidence=(
            row["opening_evidence"]
        ),

        opening_evidence_status=(
            _parse_optional_gate_status(
                row["opening_evidence_status"]
            )
        ),

        risk_reversal=(
            row["risk_reversal"]
        ),

        risk_reversal_status=(
            _parse_optional_gate_status(
                row["risk_reversal_status"]
            )
        ),

        target_expiry_gex_alignment=(
            _parse_optional_bool(
                row["target_expiry_gex_alignment"]
            )
        ),

        target_expiry_gex_alignment_status=(
            _parse_optional_gate_status(
                row["target_expiry_gex_alignment_status"]
            )
        ),

        negative_gamma_regime=(
            _parse_optional_bool(
                row["negative_gamma_regime"]
            )
        ),

        negative_gamma_regime_status=(
            _parse_optional_gate_status(
                row["negative_gamma_regime_status"]
            )
        ),

        off_exchange_cluster_score=(
            row["off_exchange_cluster_score"]
        ),

        off_exchange_cluster_score_status=(
            _parse_optional_gate_status(
                row["off_exchange_cluster_score_status"]
            )
        ),

        directional_flow_confirmation=(
            row["directional_flow_confirmation"]
        ),

        directional_flow_confirmation_status=(
            _parse_optional_gate_status(
                row["directional_flow_confirmation_status"]
            )
        ),

        iv_percentile_status=(
            _parse_optional_gate_status(
                row["iv_percentile_status"]
            )
        ),

        term_structure_inversion=(
            _parse_optional_bool(
                row["term_structure_inversion"]
            )
        ),

        term_structure_inversion_status=(
            _parse_optional_gate_status(
                row["term_structure_inversion_status"]
            )
        ),

        iv_vs_realized_vol=(
            row["iv_vs_realized_vol"]
        ),

        iv_vs_realized_vol_status=(
            _parse_optional_gate_status(
                row["iv_vs_realized_vol_status"]
            )
        ),

        target_expiry_iv=(
            row["target_expiry_iv"]
        ),

        iv_30d=(
            row["iv_30d"]
        ),

        term_structure_ratio=(
            row["term_structure_ratio"]
        ),

        # --------------------------------------------------
        # SCORING
        # --------------------------------------------------

        base_score=(
            row["base_score"]
        ),

        volatility_penalty=(
            row["volatility_penalty"]
        ),

        final_score=(
            row["final_score"]
        ),

        coverage_points=(
            row["coverage_points"]
        ),

        coverage_pct=(
            row["coverage_pct"]
        ),

        raw_grade=(
            row["raw_grade"]
        ),

        final_grade=(
            row["final_grade"]
        ),

        id=int(
            row["id"]
        ),
    )


# --------------------------------------------------
# REPOSITORY
# --------------------------------------------------


class SignalFeatureRepository:

    def create(
        self,
        feature: SignalFeature,
    ) -> SignalFeature:
        """
        Persist one immutable evaluation snapshot.

        Every evaluation gets a new
        evaluation_sequence.
        """

        values = {
            "signal_id": (
                feature.signal_id
            ),

            "evaluation_sequence": (
                feature.evaluation_sequence
            ),

            "captured_at": (
                _serialize_datetime(
                    feature.captured_at
                )
            ),

            # FLOW
            "flow_net": (
                feature.flow_net
            ),

            "flow_threshold": (
                feature.flow_threshold
            ),

            # VWAP
            "weekly_vwap": (
                feature.weekly_vwap
            ),

            "underlying_price": (
                feature.underlying_price
            ),

            "vwap_status": (
                _serialize_optional_enum(
                    feature.vwap_status
                )
            ),

            # ER
            "efficiency_ratio": (
                feature.efficiency_ratio
            ),

            "efficiency_ratio_status": (
                _serialize_optional_enum(
                    feature
                    .efficiency_ratio_status
                )
            ),

            # EARNINGS
            "next_earnings_date": (
                _serialize_optional_date(
                    feature.next_earnings_date
                )
            ),

            "earnings_event_risk_status": (
                _serialize_optional_enum(
                    feature
                    .earnings_event_risk_status
                )
            ),

            # EXPECTED MOVE
            "expected_move": (
                feature.expected_move
            ),

            "expected_move_perc": (
                feature.expected_move_perc
            ),

            # CONTRACT
            "selected_contract_symbol": (
                feature
                .selected_contract_symbol
            ),

            "selected_contract_right": (
                _serialize_optional_enum(
                    feature
                    .selected_contract_right
                )
            ),

            "selected_contract_strike": (
                feature
                .selected_contract_strike
            ),

            "selected_contract_bid": (
                feature
                .selected_contract_bid
            ),

            "selected_contract_ask": (
                feature
                .selected_contract_ask
            ),

            "selected_contract_mark": (
                feature
                .selected_contract_mark
            ),

            "selected_contract_delta": (
                feature
                .selected_contract_delta
            ),

            "selected_contract_gamma": (
                feature
                .selected_contract_gamma
            ),

            "selected_contract_theta": (
                feature
                .selected_contract_theta
            ),

            "selected_contract_vega": (
                feature
                .selected_contract_vega
            ),

            "selected_contract_iv": (
                feature
                .selected_contract_iv
            ),

            "selected_contract_spread_pct": (
                feature
                .selected_contract_spread_pct
            ),

            "selected_contract_quote_age_seconds": (
                feature
                .selected_contract_quote_age_seconds
            ),

            "eligible_contract_status": (
                _serialize_optional_enum(
                    feature
                    .eligible_contract_status
                )
            ),

            # PRICE ACTION STATUS
            "structure_status": (
                _serialize_optional_enum(
                    feature.structure_status
                )
            ),

            "impulse_status": (
                _serialize_optional_enum(
                    feature.impulse_status
                )
            ),

            "participation_status": (
                _serialize_optional_enum(
                    feature
                    .participation_status
                )
            ),

            "price_action_pass_count": (
                feature
                .price_action_pass_count
            ),

            "price_action_status": (
                _serialize_optional_enum(
                    feature
                    .price_action_status
                )
            ),

            # PRICE ACTION EVIDENCE
            "price_action_bar_at": (
                _serialize_optional_datetime(
                    feature
                    .price_action_bar_at
                )
            ),

            "trigger_open": (
                feature.trigger_open
            ),

            "trigger_high": (
                feature.trigger_high
            ),

            "trigger_low": (
                feature.trigger_low
            ),

            "trigger_close": (
                feature.trigger_close
            ),

            "trigger_volume": (
                feature.trigger_volume
            ),

            "structure_reference_level": (
                feature
                .structure_reference_level
            ),

            "structure_break_level": (
                feature
                .structure_break_level
            ),

            "impulse_body": (
                feature.impulse_body
            ),

            "impulse_median_body": (
                feature
                .impulse_median_body
            ),

            "impulse_body_atr_ratio": (
                feature
                .impulse_body_atr_ratio
            ),

            "impulse_engulfing_match": (
                _serialize_optional_bool(
                    feature
                    .impulse_engulfing_match
                )
            ),

            "impulse_expansion_match": (
                _serialize_optional_bool(
                    feature
                    .impulse_expansion_match
                )
            ),

            "participation_avg_slot_volume": (
                feature
                .participation_avg_slot_volume
            ),

            "participation_median_slot_volume": (
                feature
                .participation_median_slot_volume
            ),

            "participation_reference_sessions": (
                feature
                .participation_reference_sessions
            ),

            "participation_rvol": (
                feature
                .participation_rvol
            ),

            # ATR / VOLATILITY
            "atr_1h": (
                feature.atr_1h
            ),

            "atr_15m": (
                feature.atr_15m
            ),

            "iv_percentile": (
                feature.iv_percentile
            ),

            # QUALITY ATOMIC EVIDENCE
            "absolute_flow_strength": (
                feature.absolute_flow_strength
            ),

            "absolute_flow_strength_status": (
                _serialize_optional_enum(
                    feature.absolute_flow_strength_status
                )
            ),

            "relative_flow_strength": (
                feature.relative_flow_strength
            ),

            "relative_flow_strength_status": (
                _serialize_optional_enum(
                    feature.relative_flow_strength_status
                )
            ),

            "vwap_distance_atr": (
                feature.vwap_distance_atr
            ),

            "vwap_distance_atr_status": (
                _serialize_optional_enum(
                    feature.vwap_distance_atr_status
                )
            ),

            "sweep_ratio": (
                feature.sweep_ratio
            ),

            "sweep_ratio_status": (
                _serialize_optional_enum(
                    feature.sweep_ratio_status
                )
            ),

            "opening_evidence": (
                feature.opening_evidence
            ),

            "opening_evidence_status": (
                _serialize_optional_enum(
                    feature.opening_evidence_status
                )
            ),

            "risk_reversal": (
                feature.risk_reversal
            ),

            "risk_reversal_status": (
                _serialize_optional_enum(
                    feature.risk_reversal_status
                )
            ),

            "target_expiry_gex_alignment": (
                _serialize_optional_bool(
                    feature.target_expiry_gex_alignment
                )
            ),

            "target_expiry_gex_alignment_status": (
                _serialize_optional_enum(
                    feature.target_expiry_gex_alignment_status
                )
            ),

            "negative_gamma_regime": (
                _serialize_optional_bool(
                    feature.negative_gamma_regime
                )
            ),

            "negative_gamma_regime_status": (
                _serialize_optional_enum(
                    feature.negative_gamma_regime_status
                )
            ),

            "off_exchange_cluster_score": (
                feature.off_exchange_cluster_score
            ),

            "off_exchange_cluster_score_status": (
                _serialize_optional_enum(
                    feature.off_exchange_cluster_score_status
                )
            ),

            "directional_flow_confirmation": (
                feature.directional_flow_confirmation
            ),

            "directional_flow_confirmation_status": (
                _serialize_optional_enum(
                    feature.directional_flow_confirmation_status
                )
            ),

            "iv_percentile_status": (
                _serialize_optional_enum(
                    feature.iv_percentile_status
                )
            ),

            "term_structure_inversion": (
                _serialize_optional_bool(
                    feature.term_structure_inversion
                )
            ),

            "term_structure_inversion_status": (
                _serialize_optional_enum(
                    feature.term_structure_inversion_status
                )
            ),

            "iv_vs_realized_vol": (
                feature.iv_vs_realized_vol
            ),

            "iv_vs_realized_vol_status": (
                _serialize_optional_enum(
                    feature.iv_vs_realized_vol_status
                )
            ),

            "target_expiry_iv": (
                feature.target_expiry_iv
            ),

            "iv_30d": (
                feature.iv_30d
            ),

            "term_structure_ratio": (
                feature.term_structure_ratio
            ),

            # SCORING
            "base_score": (
                feature.base_score
            ),

            "volatility_penalty": (
                feature
                .volatility_penalty
            ),

            "final_score": (
                feature.final_score
            ),

            "coverage_points": (
                feature.coverage_points
            ),

            "coverage_pct": (
                feature.coverage_pct
            ),

            "raw_grade": (
                feature.raw_grade
            ),

            "final_grade": (
                feature.final_grade
            ),
        }

        with database_transaction() as conn:

            cursor = conn.execute(
                """
                INSERT INTO signal_features (
                    signal_id,
                    evaluation_sequence,
                    captured_at,

                    flow_net,
                    flow_threshold,

                    weekly_vwap,
                    underlying_price,
                    vwap_status,

                    efficiency_ratio,
                    efficiency_ratio_status,

                    next_earnings_date,
                    earnings_event_risk_status,

                    expected_move,
                    expected_move_perc,

                    selected_contract_symbol,
                    selected_contract_right,
                    selected_contract_strike,

                    selected_contract_bid,
                    selected_contract_ask,
                    selected_contract_mark,

                    selected_contract_delta,
                    selected_contract_gamma,
                    selected_contract_theta,
                    selected_contract_vega,
                    selected_contract_iv,

                    selected_contract_spread_pct,
                    selected_contract_quote_age_seconds,

                    eligible_contract_status,

                    structure_status,
                    impulse_status,
                    participation_status,

                    price_action_pass_count,
                    price_action_status,

                    price_action_bar_at,

                    trigger_open,
                    trigger_high,
                    trigger_low,
                    trigger_close,
                    trigger_volume,

                    structure_reference_level,
                    structure_break_level,

                    impulse_body,
                    impulse_median_body,
                    impulse_body_atr_ratio,
                    impulse_engulfing_match,
                    impulse_expansion_match,

                    participation_avg_slot_volume,
                    participation_median_slot_volume,
                    participation_reference_sessions,
                    participation_rvol,

                    atr_1h,
                    atr_15m,

                    iv_percentile,

                    absolute_flow_strength,
                    absolute_flow_strength_status,

                    relative_flow_strength,
                    relative_flow_strength_status,

                    vwap_distance_atr,
                    vwap_distance_atr_status,

                    sweep_ratio,
                    sweep_ratio_status,

                    opening_evidence,
                    opening_evidence_status,

                    risk_reversal,
                    risk_reversal_status,

                    target_expiry_gex_alignment,
                    target_expiry_gex_alignment_status,

                    negative_gamma_regime,
                    negative_gamma_regime_status,

                    off_exchange_cluster_score,
                    off_exchange_cluster_score_status,

                    directional_flow_confirmation,
                    directional_flow_confirmation_status,

                    iv_percentile_status,

                    term_structure_inversion,
                    term_structure_inversion_status,

                    iv_vs_realized_vol,
                    iv_vs_realized_vol_status,

                    target_expiry_iv,
                    iv_30d,
                    term_structure_ratio,

                    base_score,
                    volatility_penalty,
                    final_score,

                    coverage_points,
                    coverage_pct,

                    raw_grade,
                    final_grade
                )
                VALUES (
                    :signal_id,
                    :evaluation_sequence,
                    :captured_at,

                    :flow_net,
                    :flow_threshold,

                    :weekly_vwap,
                    :underlying_price,
                    :vwap_status,

                    :efficiency_ratio,
                    :efficiency_ratio_status,

                    :next_earnings_date,
                    :earnings_event_risk_status,

                    :expected_move,
                    :expected_move_perc,

                    :selected_contract_symbol,
                    :selected_contract_right,
                    :selected_contract_strike,

                    :selected_contract_bid,
                    :selected_contract_ask,
                    :selected_contract_mark,

                    :selected_contract_delta,
                    :selected_contract_gamma,
                    :selected_contract_theta,
                    :selected_contract_vega,
                    :selected_contract_iv,

                    :selected_contract_spread_pct,
                    :selected_contract_quote_age_seconds,

                    :eligible_contract_status,

                    :structure_status,
                    :impulse_status,
                    :participation_status,

                    :price_action_pass_count,
                    :price_action_status,

                    :price_action_bar_at,

                    :trigger_open,
                    :trigger_high,
                    :trigger_low,
                    :trigger_close,
                    :trigger_volume,

                    :structure_reference_level,
                    :structure_break_level,

                    :impulse_body,
                    :impulse_median_body,
                    :impulse_body_atr_ratio,
                    :impulse_engulfing_match,
                    :impulse_expansion_match,

                    :participation_avg_slot_volume,
                    :participation_median_slot_volume,
                    :participation_reference_sessions,
                    :participation_rvol,

                    :atr_1h,
                    :atr_15m,

                    :iv_percentile,

                    :absolute_flow_strength,
                    :absolute_flow_strength_status,

                    :relative_flow_strength,
                    :relative_flow_strength_status,

                    :vwap_distance_atr,
                    :vwap_distance_atr_status,

                    :sweep_ratio,
                    :sweep_ratio_status,

                    :opening_evidence,
                    :opening_evidence_status,

                    :risk_reversal,
                    :risk_reversal_status,

                    :target_expiry_gex_alignment,
                    :target_expiry_gex_alignment_status,

                    :negative_gamma_regime,
                    :negative_gamma_regime_status,

                    :off_exchange_cluster_score,
                    :off_exchange_cluster_score_status,

                    :directional_flow_confirmation,
                    :directional_flow_confirmation_status,

                    :iv_percentile_status,

                    :term_structure_inversion,
                    :term_structure_inversion_status,

                    :iv_vs_realized_vol,
                    :iv_vs_realized_vol_status,

                    :target_expiry_iv,
                    :iv_30d,
                    :term_structure_ratio,

                    :base_score,
                    :volatility_penalty,
                    :final_score,

                    :coverage_points,
                    :coverage_pct,

                    :raw_grade,
                    :final_grade
                )
                """,
                values,
            )

            feature_id = (
                cursor.lastrowid
            )

        created = self.get_by_id(
            feature_id
        )

        if created is None:
            raise RuntimeError(
                "SignalFeature was inserted "
                "but could not be read back."
            )

        return created

    # --------------------------------------------------
    # GET BY ID
    # --------------------------------------------------

    def get_by_id(
        self,
        feature_id: int,
    ) -> SignalFeature | None:

        if feature_id < 1:
            raise ValueError(
                "feature_id must be >= 1"
            )

        with database_connection() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM signal_features
                WHERE id = ?
                """,
                (
                    feature_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_model(
            row
        )

    # --------------------------------------------------
    # LATEST FOR SIGNAL
    # --------------------------------------------------

    def get_latest_for_signal(
        self,
        signal_id: int,
    ) -> SignalFeature | None:

        if signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        with database_connection() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM signal_features
                WHERE signal_id = ?
                ORDER BY
                    evaluation_sequence DESC,
                    id DESC
                LIMIT 1
                """,
                (
                    signal_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _row_to_model(
            row
        )

    # --------------------------------------------------
    # ALL FOR SIGNAL
    # --------------------------------------------------

    def get_all_for_signal(
        self,
        signal_id: int,
    ) -> list[SignalFeature]:

        if signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        with database_connection() as conn:

            rows = conn.execute(
                """
                SELECT *
                FROM signal_features
                WHERE signal_id = ?
                ORDER BY
                    evaluation_sequence ASC,
                    id ASC
                """,
                (
                    signal_id,
                ),
            ).fetchall()

        return [
            _row_to_model(row)
            for row in rows
        ]
    # --------------------------------------------------
    # NEXT EVALUATION SEQUENCE
    # --------------------------------------------------

    def next_evaluation_sequence(
        self,
        signal_id: int,
    ) -> int:

        if signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        with database_connection() as conn:

            row = conn.execute(
                """
                SELECT
                    COALESCE(
                        MAX(evaluation_sequence),
                        0
                    ) AS max_sequence
                FROM signal_features
                WHERE signal_id = ?
                """,
                (
                    signal_id,
                ),
            ).fetchone()

        return (
            int(
                row["max_sequence"]
            )
            + 1
        )