from config import get_weekly_config_path


CONFIG_PATH = get_weekly_config_path()


def load_engine_universe():
    """
    Read universe.tickers from weekly_config.yaml without modifying it.
    Returns a list of ticker strings.
    """
    lines = CONFIG_PATH.read_text(encoding="utf-8-sig").splitlines()

    tickers = []
    in_universe = False
    in_tickers = False
    universe_indent = None
    tickers_indent = None

    for raw_line in lines:
        stripped = raw_line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        if stripped == "universe:":
            in_universe = True
            in_tickers = False
            universe_indent = indent
            continue

        if in_universe and universe_indent is not None and indent <= universe_indent:
            break

        if in_universe and stripped == "tickers:":
            in_tickers = True
            tickers_indent = indent
            continue

        if in_tickers:
            if tickers_indent is not None and indent <= tickers_indent:
                break

            if stripped.startswith("- "):
                ticker = stripped[2:].strip().strip("'").strip('"').upper()
                if ticker:
                    tickers.append(ticker)

    return tickers
