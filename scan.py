"""Daily scanner: shows the DMI + MACD reading and action for every watchlist stock."""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent / "src"))

from trading.data.loader import load_yfinance  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402
from trading.strategies.dmi_macd import STRENGTH_LABELS  # noqa: E402


def action(prev_pos: int, pos: int) -> str:
    if pos == prev_pos:
        return {1: "HOLD LONG", -1: "HOLD SHORT", 0: "-"}[pos]
    return {1: "BUY", -1: "SELL SHORT", 0: "EXIT"}[pos]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("symbols", nargs="*", help="Override the watchlist")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    strategy = get_strategy(cfg["strategy"]["name"], **cfg["strategy"]["params"])

    rows = []
    for symbol in args.symbols or cfg["watchlist"]:
        data = load_yfinance(symbol, cfg["start"], interval=cfg["interval"])
        df = strategy.analyze(data)
        last, prev = df.iloc[-1], df.iloc[-2]
        macd_side = "bull" if last["macd"] > last["signal"] else "bear"
        strength = last["bull_strength"] if macd_side == "bull" else last["bear_strength"]
        rows.append({
            "symbol": symbol,
            "date": df.index[-1].date(),
            "close": round(last["close"], 2),
            "+DI": round(last["plus_di"], 1),
            "-DI": round(last["minus_di"], 1),
            "ADX": round(last["adx"], 1),
            "ADX up": "yes" if last["adx"] > prev["adx"] else "no",
            "MACD": f"{macd_side} {STRENGTH_LABELS[int(strength)]}",
            "pattern": " | ".join(filter(None, [
                last["bull_pattern"],
                last["bear_pattern"],
                "base breakout" if last["base_breakout"] else "",
                "base breakdown" if last["base_breakdown"] else "",
                "in base" if last["in_base"] else "",
            ])) or "-",
            "action": action(int(prev["position"]), int(last["position"])),
        })
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
