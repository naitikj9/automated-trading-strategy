"""Can a market filter and concentrated capital lift strategy 2's returns?

For each index: every stock runs strategy 2 (and strategy 1, for comparison) on its own, then the
portfolio layer (portfolio.py) decides which entries get capital. Grid: slots x minimum breadth.
The setup is chosen on 2018-2023 only, then shown on 2024-2026 and on the last year.

    python strategy_2_pullback/improve.py
"""
from __future__ import annotations

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
sys.path.insert(0, str(HERE))

from index_study import COSTS, TEST, TRAIN, UNIVERSES, load_universe  # noqa: E402
from portfolio import breadth, simulate  # noqa: E402
from trading.backtest.metrics import max_drawdown, sharpe  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402

LAST_YEAR = ("2025-10-31", None)
PERIODS = {"train": TRAIN, "test": TEST, "last year": LAST_YEAR}
SLOTS = [5, 10, 20, None]          # None = one slot per stock, as in the plain backtests
MIN_BREADTH = [0.0, 0.4, 0.5, 0.6]
COST = COSTS["commission_pct"] + COSTS["slippage_pct"]


def stats(rets: pd.Series, trades: pd.DataFrame, window) -> dict:
    r = rets.loc[window[0]:window[1]]
    equity = (1 + r).cumprod()
    t = trades[(trades["entry"] >= pd.Timestamp(window[0]))
               & ((trades["entry"] <= pd.Timestamp(window[1])) if window[1] else True)]["ret"]
    wins, losses = t[t > 0], t[t <= 0]
    return {
        "cagr": equity.iloc[-1] ** (252 / len(r)) - 1,
        "sharpe": sharpe(r),
        "max_dd": max_drawdown(equity),
        "trades": len(t),
        "win_rate": len(wins) / len(t) if len(t) else np.nan,
        "avg_win": wins.mean(),
        "avg_loss": losses.mean(),
    }


def frames_for(universe: dict, name: str, params: dict) -> dict:
    strategy = get_strategy(name, **params)
    return {s: strategy.analyze(d)[["close", "adx", "position"]] for s, d in universe.items()}


def main():
    with open(ROOT / "config" / "config.yaml") as f:
        live = yaml.safe_load(f)["strategy"]["params"]
    with open(HERE / "config.yaml") as f:
        pullback = yaml.safe_load(f)["strategy"]["params"]

    rows = []
    for uname in UNIVERSES:
        universe = load_universe(uname)
        market = breadth(pd.DataFrame({s: d["close"] for s, d in universe.items()}))
        for label, name, params in (("1", "dmi_macd", live), ("2", "dmi_pullback", pullback)):
            frames = frames_for(universe, name, params)
            for slots, min_b in itertools.product(SLOTS, MIN_BREADTH):
                rets, trades = simulate(frames, slots or len(frames), COST, market, min_b)
                for period, window in PERIODS.items():
                    rows.append({"universe": uname, "strategy": label, "slots": slots or "all",
                                 "min_breadth": min_b, "period": period, **stats(rets, trades, window)})
            print(f"{uname} strategy {label} done", flush=True)
    table = pd.DataFrame(rows)
    out = ROOT / "results" / "pullback_improve.csv"
    out.parent.mkdir(exist_ok=True)
    table.to_csv(out, index=False)

    train = table[table["period"] == "train"]
    pick = train.groupby(["strategy", "slots", "min_breadth"])[["cagr", "sharpe", "max_dd"]].mean()
    pd.set_option("display.width", 200)
    print("\nTrain 2018-2023, mean of the three indices")
    print(pick.round(3).sort_values("sharpe", ascending=False).to_string())


if __name__ == "__main__":
    main()
