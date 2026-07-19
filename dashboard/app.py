"""Dashboard backend — a pure viewer over files the trading-agents pipeline
produces, plus live price history for charting. Optionally runs the pipeline
itself on a daily schedule (in-process) when ENABLE_SCHEDULER=true.

This process never imports or calls anything from a brokerage connector and
has no order-placement code path. It only reads watchlist.json and
decisions_log.jsonl, and fetches public market data via yfinance.
"""

import base64
import json
import os
import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import yfinance as yf
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

TRADING_AGENTS_DIR = Path(__file__).resolve().parent.parent / "trading-agents"
sys.path.insert(0, str(TRADING_AGENTS_DIR))

DATA_DIR = Path(os.environ.get("DATA_DIR", TRADING_AGENTS_DIR))
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
DECISIONS_LOG_PATH = DATA_DIR / "decisions_log.jsonl"

DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")
ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "false").lower() == "true"


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Gates every request, including mounted static files — a route-level
    Depends() would skip the /static mount, which isn't a FastAPI path
    operation. No-op when DASHBOARD_PASSWORD is unset (local dev)."""

    async def dispatch(self, request: Request, call_next):
        if not DASHBOARD_PASSWORD:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
            except Exception:
                user, pw = "", ""
            if secrets.compare_digest(user, "admin") and secrets.compare_digest(pw, DASHBOARD_PASSWORD):
                return await call_next(request)

        return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    if ENABLE_SCHEDULER:
        from apscheduler.schedulers.background import BackgroundScheduler
        from run_watchlist import refresh_watchlist

        scheduler = BackgroundScheduler()
        scheduler.add_job(refresh_watchlist, "cron", hour=int(os.environ.get("REFRESH_HOUR_UTC", "10")))
        scheduler.start()
        yield
        scheduler.shutdown()
    else:
        yield


app = FastAPI(title="Trading Agents Dashboard", lifespan=lifespan)
app.add_middleware(BasicAuthMiddleware)


def _read_watchlist() -> list[str]:
    if not WATCHLIST_PATH.exists():
        return []
    return json.loads(WATCHLIST_PATH.read_text())


def _read_decisions() -> list[dict]:
    if not DECISIONS_LOG_PATH.exists():
        return []
    entries = []
    for line in DECISIONS_LOG_PATH.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


@app.get("/api/watchlist")
def get_watchlist():
    return {"watchlist": _read_watchlist()}


@app.get("/api/decisions")
def get_decisions():
    """All logged proposals, plus the latest one per ticker."""
    entries = _read_decisions()
    latest_by_ticker: dict[str, dict] = {}
    for entry in entries:
        ticker = entry["ticker"]
        if ticker not in latest_by_ticker or entry["logged_at"] > latest_by_ticker[ticker]["logged_at"]:
            latest_by_ticker[ticker] = entry
    return {"latest": latest_by_ticker, "history": entries}


@app.get("/api/decisions/{ticker}")
def get_decisions_for_ticker(ticker: str):
    entries = [e for e in _read_decisions() if e["ticker"] == ticker.upper()]
    if not entries:
        raise HTTPException(status_code=404, detail=f"No logged decisions for {ticker.upper()}")
    return {"ticker": ticker.upper(), "history": entries}


@app.get("/api/price-history/{ticker}")
def get_price_history(ticker: str, period: str = "6mo"):
    history = yf.Ticker(ticker.upper()).history(period=period, interval="1d")
    if history.empty:
        raise HTTPException(status_code=404, detail=f"No price history for {ticker.upper()}")
    history = history.rename(columns=str.lower)
    return {
        "ticker": ticker.upper(),
        "dates": [d.strftime("%Y-%m-%d") for d in history.index],
        "open": history["open"].round(2).tolist(),
        "high": history["high"].round(2).tolist(),
        "low": history["low"].round(2).tolist(),
        "close": history["close"].round(2).tolist(),
        "volume": history["volume"].tolist(),
    }


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
