from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "weekly_config.yaml"


def get_weekly_config_path() -> Path:
    """
    Resolve the active weekly_v1 config path.

    OPTIONS_FLOW_CONFIG_PATH is a deployment-only
    override for persistent storage environments.

    When unset, local behavior remains unchanged.

    On first deployment, the tracked weekly_config.yaml
    is copied to the persistent path if needed.
    """

    env_path = os.getenv("OPTIONS_FLOW_CONFIG_PATH")

    if not env_path:
        return DEFAULT_CONFIG_PATH

    persistent_path = Path(
        env_path
    ).expanduser().resolve()

    if not persistent_path.exists():
        persistent_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            DEFAULT_CONFIG_PATH,
            persistent_path,
        )

    return persistent_path


class ConfigError(Exception):
    """Raised when weekly_v1 configuration is missing or invalid."""


def _require(
    config: dict[str, Any],
    path: str,
) -> Any:
    """
    Read a nested value using dot notation.

    Example:
        _require(config, "contract_selector.delta_min")
    """
    current: Any = config

    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ConfigError(f"Missing required config value: {path}")

        current = current[part]

    return current


def _require_number(
    config: dict[str, Any],
    path: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    allow_equal_min: bool = True,
    allow_equal_max: bool = True,
) -> float:
    value = _require(config, path)

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(
            f"{path} must be a number. Current value: {value!r}"
        )

    numeric = float(value)

    if minimum is not None:
        if allow_equal_min:
            invalid = numeric < minimum
        else:
            invalid = numeric <= minimum

        if invalid:
            operator = ">=" if allow_equal_min else ">"
            raise ConfigError(
                f"{path} must be {operator} {minimum}. "
                f"Current value: {numeric}"
            )

    if maximum is not None:
        if allow_equal_max:
            invalid = numeric > maximum
        else:
            invalid = numeric >= maximum

        if invalid:
            operator = "<=" if allow_equal_max else "<"
            raise ConfigError(
                f"{path} must be {operator} {maximum}. "
                f"Current value: {numeric}"
            )

    return numeric


def _require_int(
    config: dict[str, Any],
    path: str,
    *,
    minimum: int | None = None,
) -> int:
    value = _require(config, path)

    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            f"{path} must be an integer. Current value: {value!r}"
        )

    if minimum is not None and value < minimum:
        raise ConfigError(
            f"{path} must be >= {minimum}. Current value: {value}"
        )

    return value


def _require_bool(
    config: dict[str, Any],
    path: str,
) -> bool:
    value = _require(config, path)

    if not isinstance(value, bool):
        raise ConfigError(
            f"{path} must be true/false. Current value: {value!r}"
        )

    return value


def _require_string(
    config: dict[str, Any],
    path: str,
) -> str:
    value = _require(config, path)

    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"{path} must be a non-empty string."
        )

    return value.strip()


def _validate_strategy(config: dict[str, Any]) -> None:
    version = _require_string(
        config,
        "strategy.strategy_version",
    )

    if version != "weekly_v1":
        raise ConfigError(
            "strategy.strategy_version must be exactly 'weekly_v1'. "
            f"Current value: {version!r}"
        )


def _validate_universe(config: dict[str, Any]) -> None:
    tickers = _require(config, "universe.tickers")

    if not isinstance(tickers, list) or not tickers:
        raise ConfigError(
            "universe.tickers must contain at least one ticker."
        )

    seen: set[str] = set()

    for ticker in tickers:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ConfigError(
                "Every ticker in universe.tickers must be a non-empty string."
            )

        normalized = ticker.strip().upper()

        if ticker != normalized:
            raise ConfigError(
                f"Ticker {ticker!r} must be uppercase: {normalized!r}"
            )

        if normalized in seen:
            raise ConfigError(
                f"Duplicate ticker in universe.tickers: {normalized}"
            )

        seen.add(normalized)


def _validate_market(config: dict[str, Any]) -> None:
    timezone = _require_string(
        config,
        "market.timezone",
    )

    if timezone != "America/New_York":
        raise ConfigError(
            "weekly_v1 market.timezone must be 'America/New_York'."
        )

    _require_bool(
        config,
        "market.regular_hours_only",
    )

    feed = _require_string(
        config,
        "market.stock_data_feed_preferred",
    ).lower()

    if feed not in {"sip", "iex"}:
        raise ConfigError(
            "market.stock_data_feed_preferred must be 'sip' or 'iex'."
        )


    option_feed = _require_string(
        config,
        "market.option_data_feed_preferred",
    ).lower()

    if option_feed not in {"opra", "indicative"}:
        raise ConfigError(
            "market.option_data_feed_preferred must be "
            "'opra' or 'indicative'."
        )


def _validate_target_expiry(config: dict[str, Any]) -> None:
    minimum = _require_int(
        config,
        "target_expiry.min_sessions",
        minimum=1,
    )

    maximum = _require_int(
        config,
        "target_expiry.max_sessions",
        minimum=1,
    )

    if minimum != 3:
        raise ConfigError(
            "weekly_v1 target_expiry.min_sessions must currently be 3."
        )

    if maximum != 7:
        raise ConfigError(
            "weekly_v1 target_expiry.max_sessions must currently be 7."
        )

    if minimum > maximum:
        raise ConfigError(
            "target_expiry.min_sessions cannot exceed max_sessions."
        )


def _validate_scanner(config: dict[str, Any]) -> None:
    _require_int(
        config,
        "scanner.scan_interval_minutes",
        minimum=1,
    )

    _require_int(
        config,
        "scanner.deadline_processing_grace_polls",
        minimum=0,
    )


def _validate_flow(config: dict[str, Any]) -> None:
    _require_number(
        config,
        "flow.flow_threshold",
        minimum=0,
        allow_equal_min=False,
    )

    _require_number(
        config,
        "flow.rearm_aligned_flow_min",
        minimum=0,
        allow_equal_min=False,
    )

    _require_int(
        config,
        "flow.cooldown_minutes",
        minimum=0,
    )

    _require_number(
        config,
        "flow.flow_accel_z",
        minimum=0,
        allow_equal_min=False,
    )

    _require_number(
        config,
        "flow.flow_accel_floor",
        minimum=0,
        allow_equal_min=False,
    )

    _require_int(
        config,
        "flow.flow_accel_lookback_observations",
        minimum=1,
    )


def _validate_price_action(config: dict[str, Any]) -> None:
    _require_int(
        config,
        "price_action.price_action_confirmation_minutes",
        minimum=1,
    )

    _require_int(
        config,
        "price_action.structure.lookback_bars",
        minimum=1,
    )

    _require_number(
        config,
        "price_action.structure.atr_break",
        minimum=0,
    )

    _require_int(
        config,
        "price_action.impulse.body_lookback_bars",
        minimum=1,
    )

    _require_number(
        config,
        "price_action.impulse.body_expansion_multiplier",
        minimum=0,
        allow_equal_min=False,
    )

    _require_number(
        config,
        "price_action.impulse.body_min_atr",
        minimum=0,
        allow_equal_min=False,
    )

    _require_number(
        config,
        "price_action.participation.rvol_min",
        minimum=0,
        allow_equal_min=False,
    )

    _require_int(
        config,
        "price_action.participation.rvol_lookback_sessions",
        minimum=1,
    )


def _validate_regime(config: dict[str, Any]) -> None:
    _require_number(
        config,
        "regime.efficiency_ratio_min",
        minimum=0,
        maximum=1,
    )

    _require_int(
        config,
        "regime.min_er_bars",
        minimum=2,
    )

    _require_int(
        config,
        "regime.atr_1h_period",
        minimum=1,
    )

    _require_int(
        config,
        "regime.atr_15m_period",
        minimum=1,
    )


def _validate_contract_selector(
    config: dict[str, Any],
    *,
    require_runtime_ready: bool,
) -> None:
    delta_min = _require_number(
        config,
        "contract_selector.delta_min",
        minimum=0,
        maximum=1,
    )

    delta_max = _require_number(
        config,
        "contract_selector.delta_max",
        minimum=0,
        maximum=1,
    )

    if delta_min > delta_max:
        raise ConfigError(
            "contract_selector.delta_min cannot exceed delta_max."
        )

    _require_number(
        config,
        "contract_selector.max_spread_pct",
        minimum=0,
        maximum=1,
        allow_equal_min=False,
    )

    _require_int(
        config,
        "contract_selector.max_option_quote_age_seconds",
        minimum=1,
    )

    contract_size = _require_int(
        config,
        "contract_selector.standard_contract_size",
        minimum=1,
    )

    if contract_size != 100:
        raise ConfigError(
            "weekly_v1 currently supports standard contract_size=100 only."
        )

    _require_bool(
        config,
        "contract_selector.require_standard_contract",
    )

    _require_bool(
        config,
        "contract_selector.require_tradable_contract",
    )

    max_budget = _require(
        config,
        "contract_selector.max_budget",
    )

    if max_budget is None:
        if require_runtime_ready:
            raise ConfigError(
                "contract_selector.max_budget is REQUIRED before starting "
                "weekly_v1 Scanner. Set a positive numeric value in "
                "weekly_config.yaml."
            )
    else:
        if isinstance(max_budget, bool) or not isinstance(
            max_budget,
            (int, float),
        ):
            raise ConfigError(
                "contract_selector.max_budget must be a positive number."
            )

        if float(max_budget) <= 0:
            raise ConfigError(
                "contract_selector.max_budget must be greater than zero."
            )

    _require_int(
        config,
        "contract_selector.scenario.horizon_days",
        minimum=1,
    )

    _require_number(
        config,
        "contract_selector.scenario.move_fraction",
        minimum=0,
        allow_equal_min=False,
    )

    _require_number(
        config,
        "contract_selector.shadow_target_abs_delta",
        minimum=0,
        maximum=1,
    )


def _validate_quality_weights(config: dict[str, Any]) -> None:
    quality_weight_paths = [
        "quality_scoring.absolute_flow_strength.weight",
        "quality_scoring.relative_flow_strength.weight",
        "quality_scoring.vwap_distance_atr.weight",
        "quality_scoring.efficiency_ratio_strength.weight",
        "quality_scoring.sweep_ratio.weight",
        "quality_scoring.opening_evidence.weight",
        "quality_scoring.risk_reversal.weight",
        (
            "quality_scoring.market_structure."
            "target_expiry_gex_alignment.weight"
        ),
        (
            "quality_scoring.market_structure."
            "negative_gamma_regime.weight"
        ),
        (
            "quality_scoring.market_structure."
            "off_exchange_cluster_score.weight"
        ),
        "quality_scoring.directional_flow_confirmation.weight",
    ]

    quality_total = 0.0

    for path in quality_weight_paths:
        quality_total += _require_number(
            config,
            path,
            minimum=0,
        )

    if abs(quality_total - 100.0) > 1e-9:
        raise ConfigError(
            "Quality atomic weights must total exactly 100. "
            f"Current total: {quality_total}"
        )

    volatility_paths = [
        "volatility_penalty.iv_percentile.weight",
        "volatility_penalty.term_structure.weight",
        "volatility_penalty.iv_vs_rv.weight",
    ]

    volatility_total = 0.0

    for path in volatility_paths:
        volatility_total += _require_number(
            config,
            path,
            minimum=0,
        )

    if abs(volatility_total - 15.0) > 1e-9:
        raise ConfigError(
            "Volatility-risk availability weights must total exactly 15. "
            f"Current total: {volatility_total}"
        )

    expected_coverage_total = quality_total + volatility_total

    configured_coverage_total = _require_number(
        config,
        "coverage.total_availability_weight",
        minimum=0,
        allow_equal_min=False,
    )

    if abs(configured_coverage_total - expected_coverage_total) > 1e-9:
        raise ConfigError(
            "coverage.total_availability_weight must equal "
            "Quality weights + Volatility-risk weights. "
            f"Expected {expected_coverage_total}, "
            f"got {configured_coverage_total}."
        )


def _validate_quality_scoring_details(
    config: dict[str, Any],
) -> None:
    absolute_min = _require_number(
        config,
        "quality_scoring.absolute_flow_strength.minimum_flow",
        minimum=0,
    )

    absolute_full = _require_number(
        config,
        "quality_scoring.absolute_flow_strength.full_score_flow",
        minimum=0,
    )

    if absolute_full <= absolute_min:
        raise ConfigError(
            "absolute_flow_strength.full_score_flow "
            "must be greater than minimum_flow."
        )

    for path in (
        "quality_scoring.relative_flow_strength.enabled",
        "quality_scoring.risk_reversal.enabled",
        (
            "quality_scoring.market_structure."
            "target_expiry_gex_alignment.enabled"
        ),
        (
            "quality_scoring.market_structure."
            "negative_gamma_regime.enabled"
        ),
        (
            "quality_scoring.market_structure."
            "off_exchange_cluster_score.enabled"
        ),
        "volatility_penalty.iv_percentile.enabled",
        "volatility_penalty.term_structure.enabled",
        "volatility_penalty.iv_vs_rv.enabled",
    ):
        _require_bool(
            config,
            path,
        )

    for path in (
        "quality_scoring.relative_flow_strength.default_status",
        "quality_scoring.risk_reversal.default_status",
        (
            "quality_scoring.market_structure."
            "target_expiry_gex_alignment.default_status"
        ),
        (
            "quality_scoring.market_structure."
            "off_exchange_cluster_score.default_status"
        ),
    ):
        status = _require_string(
            config,
            path,
        )

        if status != "UNKNOWN":
            raise ConfigError(
                f"{path} must be exactly 'UNKNOWN'."
            )

    interpolation_points = _require(
        config,
        "quality_scoring.vwap_distance_atr.interpolation_points",
    )

    if (
        not isinstance(interpolation_points, list)
        or len(interpolation_points) < 2
    ):
        raise ConfigError(
            "vwap_distance_atr.interpolation_points "
            "must contain at least two points."
        )

    previous_x = None

    vwap_weight = _require_number(
        config,
        "quality_scoring.vwap_distance_atr.weight",
        minimum=0,
    )

    for index, point in enumerate(
        interpolation_points
    ):
        if not isinstance(point, dict):
            raise ConfigError(
                "Every VWAP interpolation point "
                "must be a mapping."
            )

        x = point.get("x")
        points = point.get("points")

        if (
            isinstance(x, bool)
            or not isinstance(x, (int, float))
            or x < 0
        ):
            raise ConfigError(
                f"VWAP interpolation x at index "
                f"{index} must be >= 0."
            )

        if (
            isinstance(points, bool)
            or not isinstance(points, (int, float))
            or points < 0
            or points > vwap_weight
        ):
            raise ConfigError(
                f"VWAP interpolation points at index "
                f"{index} must be between 0 "
                f"and {vwap_weight}."
            )

        numeric_x = float(x)

        if (
            previous_x is not None
            and numeric_x <= previous_x
        ):
            raise ConfigError(
                "VWAP interpolation x values "
                "must be strictly increasing."
            )

        previous_x = numeric_x

    er_min = _require_number(
        config,
        "quality_scoring.efficiency_ratio_strength.minimum_er",
        minimum=0,
        maximum=1,
    )

    er_max = _require_number(
        config,
        "quality_scoring.efficiency_ratio_strength.maximum_er",
        minimum=0,
        maximum=1,
    )

    if er_max <= er_min:
        raise ConfigError(
            "efficiency_ratio_strength.maximum_er "
            "must be greater than minimum_er."
        )

    sweep_breakpoint = _require_number(
        config,
        "quality_scoring.sweep_ratio.breakpoint_ratio",
        minimum=0,
        maximum=1,
    )

    sweep_max_ratio = _require_number(
        config,
        "quality_scoring.sweep_ratio.maximum_ratio",
        minimum=0,
        maximum=1,
    )

    if sweep_max_ratio < sweep_breakpoint:
        raise ConfigError(
            "sweep_ratio.maximum_ratio cannot be "
            "below breakpoint_ratio."
        )

    sweep_weight = _require_number(
        config,
        "quality_scoring.sweep_ratio.weight",
        minimum=0,
    )

    sweep_breakpoint_points = _require_number(
        config,
        "quality_scoring.sweep_ratio.points_at_breakpoint",
        minimum=0,
    )

    sweep_max_points = _require_number(
        config,
        "quality_scoring.sweep_ratio.maximum_points",
        minimum=0,
    )

    if (
        sweep_breakpoint_points > sweep_max_points
        or sweep_max_points > sweep_weight
    ):
        raise ConfigError(
            "Sweep ratio scoring points must satisfy "
            "breakpoint_points <= maximum_points <= weight."
        )

    opening_weight = _require_number(
        config,
        "quality_scoring.opening_evidence.weight",
        minimum=0,
    )

    opening_point_paths = (
        "all_opening_trades_points",
        "volume_oi_ratio_2_points",
        "volume_oi_ratio_1_points",
        "below_1_points",
    )

    for field in opening_point_paths:
        points = _require_number(
            config,
            "quality_scoring.opening_evidence."
            + field,
            minimum=0,
        )

        if points > opening_weight:
            raise ConfigError(
                "opening_evidence scoring points "
                "cannot exceed its weight."
            )

    directional_weight = _require_number(
        config,
        "quality_scoring.directional_flow_confirmation.weight",
        minimum=0,
    )

    _require_number(
        config,
        "quality_scoring.directional_flow_confirmation.strong_threshold",
        minimum=0,
        maximum=1,
    )

    for field in (
        "strong_points",
        "weak_points",
        "conflict_points",
    ):
        points = _require_number(
            config,
            "quality_scoring.directional_flow_confirmation."
            + field,
            minimum=0,
        )

        if points > directional_weight:
            raise ConfigError(
                "directional_flow_confirmation points "
                "cannot exceed its weight."
            )

    for section in (
        "iv_percentile",
        "term_structure",
        "iv_vs_rv",
    ):
        weight = _require_number(
            config,
            f"volatility_penalty.{section}.weight",
            minimum=0,
        )

        penalty = _require_number(
            config,
            f"volatility_penalty.{section}.penalty",
            minimum=0,
        )

        if penalty > weight:
            raise ConfigError(
                f"volatility_penalty.{section}.penalty "
                "cannot exceed its weight."
            )

    maximum_penalty = _require_number(
        config,
        "volatility_penalty.maximum_penalty",
        minimum=0,
    )

    if maximum_penalty != 15:
        raise ConfigError(
            "weekly_v1 volatility_penalty.maximum_penalty "
            "must be exactly 15."
        )

def _validate_grades_and_coverage(config: dict[str, Any]) -> None:
    coverage_a = _require_number(
        config,
        "coverage.coverage_a_min",
        minimum=0,
        maximum=1,
    )

    coverage_b = _require_number(
        config,
        "coverage.coverage_b_min",
        minimum=0,
        maximum=1,
    )

    coverage_min = _require_number(
        config,
        "coverage.coverage_minimum_for_rating",
        minimum=0,
        maximum=1,
    )

    if coverage_a < coverage_b:
        raise ConfigError(
            "coverage.coverage_a_min must be >= coverage_b_min."
        )

    if abs(coverage_b - coverage_min) > 1e-9:
        raise ConfigError(
            "weekly_v1 requires coverage_b_min and "
            "coverage_minimum_for_rating to be equal."
        )

    grade_a = _require_number(
        config,
        "grades.grade_a_min_score",
        minimum=0,
        maximum=100,
    )

    grade_b = _require_number(
        config,
        "grades.grade_b_min_score",
        minimum=0,
        maximum=100,
    )

    if grade_a <= grade_b:
        raise ConfigError(
            "grades.grade_a_min_score must be greater than "
            "grade_b_min_score."
        )


def _validate_outcomes(config: dict[str, Any]) -> None:
    mode = _require_string(
        config,
        "outcomes.outcome_option_return_mode",
    )

    if mode != "executable_bid_vs_baseline_ask":
        raise ConfigError(
            "weekly_v1 requires outcomes.outcome_option_return_mode="
            "'executable_bid_vs_baseline_ask'."
        )

    checkpoints = _require(
        config,
        "outcomes.checkpoint_minutes",
    )

    if not isinstance(checkpoints, list) or not checkpoints:
        raise ConfigError(
            "outcomes.checkpoint_minutes must be a non-empty list."
        )

    for value in checkpoints:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ConfigError(
                "Every outcomes.checkpoint_minutes value "
                "must be a positive integer."
            )

    named = _require(
        config,
        "outcomes.checkpoint_named",
    )

    required_named = {
        "EOD",
        "NEXT_SESSION_CLOSE",
        "EXPIRY",
    }

    if not isinstance(named, list):
        raise ConfigError(
            "outcomes.checkpoint_named must be a list."
        )

    if set(named) != required_named:
        raise ConfigError(
            "outcomes.checkpoint_named must contain exactly: "
            "EOD, NEXT_SESSION_CLOSE, EXPIRY."
        )


def _validate_database(config: dict[str, Any]) -> None:
    _require_string(
        config,
        "database.path",
    )

    journal_mode = _require_string(
        config,
        "database.journal_mode",
    ).upper()

    if journal_mode != "WAL":
        raise ConfigError(
            "database.journal_mode must be WAL."
        )

    busy_timeout = _require_int(
        config,
        "database.busy_timeout_ms",
        minimum=1,
    )

    if busy_timeout != 5000:
        raise ConfigError(
            "weekly_v1 database.busy_timeout_ms must currently be 5000."
        )

    foreign_keys = _require_bool(
        config,
        "database.foreign_keys",
    )

    if not foreign_keys:
        raise ConfigError(
            "database.foreign_keys must be true."
        )


def validate_weekly_config(
    config: dict[str, Any],
    *,
    require_runtime_ready: bool = True,
) -> None:
    """
    Validate weekly_v1 architecture/config requirements.

    require_runtime_ready=True:
        Enforces values required before the Scanner can start,
        especially max_budget.

    require_runtime_ready=False:
        Allows architecture/config development while max_budget
        is still intentionally unset.
    """
    if not isinstance(config, dict):
        raise ConfigError(
            "weekly_config.yaml must contain a YAML mapping/object."
        )

    _validate_strategy(config)
    _validate_universe(config)
    _validate_market(config)
    _validate_target_expiry(config)
    _validate_scanner(config)
    _validate_flow(config)
    _validate_price_action(config)
    _validate_regime(config)

    _require_number(
        config,
        "volatility.iv_percentile_high",
        minimum=0,
        maximum=100,
    )

    _validate_contract_selector(
        config,
        require_runtime_ready=require_runtime_ready,
    )

    _validate_quality_weights(config)
    _validate_quality_scoring_details(config)
    _validate_grades_and_coverage(config)
    _validate_outcomes(config)
    _validate_database(config)


def calculate_config_hash(
    config: dict[str, Any],
) -> str:
    """
    Create a deterministic SHA-256 hash from the actual config values.

    The same config content always produces the same hash,
    independent of YAML formatting or key order.
    """
    canonical = json.dumps(
        config,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def load_weekly_config(
    path: str | Path | None = None,
    *,
    require_runtime_ready: bool = True,
) -> dict[str, Any]:
    config_path = (
        Path(path).resolve()
        if path is not None
        else get_weekly_config_path()
    )

    if not config_path.exists():
        raise ConfigError(
            f"Config file not found: {config_path}"
        )

    try:
        with config_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            config = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ConfigError(
            f"Invalid YAML in {config_path.name}: {exc}"
        ) from exc

    if config is None:
        raise ConfigError(
            f"{config_path.name} is empty."
        )

    validate_weekly_config(
        config,
        require_runtime_ready=require_runtime_ready,
    )

    config["_meta"] = {
        "config_path": str(config_path),
        "config_hash": calculate_config_hash(config),
    }

    return config


if __name__ == "__main__":
    try:
        loaded = load_weekly_config(
            require_runtime_ready=True,
        )

        print("weekly_v1 config: VALID")
        print(
            "strategy_version:",
            loaded["strategy"]["strategy_version"],
        )
        print(
            "config_hash:",
            loaded["_meta"]["config_hash"],
        )

    except ConfigError as exc:
        print("weekly_v1 config: INVALID")
        print(f"Reason: {exc}")
        raise SystemExit(1)