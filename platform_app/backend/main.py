import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from platform_app.backend.platform_data import (
    signals as platform_signals,
    signal_detail as platform_signal_detail,
    positions as platform_positions,
    trades as platform_trades,
    outcomes as platform_outcomes,
    data_health as platform_data_health,
)
from platform_app.backend.paper_execution_bridge import (
    prepare_entry as paper_prepare_entry_service,
    prepare_exit as paper_prepare_exit_service,
)

from weekly.db.migration_runner import run_migrations

from platform_app.backend.engine_config_writer import (
    UniverseConfigWriteError,
    add_universe_ticker,
    delete_universe_ticker,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("OPTIONS_FLOW_DB_PATH"):
        run_migrations()

    yield


app = FastAPI(
    title="Options Flow Platform",
    version="0.1.0",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parents[1]




TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# === SIGNAL STATE ARABIC UI ===

SIGNAL_STATE_AR = {
    "CANDIDATE": "?????",
    "CONFIRMED": "?????",
    "ACTIVE": "????",
    "ACCELERATED": "???????",
    "REJECTED": "??????",
    "INVALIDATED": "?????",
    "DATA_BLOCKED": "??????",
    "DATA_UNRESOLVED": "??? ??????",
    "EXPIRED": "??????",
}


def signal_state_ar(value):
    if value is None:
        return "?"

    key = str(value)

    return SIGNAL_STATE_AR.get(
        key,
        key,
    )


templates.env.filters[
    "state_ar"
] = signal_state_ar

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")








@app.get("/health")
def health():
    from platform_app.backend.engine_reader import (
        engine_connection_status,
    )

    engine_status = engine_connection_status()
    engine_connected = bool(
        engine_status.get("connected", False)
    )

    return {
        "status": "ok",
        "platform": (
            "engine-integrated"
            if engine_connected
            else "engine-data-unavailable"
        ),
        "engine_connected": engine_connected,
        "engine_database": engine_status.get("database"),
        "paper_preparation": True,
        "broker_connected": False,
        "broker_order_submission": False,
        "runtime_controlled_by_platform": False,
    }


@app.get("/api/signals")
def get_signals():
    signals, data_source = platform_signals()
    return {
        "source": data_source,
        "count": len(signals),
        "signals": signals,
    }


@app.get("/api/universe")
def get_universe():
    from platform_app.backend.engine_config_reader import load_engine_universe

    tickers = load_engine_universe()

    return {
        "source": "ENGINE CONFIG",
        "read_only": False,
        "manageable": True,
        "count": len(tickers),
        "universe": [{"ticker": ticker} for ticker in tickers],
    }


@app.post("/api/universe/add")
def add_universe_ticker_api(ticker: str):
    try:
        tickers = add_universe_ticker(ticker)
    except UniverseConfigWriteError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "status": "ok",
        "action": "added",
        "ticker": ticker.strip().upper(),
        "count": len(tickers),
        "universe": [
            {"ticker": item}
            for item in tickers
        ],
    }


@app.post("/api/universe/{ticker}/toggle")
def toggle_universe_ticker_api(ticker: str):
    raise HTTPException(
        status_code=405,
        detail="Ticker enable/disable is not defined. Use add/delete.",
    )


@app.delete("/api/universe/{ticker}")
def delete_universe_ticker_api(ticker: str):
    try:
        tickers = delete_universe_ticker(ticker)
    except UniverseConfigWriteError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "status": "ok",
        "action": "deleted",
        "ticker": ticker.strip().upper(),
        "count": len(tickers),
        "universe": [
            {"ticker": item}
            for item in tickers
        ],
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    signals, data_source = platform_signals()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "signals": signals,
            "data_source": data_source,
        },
    )


@app.get("/universe", response_class=HTMLResponse)
def universe_page(request: Request):
    from platform_app.backend.engine_config_reader import load_engine_universe

    tickers = load_engine_universe()
    universe = [{"ticker": ticker} for ticker in tickers]

    return templates.TemplateResponse(
        request=request,
        name="universe.html",
        context={
            "universe": universe,
            "total_count": len(universe),
            "data_source": "ENGINE CONFIG",
            "notice": request.query_params.get("notice"),
            "notice_ticker": request.query_params.get("ticker", ""),
            "notice_reason": request.query_params.get("reason", ""),
        },
    )


@app.post("/universe/add")
def universe_add_form(ticker: str = Form(...)):
    normalized = ticker.strip().upper()

    try:
        add_universe_ticker(ticker)
    except UniverseConfigWriteError as exc:
        message = str(exc)

        if "already exists" in message:
            reason = "duplicate"
        elif (
            "invalid" in message
            or "empty" in message
        ):
            reason = "invalid"
        else:
            reason = "error"

        return RedirectResponse(
            url=(
                "/universe?notice=error"
                f"&reason={reason}"
                f"&ticker={normalized}"
            ),
            status_code=303,
        )

    return RedirectResponse(
        url=(
            "/universe?notice=added"
            f"&ticker={normalized}"
        ),
        status_code=303,
    )


@app.post("/universe/{ticker}/toggle")
def universe_toggle_form(ticker: str):
    raise HTTPException(
        status_code=405,
        detail="Ticker enable/disable is not defined. Use add/delete.",
    )


@app.post("/universe/{ticker}/delete")
def universe_delete_form(ticker: str):
    normalized = ticker.strip().upper()

    try:
        delete_universe_ticker(ticker)
    except UniverseConfigWriteError as exc:
        message = str(exc)

        if "last" in message:
            reason = "last"
        elif "not found" in message:
            reason = "not_found"
        else:
            reason = "error"

        return RedirectResponse(
            url=(
                "/universe?notice=error"
                f"&reason={reason}"
                f"&ticker={normalized}"
            ),
            status_code=303,
        )

    return RedirectResponse(
        url=(
            "/universe?notice=deleted"
            f"&ticker={normalized}"
        ),
        status_code=303,
    )


@app.get("/signals", response_class=HTMLResponse)
def signals_page(request: Request):
    signals, data_source = platform_signals()

    return templates.TemplateResponse(
        request=request,
        name="signals.html",
        context={
            "signals": signals,
            "data_source": data_source,
        },
    )





@app.get("/signals/{ticker}", response_class=HTMLResponse)
def signal_detail_page(request: Request, ticker: str):
    ticker = ticker.strip().upper()
    signal, data_source = platform_signal_detail(ticker)

    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found.")

    return templates.TemplateResponse(
        request=request,
        name="signal_detail.html",
        context={
            "signal": signal,
            "data_source": data_source,
        },
    )





@app.get("/positions", response_class=HTMLResponse)
def positions_page(request: Request):
    positions, data_source = platform_positions()

    total_entry_value = sum(
        position["entry_price"] * 100 * position["quantity"]
        for position in positions
        if position.get("entry_price") is not None
    )

    current_prices_available = all(
        position.get("current_price") is not None
        for position in positions
    )

    if current_prices_available:
        total_current_value = sum(
            position["current_price"] * 100 * position["quantity"]
            for position in positions
        )
        total_pnl = total_current_value - total_entry_value
    else:
        total_current_value = None
        total_pnl = None

    return templates.TemplateResponse(
        request=request,
        name="positions.html",
        context={
            "positions": positions,
            "total_entry_value": total_entry_value,
            "total_current_value": total_current_value,
            "total_pnl": total_pnl,
            "data_source": data_source,
        },
    )





@app.get("/trades", response_class=HTMLResponse)
def trades_page(request: Request):
    trades, data_source = platform_trades()

    return templates.TemplateResponse(
        request=request,
        name="trades.html",
        context={
            "trades": trades,
            "data_source": data_source,
        },
    )





@app.get("/outcomes", response_class=HTMLResponse)
def outcomes_page(request: Request):
    outcomes, data_source = platform_outcomes()

    option_values = [
        item["option_executable_return_pct"]
        for item in outcomes
        if item.get("option_executable_return_pct") is not None
    ]

    directional_values = [
        item["directional_return_pct"]
        for item in outcomes
        if item.get("directional_return_pct") is not None
    ]

    avg_option_return = (
        sum(option_values) / len(option_values)
        if option_values else None
    )

    avg_directional_return = (
        sum(directional_values) / len(directional_values)
        if directional_values else None
    )

    return templates.TemplateResponse(
        request=request,
        name="outcomes.html",
        context={
            "outcomes": outcomes,
            "avg_option_return": avg_option_return,
            "avg_directional_return": avg_directional_return,
            "data_source": data_source,
        },
    )





@app.get("/data-health", response_class=HTMLResponse)
def data_health_page(request: Request):
    items, data_source = platform_data_health()

    return templates.TemplateResponse(
        request=request,
        name="data_health.html",
        context={
            "items": items,
            "data_source": data_source,
        },
    )

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    from config import load_weekly_config
    from platform_app.backend.engine_reader import (
        engine_connection_status,
    )

    engine_status = engine_connection_status()
    config = load_weekly_config(
        require_runtime_ready=True
    )

    database_config = config["database"]

    settings = {
        "platform_mode": (
            "ENGINE CONNECTED"
            if engine_status.get("connected", False)
            else "ENGINE DATA UNAVAILABLE"
        ),
        "data_source": "ENGINE DB + weekly_config.yaml",
        "strategy_version": config["strategy"]["strategy_version"],
        "engine_connected": engine_status.get(
            "connected",
            False,
        ),
        "engine_connection_reason": engine_status.get(
            "reason"
        ),
        "engine_database": engine_status.get(
            "database"
        ),
        "paper_preparation": True,
        "broker_order_submission": False,
        "runtime_controlled_by_platform": False,
        "database_journal_mode": database_config[
            "journal_mode"
        ],
        "database_busy_timeout_ms": database_config[
            "busy_timeout_ms"
        ],
        "database_foreign_keys": database_config[
            "foreign_keys"
        ],
        "language": "AR / RTL",
    }

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "settings": settings,
            "engine_status": engine_status,
        },
    )


@app.get("/paper-trading", response_class=HTMLResponse)
def paper_trading_page(request: Request):
    from platform_app.backend.paper_position_pnl import (
        enrich_position_with_live_pnl,
    )
    from weekly.providers.weekly_provider_factory import (
        build_weekly_providers,
    )

    signals, _ = platform_signals()
    positions, _ = platform_positions()
    trades, _ = platform_trades()

    confirmed_signals = [
        signal
        for signal in signals
        if signal.get("state") == "CONFIRMED"
    ]

    open_positions = [
        position
        for position in positions
        if position.get("status") == "OPEN"
    ]

    options_provider = None

    has_filled_position = any(
        position.get("entry_price") is not None
        for position in open_positions
    )

    if has_filled_position:
        try:
            providers = build_weekly_providers()
            options_provider = providers.options
        except Exception:
            options_provider = None

    positions_with_pnl = [
        enrich_position_with_live_pnl(
            position,
            options_provider=options_provider,
        )
        for position in open_positions
    ]

    paper_trades = [
        trade
        for trade in trades
        if trade.get("execution_mode") == "PAPER"
    ]

    return templates.TemplateResponse(
        request=request,
        name="paper_trading.html",
        context={
            "signals": confirmed_signals,
            "positions": positions_with_pnl,
            "trades": paper_trades,
            "data_source": "ENGINE DB",
        },
    )

@app.post("/paper-trading/prepare-entry")
def paper_prepare_entry(
    signal_id: int = Form(...),
    quantity: int = Form(...),
):
    if signal_id < 1:
        raise HTTPException(
            status_code=400,
            detail="signal_id must be >= 1",
        )

    if quantity < 1:
        raise HTTPException(
            status_code=400,
            detail="quantity must be >= 1",
        )

    try:
        paper_prepare_entry_service(
            signal_id=signal_id,
            quantity=quantity,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url="/paper-trading",
        status_code=303,
    )


@app.post("/paper-trading/prepare-exit")
def paper_prepare_exit(
    position_id: int = Form(...),
):
    if position_id < 1:
        raise HTTPException(
            status_code=400,
            detail="position_id must be >= 1",
        )

    try:
        paper_prepare_exit_service(
            position_id=position_id,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="\u062a\u0639\u0630\u0631 \u062a\u062c\u0647\u064a\u0632 \u0627\u0644\u062e\u0631\u0648\u062c \u0628\u0633\u0628\u0628 \u0639\u062f\u0645 \u062a\u0648\u0641\u0631 \u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0639\u0642\u062f \u0627\u0644\u062d\u0627\u0644\u064a\u0629.",
        ) from exc

    return RedirectResponse(
        url="/paper-trading",
        status_code=303,
    )


@app.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="alerts.html",
        context={
            "alerts": [],
            "data_source": "NO_REAL_ALERT_SOURCE",
        },
    )


@app.post("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: str):
    raise HTTPException(
        status_code=403,
        detail="No authoritative alert store is configured.",
    )

