from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import weekly.db.database as dbmod
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import Direction, SignalState
from weekly.domain.models import Signal


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def main():
    production_db = (
        dbmod.get_database_path().resolve()
    )

    if not production_db.exists():
        raise RuntimeError(
            "Production database not found: "
            f"{production_db}"
        )

    before = sha256(production_db)

    with tempfile.TemporaryDirectory(
        prefix="weekly_signal_provenance_test_"
    ) as temp_dir:
        temp_db = (
            Path(temp_dir)
            / "weekly_trading_test.db"
        )

        source = sqlite3.connect(
            f"{production_db.as_uri()}?mode=ro",
            uri=True,
        )

        target = sqlite3.connect(
            temp_db
        )

        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

        original_get_database_path = (
            dbmod.get_database_path
        )

        dbmod.get_database_path = (
            lambda: temp_db
        )

        try:
            repo = SignalRepository()

            trading_day = date(
                2099,
                2,
                2,
            )

            expiry = date(
                2099,
                2,
                6,
            )

            seq = (
                repo.next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker="AAPL",
                    trading_date_et=trading_day,
                    target_expiry=expiry,
                    direction=(
                        Direction.BULLISH
                    ),
                )
            )

            candidate_at = datetime(
                2099,
                2,
                2,
                15,
                0,
                tzinfo=timezone.utc,
            )

            signal = Signal(
                strategy_version="weekly_v1",
                config_hash=(
                    "provenance-temp-test"
                ),
                ticker="AAPL",
                trading_date_et=trading_day,
                target_expiry=expiry,
                direction=Direction.BULLISH,
                candidate_sequence=seq,
                state=SignalState.CANDIDATE,
                candidate_at=candidate_at,
                net_flow_at_candidate=(
                    600000.0
                ),
                flow_dedup_level=(
                    "alert_uuid"
                ),
                stock_data_provider=None,
                stock_data_feed=None,
                options_data_provider=None,
                options_data_feed=None,
                scenario_return_enabled=False,
            )

            created = repo.create(
                signal
            )

            assert created.id is not None

            assert (
                created.stock_data_provider
                is None
            )

            assert (
                created.options_data_provider
                is None
            )

            # ------------------------------------------
            # 1) Stock provenance
            # ------------------------------------------

            stock_updated = (
                repo.update_market_data_provenance(
                    signal_id=created.id,
                    stock_data_provider=(
                        "ALPACA"
                    ),
                    stock_data_feed="iex",
                )
            )

            assert (
                stock_updated.stock_data_provider
                == "ALPACA"
            )

            assert (
                stock_updated.stock_data_feed
                == "iex"
            )

            assert (
                stock_updated.options_data_provider
                is None
            )

            assert (
                stock_updated.options_data_feed
                is None
            )

            assert (
                stock_updated.state
                is SignalState.CANDIDATE
            )

            # ------------------------------------------
            # 2) Options provenance
            # ------------------------------------------

            options_updated = (
                repo.update_market_data_provenance(
                    signal_id=created.id,
                    options_data_provider=(
                        "ALPACA"
                    ),
                    options_data_feed=(
                        "indicative"
                    ),
                )
            )

            assert (
                options_updated.stock_data_provider
                == "ALPACA"
            )

            assert (
                options_updated.stock_data_feed
                == "iex"
            )

            assert (
                options_updated.options_data_provider
                == "ALPACA"
            )

            assert (
                options_updated.options_data_feed
                == "indicative"
            )

            assert (
                options_updated.state
                is SignalState.CANDIDATE
            )

            # ------------------------------------------
            # 3) Reload persistence
            # ------------------------------------------

            reloaded = repo.get_by_id(
                created.id
            )

            assert reloaded is not None

            assert (
                reloaded.stock_data_provider
                == "ALPACA"
            )

            assert (
                reloaded.stock_data_feed
                == "iex"
            )

            assert (
                reloaded.options_data_provider
                == "ALPACA"
            )

            assert (
                reloaded.options_data_feed
                == "indicative"
            )

            # ------------------------------------------
            # 4) Partial pair rejected
            # ------------------------------------------

            partial_pair_rejected = False

            try:
                repo.update_market_data_provenance(
                    signal_id=created.id,
                    stock_data_provider=(
                        "ALPACA"
                    ),
                )
            except ValueError:
                partial_pair_rejected = True

            assert partial_pair_rejected

            # ------------------------------------------
            # 5) Empty update rejected
            # ------------------------------------------

            empty_update_rejected = False

            try:
                repo.update_market_data_provenance(
                    signal_id=created.id,
                )
            except ValueError:
                empty_update_rejected = True

            assert empty_update_rejected

            # ------------------------------------------
            # 6) Existing values preserved
            # ------------------------------------------

            final_reload = (
                repo.get_by_id(
                    created.id
                )
            )

            assert final_reload is not None

            assert (
                final_reload.stock_data_provider
                == "ALPACA"
            )

            assert (
                final_reload.stock_data_feed
                == "iex"
            )

            assert (
                final_reload.options_data_provider
                == "ALPACA"
            )

            assert (
                final_reload.options_data_feed
                == "indicative"
            )

            assert (
                final_reload.state
                is SignalState.CANDIDATE
            )

        finally:
            dbmod.get_database_path = (
                original_get_database_path
            )

    after = sha256(
        production_db
    )

    assert before == after

    print(
        "1. temporary database copy: PASS"
    )
    print(
        "2. stock provenance persisted: PASS"
    )
    print(
        "3. options provenance persisted: PASS"
    )
    print(
        "4. existing provenance preserved: PASS"
    )
    print(
        "5. partial provenance pair rejected: PASS"
    )
    print(
        "6. empty provenance update rejected: PASS"
    )
    print(
        "7. signal state unchanged: PASS"
    )
    print(
        "8. production database unchanged: PASS"
    )

    print()
    print("=" * 70)

    print(
        "SIGNAL REPOSITORY PROVENANCE: PASS 8/8"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
