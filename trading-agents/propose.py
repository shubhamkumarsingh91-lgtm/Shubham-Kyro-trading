"""Run TradingAgents for a ticker and print a proposed decision for manual review.

This script never places an order. It only prints and logs what the multi-agent
debate concluded (Buy / Overweight / Hold / Underweight / Sell) plus the
reasoning behind it. Reviewing the proposal and deciding whether to act on it,
and actually submitting any order, is on you.

Usage:
    .venv/bin/python propose.py TICKER [YYYY-MM-DD]
"""

import sys
from datetime import date

from proposal_runner import run_proposal
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


def main():
    if len(sys.argv) < 2:
        print("Usage: python propose.py TICKER [YYYY-MM-DD]")
        sys.exit(1)

    ticker = sys.argv[1]
    trade_date = sys.argv[2] if len(sys.argv) > 2 else date.today().isoformat()

    config = DEFAULT_CONFIG.copy()
    ta = TradingAgentsGraph(debug=False, config=config)
    run_proposal(ta, ticker, trade_date)


if __name__ == "__main__":
    main()
