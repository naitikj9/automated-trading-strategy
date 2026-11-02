import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "strategy_2_pullback"))

from portfolio import breadth, simulate  # noqa: E402


def frame(position, close, adx=20.0):
    idx = pd.bdate_range("2024-01-01", periods=len(position))
    return pd.DataFrame({"position": position, "close": np.asarray(close, dtype=float), "adx": adx}, index=idx)


def test_slots_limit_entries_to_strongest_adx():
    pos = [0, 1, 1, 1, 0]
    frames = {"A": frame(pos, [100, 100, 110, 120, 120], adx=10), "B": frame(pos, [100, 100, 90, 80, 80], adx=30)}
    rets, trades = simulate(frames, slots=1, cost=0.0)
    assert list(trades["symbol"]) == ["B"]
    assert np.isclose((1 + rets).prod() - 1, -0.2)


def test_one_slot_per_stock_averages_returns():
    pos = [0, 1, 1, 0]
    frames = {"A": frame(pos, [100, 100, 110, 110]), "B": frame(pos, [100, 100, 90, 90])}
    rets, trades = simulate(frames, slots=2, cost=0.0)
    assert len(trades) == 2 and np.isclose(rets.sum(), 0.0)


def test_market_filter_blocks_entries_but_not_exits():
    frames = {"A": frame([0, 1, 1, 0], [100, 100, 110, 110])}
    weak = pd.Series(0.2, index=frames["A"].index)
    _, trades = simulate(frames, slots=1, cost=0.0, market=weak, min_breadth=0.5)
    assert trades.empty


def test_breadth_counts_listed_stocks_only():
    idx = pd.bdate_range("2024-01-01", periods=60)
    up = pd.Series(np.linspace(100, 160, 60), index=idx)
    late = up.copy()
    late.iloc[:30] = np.nan
    b = breadth(pd.DataFrame({"A": up, "B": -up + 300, "C": late}))
    assert np.isclose(b.iloc[10], 0.5) and np.isclose(b.iloc[-1], 2 / 3)
