"""Tune the DMI + MACD strategy on Nifty 50 stocks, then test it on years it never saw.

Train: 2018-2023 (parameter grid search)
Test:  2024 onwards (best train settings vs defaults vs buy-and-hold)

Each stock gets an equal share of capital; idle capital earns nothing.
"""
from __future__ import annotations

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

# Current constituents, so older years carry survivorship bias.
NIFTY50 = """ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO BAJFINANCE BAJAJFINSV BEL
BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT ETERNAL GRASIM HCLTECH HDFCBANK HDFCLIFE HEROMOTOCO
HINDALCO HINDUNILVR ICICIBANK INDUSINDBK INFY ITC JIOFIN JSWSTEEL KOTAKBANK LT M&M MARUTI
NESTLEIND NTPC ONGC POWERGRID RELIANCE SBILIFE SBIN SHRIRAMFIN SUNPHARMA TATACONSUM TATAMOTORS
TATASTEEL TCS TECHM TITAN TRENT ULTRACEMCO WIPRO""".split()

DATA_START = "2017-01-01"  # one warm-up year before training starts
TRAIN = ("2018-01-01", "2023-12-31")
TEST = ("2024-01-01", None)
COSTS = {"commission_pct": 0.0003, "slippage_pct": 0.0005}

GRID = {
    "adx_min": [0, 20, 25],
    "min_strength": [1, 2, 3],
    "exit_ema": [20, 50, None],
    "macd_lookback": [3, 5],
}

CACHE = ROOT / "data" / "cache"
RESULTS = ROOT / "results"


def load_universe() -> dict[str, pd.DataFrame]:
    CACHE.mkdir(parents=True, exist_ok=True)
    universe = {}
    for name in NIFTY50:
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
            universe[name] = data
    return universe


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
    universe = load_universe()
    print(f"{len(universe)} stocks loaded\n")
    RESULTS.mkdir(exist_ok=True)

    rows = []
    for values in itertools.product(*GRID.values()):
        params = dict(zip(GRID, values))
        rows.append({**params, **evaluate(universe, params, TRAIN)})
    grid = pd.DataFrame(rows).sort_values("sharpe", ascending=False)
    grid.to_csv(RESULTS / "grid_train.csv", index=False)
    print("Top 10 settings on TRAIN (2018-2023), by Sharpe:")
    print(grid.head(10).round(3).to_string(index=False))

    best = {k: grid.iloc[0][k] for k in GRID}
    best = {k: (None if pd.isna(v) else int(v)) for k, v in best.items()}
    candidates = {"defaults": {}, "tuned": best}

    summary = []
    for label, window in (("train", TRAIN), ("test", TEST)):
        for name, params in candidates.items():
            summary.append({"period": label, "model": name, **evaluate(universe, params, window)})
        summary.append({"period": label, "model": "buy & hold", **portfolio_stats(buy_hold_returns(universe, window)),
                        "time_in_market": 1.0, "beats_bh_pct": np.nan})
    summary = pd.DataFrame(summary)
    summary.to_csv(RESULTS / "summary.csv", index=False)
    print(f"\nTuned settings: {best}\n")
    print(summary.round(3).to_string(index=False))

    plot_test_equity(universe, candidates)


def plot_test_equity(universe, candidates):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    curves = {name: strategy_returns(universe, params, TEST)[0] for name, params in candidates.items()}
    curves["buy & hold"] = buy_hold_returns(universe, TEST)
    for name, rets in curves.items():
        ax.plot((1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod(), label=name)
    ax.set_title("Nifty 50 equal-weight portfolio, unseen test period (2024 onwards)")
    ax.set_ylabel("Growth of 1")
    ax.grid(alpha=0.3)
    ax.legend()
    out = ROOT / "docs" / "test_equity.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    print(f"\nChart saved to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
