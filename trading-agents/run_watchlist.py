"""Refresh proposals for every ticker in watchlist.json.

Run this before checking the dashboard so it has fresh decisions to show.
Never places an order — same as propose.py, just looped over the watchlist.
Also used by the dashboard's in-process scheduler for automated daily refreshes.

Usage:
    .venv/bin/python run_watchlist.py [YYYY-MM-DD]
"""

import json
import shutil
import sys
from datetime import date
from pathlib import Path

from proposal_runner import DATA_DIR, run_proposal
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

_DEFAULT_WATCHLIST = Path(__file__).parent / "watchlist.json"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"


def _ensure_watchlist() -> list[str]:
    """Seed DATA_DIR/watchlist.json from the repo default on first run."""
    if not WATCHLIST_PATH.exists():
        WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_DEFAULT_WATCHLIST, WATCHLIST_PATH)
    return json.loads(WATCHLIST_PATH.read_text())


def refresh_watchlist(trade_date: str | None = None) -> int:
    """Run a proposal for every watchlist ticker. Returns the count refreshed."""
    trade_date = trade_date or date.today().isoformat()
    watchlist = _ensure_watchlist()

    config = DEFAULT_CONFIG.copy()
    ta = TradingAgentsGraph(debug=False, config=config)

    for ticker in watchlist:
        try:
            run_proposal(ta, ticker, trade_date)
        except Exception as exc:
            print(f"Skipping {ticker}: {exc}")
        print()

    print(f"Refreshed {len(watchlist)} tickers for {trade_date}.")
    return len(watchlist)


if __name__ == "__main__":
    trade_date = sys.argv[1] if len(sys.argv) > 1 else None
    refresh_watchlist(trade_date)
