"""Shared logic for running one TradingAgents proposal and logging it.

Used by both propose.py (single ticker, CLI) and run_watchlist.py (loops the
whole watchlist). Never places an order — only prints/logs a proposal.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
LOG_PATH = DATA_DIR / "decisions_log.jsonl"
sys.path.insert(0, str(Path(__file__).parent.parent / "kronos-model"))


def run_proposal(ta, ticker: str, trade_date: str, verbose: bool = True) -> dict:
    ticker = ticker.upper()
    if verbose:
        print(f"Running TradingAgents multi-agent analysis for {ticker} on {trade_date}...\n")

    final_state, decision = ta.propagate(ticker, trade_date)

    try:
        from forecast import forecast

        kronos_forecast = forecast(ticker)
    except Exception as exc:
        kronos_forecast = {"error": str(exc)}

    entry = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "trade_date": trade_date,
        "decision": decision,
        "kronos_forecast": kronos_forecast,
        "market_report": final_state["market_report"],
        "sentiment_report": final_state["sentiment_report"],
        "news_report": final_state["news_report"],
        "fundamentals_report": final_state["fundamentals_report"],
        "final_trade_decision": final_state["final_trade_decision"],
        "risk_judge_decision": final_state["risk_debate_state"]["judge_decision"],
    }

    if verbose:
        print("=" * 70)
        print(f"PROPOSED DECISION for {ticker} ({trade_date}): {decision}")
        print("=" * 70)
        print("\n--- Final trader reasoning ---")
        print(entry["final_trade_decision"])
        print("\n--- Risk management judge ---")
        print(entry["risk_judge_decision"])
        print(
            "\nThis is a proposal only — nothing was bought, sold, or submitted to any "
            "broker. Review it yourself before acting."
        )

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    if verbose:
        print(f"\nLogged to {LOG_PATH}")

    return entry
