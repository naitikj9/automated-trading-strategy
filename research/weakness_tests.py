"""Test fixes for the weaknesses found by five_year_study.py, without touching the live config.

    A. drop the EMA 20 reclaim entry (weakest rule: profit factor 1.2)
    B. trailing exit: once a trade is up `trail_after` or more, exit on a close below EMA 20 instead of EMA 50
       (winners gave back more than half their peak gain)
    A+B together

Each variant is judged on 2018-2023 (train) and 2024 onwards (test), all stocks and 10 slots.

    python research/weakness_tests.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "strategy_2_pullback"))

from index_study import COSTS, TEST, TRAIN, UNIVERSES, load_universe  # noqa: E402
from portfolio import simulate  # noqa: E402
from trading.backtest.metrics import max_drawdown, sharpe  # noqa: E402
from trading.indicators import ema  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402

COST = COSTS["commission_pct"] + COSTS["slippage_pct"]
PERIODS = {"train": TRAIN, "test": TEST}


def trail(df: pd.DataFrame, after: float, length: int = 20) -> pd.Series:
    """Position with a tighter exit once the trade is `after` in profit; the next fresh entry starts over."""
    pos = df["position"].to_numpy().copy()
    close = df["close"].to_numpy()
    fast = ema(df["close"], length).to_numpy()
    entry, armed, out = None, False, False
    for t in range(len(pos)):
        if pos[t] == 1 and (t == 0 or df["position"].iloc[t - 1] == 0):
            entry, armed, out = close[t], False, False
        if df["position"].iloc[t] == 0:
            entry, out = None, False
            continue
        if out:
            pos[t] = 0
            continue
        if entry is not None and close[t] >= entry * (1 + after):
            armed = True
        if armed and close[t] < fast[t]:
            pos[t], out = 0, True
    return pd.Series(pos, index=df.index)


def stats(rets: pd.Series, window) -> dict:
    r = rets.loc[window[0]:window[1]]
    equity = (1 + r).cumprod()
    return {"cagr": equity.iloc[-1] ** (252 / len(r)) - 1, "sharpe": sharpe(r), "max_dd": max_drawdown(equity)}


def main():
    with open(ROOT / "config" / "config.yaml") as f:
        live = yaml.safe_load(f)["strategy"]["params"]
    variants = {
        "live": (live, None),
        "A no reclaim": ({**live, "ema_reclaim_reentry": False}, None),
        "B trail +20%": (live, 0.20),
        "B trail +30%": (live, 0.30),
        "B trail +50%": (live, 0.50),
        "A+B trail +30%": ({**live, "ema_reclaim_reentry": False}, 0.30),
    }
    rows = []
    for uname in UNIVERSES:
        universe = load_universe(uname)
        for vname, (params, after) in variants.items():
            strategy = get_strategy("dmi_macd", **params)
            frames = {}
            for s, d in universe.items():
                df = strategy.analyze(d)[["close", "adx", "position"]].copy()
                if after is not None:
                    df["position"] = trail(df, after)
                frames[s] = df
            for slots in (None, 10):
                rets, _ = simulate(frames, slots or len(frames), COST)
                for period, window in PERIODS.items():
                    rows.append({"universe": uname, "variant": vname, "slots": slots or "all", "period": period,
                                 **stats(rets, window)})
            print(f"{uname} {vname} done", flush=True)
    table = pd.DataFrame(rows)
    out = ROOT / "results" / "five_year" / "weakness_tests.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)
    pd.set_option("display.width", 220)
    view = table.pivot_table(index=["slots", "variant"], columns=["period", "universe"], values=["cagr", "sharpe"])
    print(view.round(3).to_string())
    print("\nmax drawdown, test")
    print(table[table["period"] == "test"].pivot_table(index=["slots", "variant"], columns="universe",
                                                        values="max_dd").round(3).to_string())


if __name__ == "__main__":
    main()
