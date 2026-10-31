"""Sanity checks on the live config: no lookahead, and no rules fighting each other.

1. Lookahead: run the strategy on history cut at several dates and compare with the full run.
   If any signal up to the cut changes once later bars exist, the strategy peeked at the future.
2. Contradictions, over every trade in the chosen universe:
   - long entered while -DI was above +DI (DMI, the main indicator, said sellers were in control)
   - long entered below EMA 50 (the exit rule would close it at once)
   - trade held for only one bar (entered and exited on consecutive bars)

    python research/audit.py --universe smallcap100
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research"))

from index_study import UNIVERSES, load_universe  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402

CHECK_COLUMNS = ["long_setup", "short_setup", "bull_pattern", "bear_pattern", "position"]


def lookahead_failures(strategy, data: pd.DataFrame, cuts: int = 6) -> list[str]:
    full = strategy.analyze(data)
    failures = []
    for cut in np.linspace(300, len(data) - 1, cuts).astype(int):
        part = strategy.analyze(data.iloc[:cut])
        for col in CHECK_COLUMNS:
            a, b = full[col].iloc[:cut], part[col]
            if not a.equals(b):
                first = a.index[(a != b).to_numpy()][0]
                failures.append(f"{col} differs at {first.date()} when history is cut at {data.index[cut - 1].date()}")
    return failures


def contradictions(strategy, data: pd.DataFrame) -> pd.DataFrame:
    df = strategy.analyze(data)
    pos = df["position"]
    entries = df.index[(pos == 1) & (pos.shift(1) == 0)]
    rows = []
    for t in entries:
        i = df.index.get_loc(t)
        held = 0
        while i + held + 1 < len(df) and pos.iloc[i + held + 1] == 1:
            held += 1
        row = df.loc[t]
        rows.append({
            "date": t, "reason": row["long_reason"],
            "di_bearish": row["minus_di"] > row["plus_di"],
            "below_ema50": row["close"] < row["ema_slow"],
            "one_bar": held == 0,
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=UNIVERSES, default="smallcap100")
    parser.add_argument("--lookahead-stocks", type=int, default=15)
    name = parser.parse_args().universe
    args = parser.parse_args()

    with open(ROOT / "config" / "config.yaml") as f:
        params = yaml.safe_load(f)["strategy"]["params"]
    # switch every optional rule on, so the lookahead check covers all the code paths
    all_on = {**params, "poc_filter": True, "poc_retest_entry": True, "accumulation_breakout": True,
              "ema_cross_entry": True, "exit_on_divergence": True, "allow_short": True}
    universe = load_universe(name)

    print(f"Lookahead check on {args.lookahead_stocks} stocks, every optional rule on")
    bad = 0
    for sym in list(universe)[:args.lookahead_stocks]:
        failures = lookahead_failures(get_strategy("dmi_macd", **all_on), universe[sym])
        if failures:
            bad += 1
            print(f"  {sym}: {failures[0]}")
    print(f"  {'no lookahead found' if not bad else f'{bad} stocks changed'}\n")

    strategy = get_strategy("dmi_macd", **params)
    trades = pd.concat([contradictions(strategy, d).assign(symbol=s) for s, d in universe.items()], ignore_index=True)
    print(f"Contradiction check, live config, {len(trades)} long entries in {name}")
    for col, label in (("di_bearish", "entered while -DI > +DI"), ("below_ema50", "entered below EMA 50"),
                       ("one_bar", "held one bar only")):
        hit = trades[trades[col]]
        print(f"  {label:26} {len(hit):5d} ({len(hit) / len(trades):.1%})")
        if len(hit):
            print("    by rule: " + ", ".join(f"{k} {v}" for k, v in hit["reason"].value_counts().head(4).items()))


if __name__ == "__main__":
    main()
