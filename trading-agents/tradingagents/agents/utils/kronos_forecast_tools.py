import sys
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

_KRONOS_DIR = Path(__file__).resolve().parents[4] / "kronos-model"
sys.path.insert(0, str(_KRONOS_DIR))


@tool
def get_kronos_forecast(
    symbol: Annotated[str, "ticker symbol of the company"],
) -> str:
    """
    Get a quantitative price forecast from Kronos, a foundation model trained
    specifically on candlestick (OHLCV) data across 45+ global exchanges.
    Unlike indicator analysis, this is an actual model prediction of future
    prices, not an interpretation of past ones. Use it as one input among
    several, not as a standalone signal.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
    Returns:
        str: The predicted close price path over the next 5 trading days,
        the total predicted % change, and a direction label.
    """
    from forecast import forecast  # local import: only needed when this tool runs

    result = forecast(symbol)
    path = ", ".join(f"${c:.2f}" for c in result["predicted_closes"])
    return (
        f"Kronos forecast for {result['ticker']} (last close ${result['last_close']:.2f}):\n"
        f"Predicted close path over next {len(result['predicted_closes'])} trading days: {path}\n"
        f"Total predicted change: {result['pct_change']:+.2f}% ({result['direction']})"
    )
