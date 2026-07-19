"""Reusable Kronos price-forecast wrapper.

Loads the Kronos-small model once and exposes forecast(ticker) as a plain
function so both the TradingAgents tool and (later) the dashboard can call it
without depending on LangChain. This is the "layer 2" (forecasting) piece of
the data -> forecast -> strategy -> execution-proposal pipeline.
"""

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
from model import Kronos, KronosPredictor, KronosTokenizer  # noqa: E402

_TOKENIZER_ID = "NeoQuasar/Kronos-Tokenizer-base"
_MODEL_ID = "NeoQuasar/Kronos-small"
_MAX_CONTEXT = 512

_predictor = None


def _get_predictor() -> KronosPredictor:
    global _predictor
    if _predictor is None:
        tokenizer = KronosTokenizer.from_pretrained(_TOKENIZER_ID)
        model = Kronos.from_pretrained(_MODEL_ID)
        _predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=_MAX_CONTEXT)
    return _predictor


def forecast(ticker: str, pred_len: int = 5, lookback: int = 400) -> dict:
    """Forecast the next `pred_len` trading days of closes for `ticker`.

    Returns a dict with the last known close, the predicted close path, the
    total predicted % change, and a simple up/down/flat direction label.
    """
    history = yf.Ticker(ticker).history(period="2y", interval="1d")
    if history.empty:
        raise ValueError(f"No price history returned for {ticker!r}")

    history = history.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    history = history.tail(lookback)
    history.index = history.index.tz_localize(None)

    x_timestamp = pd.Series(history.index)
    y_timestamp = pd.Series(pd.bdate_range(start=history.index[-1], periods=pred_len + 1)[1:])

    predictor = _get_predictor()
    pred_df = predictor.predict(
        df=history.reset_index(drop=True),
        x_timestamp=x_timestamp,
        y_timestamp=y_timestamp,
        pred_len=pred_len,
        T=1.0,
        top_p=0.9,
        sample_count=1,
    )

    last_close = float(history["close"].iloc[-1])
    predicted_closes = [float(c) for c in pred_df["close"].tolist()]
    pct_change = (predicted_closes[-1] - last_close) / last_close * 100
    direction = "up" if pct_change > 0.5 else "down" if pct_change < -0.5 else "flat"

    return {
        "ticker": ticker.upper(),
        "last_close": last_close,
        "predicted_dates": [d.strftime("%Y-%m-%d") for d in y_timestamp],
        "predicted_closes": predicted_closes,
        "pct_change": round(pct_change, 2),
        "direction": direction,
    }


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    result = forecast(ticker)
    print(f"Kronos forecast for {result['ticker']}:")
    print(f"  Last close: ${result['last_close']:.2f}")
    print(f"  Predicted path: {[round(c, 2) for c in result['predicted_closes']]}")
    print(f"  Total change over {len(result['predicted_closes'])} trading days: {result['pct_change']:+.2f}% ({result['direction']})")
