from pathlib import Path
import shutil

p = Path("weekly/db/signal_repository.py")
b = Path("weekly/db/signal_repository.before_update_state.bak")

METHOD = '\n    def update_state(\n        self,\n        *,\n        signal_id: int,\n        new_state: SignalState,\n        expected_state: SignalState | None = None,\n        confirmed_at: datetime | None = None,\n        terminal_at: datetime | None = None,\n        terminal_reason: str | None = None,\n        net_flow_at_confirmation: float | None = None,\n    ) -> Signal:\n        if signal_id < 1:\n            raise ValueError("signal_id must be >= 1")\n\n        for name, value in (\n            ("confirmed_at", confirmed_at),\n            ("terminal_at", terminal_at),\n        ):\n            if value is not None and value.tzinfo is None:\n                raise ValueError(f"{name} must be timezone-aware")\n\n        params = {\n            "signal_id": signal_id,\n            "new_state": new_state.value,\n            "expected_state": (\n                expected_state.value\n                if expected_state is not None\n                else None\n            ),\n            "confirmed_at": _datetime_to_db(confirmed_at),\n            "terminal_at": _datetime_to_db(terminal_at),\n            "terminal_reason": terminal_reason,\n            "net_flow_at_confirmation": net_flow_at_confirmation,\n        }\n\n        with database_transaction() as connection:\n            if expected_state is None:\n                cursor = connection.execute(\n                    """\n                    UPDATE signals\n                    SET\n                        state = :new_state,\n                        confirmed_at = COALESCE(:confirmed_at, confirmed_at),\n                        terminal_at = COALESCE(:terminal_at, terminal_at),\n                        terminal_reason = COALESCE(:terminal_reason, terminal_reason),\n                        net_flow_at_confirmation = COALESCE(\n                            :net_flow_at_confirmation,\n                            net_flow_at_confirmation\n                        ),\n                        updated_at = strftime(\'%Y-%m-%dT%H:%M:%fZ\', \'now\')\n                    WHERE id = :signal_id;\n                    """,\n                    params,\n                )\n            else:\n                cursor = connection.execute(\n                    """\n                    UPDATE signals\n                    SET\n                        state = :new_state,\n                        confirmed_at = COALESCE(:confirmed_at, confirmed_at),\n                        terminal_at = COALESCE(:terminal_at, terminal_at),\n                        terminal_reason = COALESCE(:terminal_reason, terminal_reason),\n                        net_flow_at_confirmation = COALESCE(\n                            :net_flow_at_confirmation,\n                            net_flow_at_confirmation\n                        ),\n                        updated_at = strftime(\'%Y-%m-%dT%H:%M:%fZ\', \'now\')\n                    WHERE id = :signal_id\n                      AND state = :expected_state;\n                    """,\n                    params,\n                )\n\n            if cursor.rowcount != 1:\n                if expected_state is None:\n                    raise RuntimeError(\n                        "Signal state update failed: signal not found."\n                    )\n                raise RuntimeError(\n                    "Signal state update failed: signal not found or current state "\n                    "does not match expected_state."\n                )\n\n            row = connection.execute(\n                "SELECT * FROM signals WHERE id = ?;",\n                (signal_id,),\n            ).fetchone()\n\n        if row is None:\n            raise RuntimeError(\n                "Signal state update succeeded but the updated row could not be read."\n            )\n\n        return _row_to_signal(row)\n'

def main():
    if not p.exists():
        raise RuntimeError(f"File not found: {p}")

    text = p.read_text(encoding="utf-8")

    if "def update_state(" in text:
        print("update_state: already present")
        print("SIGNAL REPOSITORY UPDATE_STATE PATCH: PASS")
        return

    if "class SignalRepository:" not in text:
        raise RuntimeError("SignalRepository class not found. No file was changed.")

    if not b.exists():
        shutil.copy2(p, b)
        print(f"Backup created: {b}")
    else:
        print(f"Backup already exists: {b}")

    updated = text.rstrip() + METHOD + "\n"
    compile(updated, str(p), "exec")
    p.write_text(updated, encoding="utf-8")

    print("update_state: patched")
    print("SIGNAL REPOSITORY UPDATE_STATE PATCH: PASS")

if __name__ == "__main__":
    main()
