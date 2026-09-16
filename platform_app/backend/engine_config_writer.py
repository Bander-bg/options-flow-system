from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from config import load_weekly_config

from platform_app.backend.engine_config_reader import (
    CONFIG_PATH,
    load_engine_universe,
)


class UniverseConfigWriteError(ValueError):
    pass


_TICKER_PATTERN = re.compile(
    r"^[A-Z][A-Z0-9.\-]{0,14}$"
)


def normalize_ticker(ticker: str) -> str:
    if not isinstance(ticker, str):
        raise UniverseConfigWriteError(
            "Ticker must be a string."
        )

    normalized = ticker.strip().upper()

    if not normalized:
        raise UniverseConfigWriteError(
            "Ticker cannot be empty."
        )

    if not _TICKER_PATTERN.fullmatch(
        normalized
    ):
        raise UniverseConfigWriteError(
            "Ticker format is invalid."
        )

    return normalized


def _load_universe_from_path(
    path: Path,
) -> list[str]:
    config = load_weekly_config(
        path=path,
        require_runtime_ready=True,
    )

    return [
        str(ticker).strip().upper()
        for ticker in config[
            "universe"
        ]["tickers"]
    ]


def _replace_universe_tickers(
    *,
    path: Path,
    tickers: list[str],
) -> str:
    raw = path.read_bytes()

    if raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        text = raw.decode("utf-8")

    newline = (
        "\r\n"
        if "\r\n" in text
        else "\n"
    )

    lines = text.splitlines(
        keepends=True
    )

    universe_index = None
    universe_indent = None
    tickers_index = None
    tickers_indent = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == "universe:":
            universe_index = i
            universe_indent = (
                len(line)
                - len(line.lstrip())
            )
            continue

        if universe_index is None:
            continue

        if not stripped:
            continue

        indent = (
            len(line)
            - len(line.lstrip())
        )

        if (
            universe_indent is not None
            and indent <= universe_indent
            and i > universe_index
        ):
            break

        if stripped == "tickers:":
            tickers_index = i
            tickers_indent = indent
            break

    if (
        tickers_index is None
        or tickers_indent is None
    ):
        raise UniverseConfigWriteError(
            "universe.tickers section "
            "was not found."
        )

    list_start = tickers_index + 1
    list_end = list_start

    while list_end < len(lines):
        line = lines[list_end]
        stripped = line.strip()

        if not stripped:
            list_end += 1
            continue

        indent = (
            len(line)
            - len(line.lstrip())
        )

        if indent <= tickers_indent:
            break

        list_end += 1

    item_indent = " " * (
        tickers_indent + 2
    )

    replacement = [
        f"{item_indent}- {ticker}{newline}"
        for ticker in tickers
    ]

    # Keep a clean separator before
    # the next top-level config section.
    replacement.append(newline)

    updated_lines = (
        lines[:list_start]
        + replacement
        + lines[list_end:]
    )

    # Avoid duplicated blank lines
    # introduced at the boundary.
    while (
        list_start
        + len(replacement)
        < len(updated_lines)
        and updated_lines[
            list_start
            + len(replacement)
            - 1
        ].strip() == ""
        and updated_lines[
            list_start
            + len(replacement)
        ].strip() == ""
    ):
        del updated_lines[
            list_start
            + len(replacement)
        ]

    return "".join(updated_lines)


def _atomic_write_validated(
    *,
    path: Path,
    updated_text: str,
) -> None:
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=".weekly_config_",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(
                updated_text
            )
            temp_file.flush()
            os.fsync(
                temp_file.fileno()
            )
            temp_path = Path(
                temp_file.name
            )

        # Full weekly_v1 validation
        # happens BEFORE replacing
        # the real config file.
        load_weekly_config(
            path=temp_path,
            require_runtime_ready=True,
        )

        os.replace(
            temp_path,
            path,
        )

        temp_path = None

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()


def set_universe_tickers(
    tickers: list[str],
    *,
    path: Path = CONFIG_PATH,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for ticker in tickers:
        value = normalize_ticker(
            ticker
        )

        if value in seen:
            raise UniverseConfigWriteError(
                f"Duplicate ticker: {value}"
            )

        seen.add(value)
        normalized.append(value)

    if not normalized:
        raise UniverseConfigWriteError(
            "Universe must contain at "
            "least one ticker."
        )

    updated_text = (
        _replace_universe_tickers(
            path=path,
            tickers=normalized,
        )
    )

    _atomic_write_validated(
        path=path,
        updated_text=updated_text,
    )

    return _load_universe_from_path(
        path
    )


def add_universe_ticker(
    ticker: str,
    *,
    path: Path = CONFIG_PATH,
) -> list[str]:
    normalized = normalize_ticker(
        ticker
    )

    current = (
        _load_universe_from_path(
            path
        )
    )

    if normalized in current:
        raise UniverseConfigWriteError(
            f"{normalized} already exists."
        )

    return set_universe_tickers(
        current + [normalized],
        path=path,
    )


def delete_universe_ticker(
    ticker: str,
    *,
    path: Path = CONFIG_PATH,
) -> list[str]:
    normalized = normalize_ticker(
        ticker
    )

    current = (
        _load_universe_from_path(
            path
        )
    )

    if normalized not in current:
        raise UniverseConfigWriteError(
            f"{normalized} was not found."
        )

    if len(current) <= 1:
        raise UniverseConfigWriteError(
            "Cannot delete the last "
            "ticker from the universe."
        )

    updated = [
        item
        for item in current
        if item != normalized
    ]

    return set_universe_tickers(
        updated,
        path=path,
    )
