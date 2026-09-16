from pathlib import Path
import shutil

TARGET = Path("weekly/domain/models.py")
BACKUP = Path("weekly/domain/models.before_signal_sign_fix.bak")

def main():
    if not TARGET.exists():
        raise RuntimeError(f"File not found: {TARGET}")

    text = TARGET.read_text(encoding="utf-8")

    if not BACKUP.exists():
        shutil.copy2(TARGET, BACKUP)
        print(f"Backup created: {BACKUP}")
    else:
        print(f"Backup already exists: {BACKUP}")

    signal_marker = "@dataclass(frozen=True)\nclass Signal:"
    feature_marker = "@dataclass(frozen=True)\nclass SignalFeature:"

    signal_start = text.find(signal_marker)
    if signal_start == -1:
        raise RuntimeError("Signal class could not be found. No file was changed.")

    signal_end = text.find(feature_marker, signal_start)
    if signal_end == -1:
        raise RuntimeError("SignalFeature class could not be found. No file was changed.")

    signal_block = text[signal_start:signal_end]

    if "def signal_sign(" in signal_block:
        print("signal_sign property: already present")
        print()
        print("=" * 70)
        print("SIGNAL SIGN RECOVERY: PASS")
        print("=" * 70)
        return

    old = """    id: int | None = None

    def __post_init__(self):
"""

    new = """    id: int | None = None

    @property
    def signal_sign(self) -> int:
        return self.direction.sign

    def __post_init__(self):
"""

    matches = signal_block.count(old)
    if matches != 1:
        raise RuntimeError(
            "Could not safely locate the Signal insertion point. "
            f"Expected 1 match, found {matches}. No file was changed."
        )

    updated_signal_block = signal_block.replace(old, new, 1)
    updated_text = text[:signal_start] + updated_signal_block + text[signal_end:]

    compile(updated_text, str(TARGET), "exec")
    TARGET.write_text(updated_text, encoding="utf-8")

    print("signal_sign property: patched")
    print()
    print("=" * 70)
    print("SIGNAL SIGN RECOVERY: PASS")
    print("=" * 70)

if __name__ == "__main__":
    main()
