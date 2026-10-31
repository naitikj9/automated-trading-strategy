"""Which rules earn their place? Flip each rule in config/config.yaml one at a time and measure the change.

Each variant is scored on the train years and on the unseen test years, so a rule that only helps
in hindsight shows up as a train gain without a test gain.

    python research/rule_ablation.py --universe smallcap100
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "research"))

from index_study import TEST, TRAIN, UNIVERSES, buy_hold_returns, evaluate, load_universe, portfolio_stats  # noqa: E402

FLIPS = {
    "ADX floor 15 -> 0": {"adx_min": 0},
    "require MACD pattern": {"require_pattern": True},
    "no +DI cross re-entry": {"di_cross_reentry": False},
    "no EMA 20 reclaim re-entry": {"ema_reclaim_reentry": False},
    "no EMA 20 pullback entry": {"ema_pullback_entry": False},
    "accumulation breakout entry": {"accumulation_breakout": True},
    "skip re-entries inside base": {"skip_inside_base": True},
    "POC filter": {"poc_filter": True},
    "POC retest entry": {"poc_retest_entry": True},
    "exit on EMA 50 only (no DI exit)": {"exit_on_di_cross": False},
    "allow shorts": {"allow_short": True},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=UNIVERSES, default="smallcap100")
    name = parser.parse_args().universe

    with open(ROOT / "config" / "config.yaml") as f:
        base = yaml.safe_load(f)["strategy"]["params"]
    universe = load_universe(name)
    print(f"{name}: {len(universe)} stocks\n")

    rows = []
    for label, change in {"config as is": {}, **FLIPS}.items():
        params = {**base, **change}
        row = {"variant": label}
        for period, window in (("train", TRAIN), ("test", TEST)):
            stats = evaluate(universe, params, window)
            row.update({f"{period}_cagr": stats["cagr"], f"{period}_sharpe": stats["sharpe"],
                        f"{period}_dd": stats["max_dd"]})
        rows.append(row)
        print(f"  done: {label}")
    for period, window in (("train", TRAIN), ("test", TEST)):
        bh = portfolio_stats(buy_hold_returns(universe, window))
        rows[0].update({f"bh_{period}_sharpe": bh["sharpe"]})

    table = pd.DataFrame(rows).set_index("variant")
    base_row = table.loc["config as is"]
    table["d_train_sharpe"] = table["train_sharpe"] - base_row["train_sharpe"]
    table["d_test_sharpe"] = table["test_sharpe"] - base_row["test_sharpe"]
    out = ROOT / "results" / name
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "ablation.csv")

    cols = ["train_cagr", "train_sharpe", "test_cagr", "test_sharpe", "test_dd", "d_train_sharpe", "d_test_sharpe"]
    print()
    print(table[cols].round(3).to_string())
    print(f"\nbuy & hold sharpe: train {base_row['bh_train_sharpe']:.2f}, test {base_row['bh_test_sharpe']:.2f}")


if __name__ == "__main__":
    main()
