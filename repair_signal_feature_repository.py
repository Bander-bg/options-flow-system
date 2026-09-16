from __future__ import annotations

import shutil
from pathlib import Path


TARGET = Path(
    "weekly/db/signal_feature_repository.py"
)

BACKUP = Path(
    "weekly/db/signal_feature_repository.before_v3.bak"
)


def replace_once(
    text: str,
    old: str,
    new: str,
    *,
    label: str,
    already_marker: str,
) -> str:
    if already_marker in text:
        print(f"{label}: already present")
        return text

    count = text.count(old)

    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly 1 old block, "
            f"found {count}. No file was changed."
        )

    print(f"{label}: patched")

    return text.replace(
        old,
        new,
        1,
    )


def main() -> None:
    if not TARGET.exists():
        raise RuntimeError(
            f"File not found: {TARGET}"
        )

    original = TARGET.read_text(
        encoding="utf-8"
    )

    if not BACKUP.exists():
        shutil.copy2(
            TARGET,
            BACKUP,
        )

        print(
            f"Backup created: {BACKUP}"
        )

    else:
        print(
            f"Backup already exists: {BACKUP}"
        )

    text = original

    imports = """from __future__ import annotations

from datetime import date, datetime

from weekly.db.database import (
    database_connection,
    database_transaction,
)
from weekly.domain.enums import (
    GateStatus,
    OptionRight,
)
from weekly.domain.models import SignalFeature


"""

    if (
        "from weekly.db.database import"
        not in text
    ):
        text = imports + text
        print("imports: patched")
    else:
        print("imports: already present")

    text = replace_once(
        text,
        """def _serialize_optional_enum(
    value,
) -> str | None:
    if value is None:
        return None

    return value.value


# --------------------------------------------------
# PARSING HELPERS
# --------------------------------------------------
""",
        """def _serialize_optional_enum(
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
""",
        label="bool serializer",
        already_marker=(
            "def _serialize_optional_bool("
        ),
    )

    text = replace_once(
        text,
        """def _parse_optional_option_right(
    value: str | None,
) -> OptionRight | None:
    if value is None:
        return None

    return OptionRight(
        value
    )


# --------------------------------------------------
# ROW -> DOMAIN MODEL
# --------------------------------------------------
""",
        """def _parse_optional_option_right(
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
""",
        label="bool parser",
        already_marker=(
            "def _parse_optional_bool("
        ),
    )

    text = replace_once(
        text,
        """        impulse_body_atr_ratio=(
            row[
                "impulse_body_atr_ratio"
            ]
        ),

        participation_avg_slot_volume=(
            row[
                "participation_avg_slot_volume"
            ]
        ),

        participation_rvol=(
            row["participation_rvol"]
        ),
""",
        """        impulse_body_atr_ratio=(
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
""",
        label="row-to-model V3 fields",
        already_marker=(
            "        impulse_engulfing_match=("
        ),
    )

    text = replace_once(
        text,
        """            "impulse_body_atr_ratio": (
                feature
                .impulse_body_atr_ratio
            ),

            "participation_avg_slot_volume": (
                feature
                .participation_avg_slot_volume
            ),

            "participation_rvol": (
                feature
                .participation_rvol
            ),
""",
        """            "impulse_body_atr_ratio": (
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
""",
        label="create values V3 fields",
        already_marker=(
            '            "impulse_engulfing_match": ('
        ),
    )

    text = replace_once(
        text,
        """                    impulse_body,
                    impulse_median_body,
                    impulse_body_atr_ratio,

                    participation_avg_slot_volume,
                    participation_rvol,

                    atr_1h,
""",
        """                    impulse_body,
                    impulse_median_body,
                    impulse_body_atr_ratio,
                    impulse_engulfing_match,
                    impulse_expansion_match,

                    participation_avg_slot_volume,
                    participation_median_slot_volume,
                    participation_reference_sessions,
                    participation_rvol,

                    atr_1h,
""",
        label="INSERT columns V3 fields",
        already_marker=(
            "                    impulse_engulfing_match,"
        ),
    )

    text = replace_once(
        text,
        """                    :impulse_body,
                    :impulse_median_body,
                    :impulse_body_atr_ratio,

                    :participation_avg_slot_volume,
                    :participation_rvol,

                    :atr_1h,
""",
        """                    :impulse_body,
                    :impulse_median_body,
                    :impulse_body_atr_ratio,
                    :impulse_engulfing_match,
                    :impulse_expansion_match,

                    :participation_avg_slot_volume,
                    :participation_median_slot_volume,
                    :participation_reference_sessions,
                    :participation_rvol,

                    :atr_1h,
""",
        label="INSERT values V3 fields",
        already_marker=(
            "                    :impulse_engulfing_match,"
        ),
    )

    compile(
        text,
        str(TARGET),
        "exec",
    )

    TARGET.write_text(
        text,
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print(
        "SIGNAL FEATURE REPOSITORY V3 REPAIR: PASS"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()