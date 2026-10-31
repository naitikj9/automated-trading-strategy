"""Tune the DMI + MACD strategy on an NSE index, then test it on years it never saw.

Train: 2018-2023 (parameter grid search)
Test:  2024 onwards (best train settings vs defaults vs buy-and-hold)

Each stock gets an equal share of capital; idle capital earns nothing.

    python research/index_study.py --universe midcap100
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading.backtest.engine import run_backtest  # noqa: E402
from trading.backtest.metrics import max_drawdown, sharpe  # noqa: E402
from trading.data.loader import load_yfinance  # noqa: E402
from trading.strategies import DMIMACDStrategy  # noqa: E402

# Constituent lists published by NSE. They are today's members, so older years carry survivorship bias.
UNIVERSES = {
    "nifty50": "ind_nifty50list",
    "midcap100": "ind_niftymidcap100list",
    "smallcap100": "ind_niftysmallcap100list",
}
NSE_LIST_URL = "https://archives.nseindia.com/content/indices/{}.csv"

DATA_START = "2017-01-01"  # one warm-up year before training starts
TRAIN = ("2018-01-01", "2023-12-31")
TEST = ("2024-01-01", None)
COSTS = {"commission_pct": 0.0003, "slippage_pct": 0.0005}

GRID = {
    "adx_min": [0, 15, 25],
    "require_pattern": [False, True],
    "di_cross_reentry": [False, True],
    "ema_reclaim_reentry": [False, True],
    "exit_on_di_cross": [True, False],
}
BOOL_PARAMS = {"require_pattern", "di_cross_reentry", "ema_reclaim_reentry", "exit_on_di_cross"}

CACHE = ROOT / "data" / "cache"


def constituents(universe: str) -> list[str]:
    path = CACHE / f"{UNIVERSES[universe]}.csv"
    if not path.exists():
        import urllib.request

        CACHE.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(NSE_LIST_URL.format(UNIVERSES[universe]), headers={"User-Agent": "Mozilla/5.0"})
        path.write_bytes(urllib.request.urlopen(request, timeout=30).read())
    return pd.read_csv(path)["Symbol"].tolist()


def load_universe(universe: str) -> dict[str, pd.DataFrame]:
    CACHE.mkdir(parents=True, exist_ok=True)
    loaded = {}
    for name in constituents(universe):
        path = CACHE / f"{name}.csv"
        if path.exists():
            data = pd.read_csv(path, index_col=0, parse_dates=True)
        else:
            try:
                data = load_yfinance(f"{name}.NS", DATA_START)
            except Exception as exc:  # delisted or renamed symbols
                print(f"skip {name}: {exc}")
                continue
            data.to_csv(path)
        if len(data) > 250:
            loaded[name] = data
    return loaded


def portfolio_stats(daily: pd.DataFrame) -> dict:
    """Equal-weight portfolio across the stocks that were listed on each day."""
    returns = daily.mean(axis=1, skipna=True).fillna(0)
    equity = (1 + returns).cumprod()
    years = len(returns) / 252
    return {
        "cagr": equity.iloc[-1] ** (1 / years) - 1,
        "sharpe": sharpe(returns),
        "max_dd": max_drawdown(equity),
    }


def strategy_returns(universe, params, window) -> tuple[pd.DataFrame, pd.DataFrame]:
    strategy = DMIMACDStrategy(**params)
    rets, exposure = {}, {}
    for name, data in universe.items():
        result = run_backtest(data, strategy.generate_signals(data), **COSTS)
        rets[name] = result.returns.loc[window[0]:window[1]]
        exposure[name] = (result.positions != 0).loc[window[0]:window[1]]
    return pd.DataFrame(rets), pd.DataFrame(exposure)


def buy_hold_returns(universe, window) -> pd.DataFrame:
    return pd.DataFrame({n: d["close"].pct_change() for n, d in universe.items()}).loc[window[0]:window[1]]


def evaluate(universe, params, window) -> dict:
    rets, exposure = strategy_returns(universe, params, window)
    stock_bh = buy_hold_returns(universe, window)
    per_stock_win = ((1 + rets).prod() > (1 + stock_bh.fillna(0)).prod()).mean()
    return {**portfolio_stats(rets), "time_in_market": exposure.mean().mean(), "beats_bh_pct": per_stock_win}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=UNIVERSES, default="nifty50")
    name = parser.parse_args().universe

    universe = load_universe(name)
    print(f"{name}: {len(universe)} stocks loaded\n")
    results = ROOT / "results" / name
    results.mkdir(parents=True, exist_ok=True)

    rows = []
    for values in itertools.product(*GRID.values()):
        params = dict(zip(GRID, values))
        rows.append({**params, **evaluate(universe, params, TRAIN)})
    grid = pd.DataFrame(rows).sort_values("sharpe", ascending=False)
    grid.to_csv(results / "grid_train.csv", index=False)
    print("Top 10 settings on TRAIN (2018-2023), by Sharpe:")
    print(grid.head(10).round(3).to_string(index=False))

    best = {k: grid.iloc[0][k] for k in GRID}
    best = {k: (None if pd.isna(v) else bool(v) if k in BOOL_PARAMS else int(v)) for k, v in best.items()}
    candidates = {"defaults": {}, "tuned": best}

    summary = []
    for label, window in (("train", TRAIN), ("test", TEST)):
        for model, params in candidates.items():
            summary.append({"period": label, "model": model, **evaluate(universe, params, window)})
        summary.append({"period": label, "model": "buy & hold", **portfolio_stats(buy_hold_returns(universe, window)),
                        "time_in_market": 1.0, "beats_bh_pct": np.nan})
    summary = pd.DataFrame(summary)
    summary.to_csv(results / "summary.csv", index=False)
    print(f"\nTuned settings: {best}\n")
    print(summary.round(3).to_string(index=False))

    plot_test_equity(universe, candidates, name)


def plot_test_equity(universe, candidates, name):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    curves = {model: strategy_returns(universe, params, TEST)[0] for model, params in candidates.items()}
    curves["buy & hold"] = buy_hold_returns(universe, TEST)
    for model, rets in curves.items():
        ax.plot((1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod(), label=model)
    ax.set_title(f"{name} equal-weight portfolio, unseen test period (2024 onwards)")
    ax.set_ylabel("Growth of 1")
    ax.grid(alpha=0.3)
    ax.legend()
    out = ROOT / "docs" / f"test_equity_{name}.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    print(f"\nChart saved to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
