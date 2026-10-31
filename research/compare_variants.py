"""Score a few named config variants side by side on train and test years.

    python research/compare_variants.py --universe smallcap100
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "research"))

from index_study import TEST, TRAIN, UNIVERSES, evaluate, load_universe  # noqa: E402

VARIANTS = {
    "config as is": {},
    "+ EMA 20/50 cross entry": {"ema_cross_entry": True},
    "+ EMA 20/50 cross exit": {"ema_cross_exit": True},
    "+ EMA 20/50 cross entry and exit": {"ema_cross_entry": True, "ema_cross_exit": True},
    "shorts on, pattern on sells": {"allow_short": True},
    "shorts on, no pattern on sells": {"allow_short": True, "require_pattern_short": False},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=UNIVERSES, default="smallcap100")
    name = parser.parse_args().universe
    with open(ROOT / "config" / "config.yaml") as f:
        base = yaml.safe_load(f)["strategy"]["params"]
    universe = load_universe(name)

    rows = []
    for label, change in VARIANTS.items():
        row = {"variant": label}
        for period, window in (("train", TRAIN), ("test", TEST)):
            stats = evaluate(universe, {**base, **change}, window)
            row.update({f"{period}_cagr": stats["cagr"], f"{period}_sharpe": stats["sharpe"], f"{period}_dd": stats["max_dd"]})
        rows.append(row)
    table = pd.DataFrame(rows).set_index("variant")
    print(f"{name}: {len(universe)} stocks")
    print(table.round(3).to_string())


if __name__ == "__main__":
    main()
