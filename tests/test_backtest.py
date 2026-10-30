import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from trading.backtest.engine import run_backtest  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402


def make_data(n=300):
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    rets = np.random.default_rng(0).normal(0.0005, 0.01, n)
    close = pd.Series(100 * np.cumprod(1 + rets), index=idx)
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": 1000})


def test_flat_signal_keeps_capital():
    data = make_data()
    res = run_backtest(data, pd.Series(0, index=data.index), initial_capital=1000)
    assert res.equity.iloc[-1] == 1000
    assert res.stats["trades"] == 0


def test_always_long_matches_buy_and_hold():
    data = make_data()
    res = run_backtest(data, pd.Series(1, index=data.index), initial_capital=1000)
    # Signal on bar 0 is acted on at bar 1, so the hold starts from close[0].
    expected = 1000 * data["close"].iloc[-1] / data["close"].iloc[0]
    assert np.isclose(res.equity.iloc[-1], expected)


def test_no_lookahead():
    data = make_data()
    signals = get_strategy("sma_crossover", fast=5, slow=20).generate_signals(data)
    res = run_backtest(data, signals)
    assert (res.positions == signals.shift(1).fillna(0)).all()


def test_costs_reduce_returns():
    data = make_data()
    signals = get_strategy("sma_crossover", fast=5, slow=20).generate_signals(data)
    free = run_backtest(data, signals).equity.iloc[-1]
    costly = run_backtest(data, signals, commission_pct=0.001).equity.iloc[-1]
    assert costly < free
