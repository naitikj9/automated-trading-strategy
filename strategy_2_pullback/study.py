"""Strategy 2 (dmi_pullback) against strategy 1 (dmi_macd, the live config), on three NSE indices.

    python strategy_2_pullback/study.py            # compare, using strategy_2_pullback/config.yaml
    python strategy_2_pullback/study.py --grid     # tune target / stop / exit on 2018-2023 first

Periods: train 2018-2023, test 2024 onwards (unseen), and the last year on its own.
Both run daily bars only; strategy 1's 1-hour re-entries are left out so the two compare like for like.
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).parents[1]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research"))

from index_study import COSTS, TEST, TRAIN, UNIVERSES, load_universe, portfolio_stats  # noqa: E402
from trading.backtest.engine import run_backtest  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402

LAST_YEAR = ("2025-10-31", None)
GRID = {
    "adx_min": [15, 20],
    "oversold": [30, 40],
    "target_atr": [1.0, 1.5, 2.0, 3.0],
    "stop_atr": [1.5, 2.0, 3.0],
    "exit_on_overbought": [True, False],
}


def trade_returns(positions: pd.Series, close: pd.Series, window) -> list[float]:
    """Net return of every trade opened inside the window; positions are decided at each close."""
    pos = positions.to_numpy()
    c = close.to_numpy()
    start = close.index.searchsorted(pd.Timestamp(window[0]))
    end = len(c) if window[1] is None else close.index.searchsorted(pd.Timestamp(window[1]), side="right")
    cost = 2 * (COSTS["commission_pct"] + COSTS["slippage_pct"])
    out, entry = [], None
    for i in range(max(start, 1), len(c)):
        if entry is None and pos[i] == 1 and pos[i - 1] == 0 and i < end:
            entry = c[i]
        elif entry is not None and pos[i] == 0:
            out.append(c[i] / entry - 1 - cost)
            entry = None
    if entry is not None:
        out.append(c[-1] / entry - 1 - cost)
    return out


def evaluate(universe: dict, name: str, params: dict, window) -> dict:
    strategy = get_strategy(name, **params)
    rets, exposure, trades = {}, {}, []
    for data in universe.values():
        signals = strategy.generate_signals(data)
        result = run_backtest(data, signals, **COSTS)
        rets[len(rets)] = result.returns.loc[window[0]:window[1]]
        exposure[len(exposure)] = (result.positions != 0).loc[window[0]:window[1]].mean()
        trades += trade_returns(signals, data["close"], window)
    t = pd.Series(trades, dtype=float)
    wins, losses = t[t > 0], t[t <= 0]
    return {
        **portfolio_stats(pd.DataFrame(rets)),
        "in_market": float(np.nanmean(list(exposure.values()))),
        "trades": len(t),
        "win_rate": len(wins) / len(t) if len(t) else np.nan,
        "avg_win": wins.mean(),
        "avg_loss": losses.mean(),
        "profit_factor": wins.sum() / -losses.sum() if losses.sum() else np.inf,
    }


def grid(universes: dict, base: dict) -> pd.DataFrame:
    rows = []
    for values in itertools.product(*GRID.values()):
        change = dict(zip(GRID, values))
        row = dict(change)
        for uname, uni in universes.items():
            stats = evaluate(uni, "dmi_pullback", {**base, **change}, TRAIN)
            row[f"{uname}_sharpe"], row[f"{uname}_win"] = stats["sharpe"], stats["win_rate"]
        row["mean_sharpe"] = np.mean([row[f"{u}_sharpe"] for u in universes])
        row["mean_win"] = np.mean([row[f"{u}_win"] for u in universes])
        rows.append(row)
        print(change, f"sharpe {row['mean_sharpe']:.2f} win {row['mean_win']:.0%}", flush=True)
    return pd.DataFrame(rows).sort_values("mean_sharpe", ascending=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid", action="store_true")
    args = parser.parse_args()
    with open(ROOT / "config" / "config.yaml") as f:
        live = yaml.safe_load(f)["strategy"]["params"]
    with open(HERE / "config.yaml") as f:
        pullback = yaml.safe_load(f)["strategy"]["params"]
    universes = {u: load_universe(u) for u in UNIVERSES}

    if args.grid:
        table = grid(universes, pullback)
        out = ROOT / "results" / "pullback_grid.csv"
        out.parent.mkdir(exist_ok=True)
        table.to_csv(out, index=False)
        print(table.round(3).head(10).to_string(index=False))
        return

    rows = []
    for uname, uni in universes.items():
        for label, name, params in (("1: dmi_macd", "dmi_macd", live), ("2: dmi_pullback", "dmi_pullback", pullback)):
            for period, window in (("train", TRAIN), ("test", TEST), ("last year", LAST_YEAR)):
                rows.append({"universe": uname, "strategy": label, "period": period,
                             **evaluate(uni, name, params, window)})
    table = pd.DataFrame(rows)
    table.to_csv(ROOT / "results" / "pullback_vs_dmi_macd.csv", index=False)
    pd.set_option("display.width", 200)
    print(table.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
