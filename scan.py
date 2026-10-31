"""Daily scanner: shows the DMI + MACD reading and action for every watchlist stock.

With `hourly.enabled` in the config, the action also counts 1-hour re-entries, and the
"1h trigger" column shows when today's hourly trigger fired.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent / "src"))

from trading.data.loader import load_yfinance, load_yfinance_hourly  # noqa: E402
from trading.indicators import volume_profile  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402
from trading.strategies.dmi_macd import STRENGTH_LABELS  # noqa: E402
from trading.strategies.mtf import mtf_positions, session_dates  # noqa: E402


def action(prev_pos: int, pos: int) -> str:
    if pos == prev_pos:
        return {1: "HOLD LONG", -1: "HOLD SHORT", 0: "-"}[pos]
    return {1: "BUY", -1: "SELL SHORT", 0: "EXIT"}[pos]


def hourly_action(df: pd.DataFrame, symbol: str, hourly_cfg: dict, exit_ema: int) -> tuple[str, str] | None:
    """Action for the latest session using 1-hour re-entries, and the time of today's 1h trigger if any."""
    try:
        hourly = load_yfinance_hourly(symbol)
    except Exception:
        return None
    if len(hourly) < 100:
        return None
    m = mtf_positions(df, hourly, exit_ema=exit_ema, triggers=tuple(hourly_cfg["triggers"]))
    dates = session_dates(m.index)
    today = m[dates == dates[-1]]
    before = m[dates < dates[-1]]
    prev_pos = int(before["position"].iloc[-1]) if len(before) else 0
    fired = today.index[today["event"] == "1h trigger"]
    return action(prev_pos, int(m["position"].iloc[-1])), fired[0].strftime("%H:%M") if len(fired) else "-"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("symbols", nargs="*", help="Override the watchlist")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    strategy = get_strategy(cfg["strategy"]["name"], **cfg["strategy"]["params"])
    hourly_cfg = cfg.get("hourly", {})

    rows = []
    for symbol in args.symbols or cfg["watchlist"]:
        data = load_yfinance(symbol, cfg["start"], interval=cfg["interval"])
        df = strategy.analyze(data)
        last, prev = df.iloc[-1], df.iloc[-2]
        vp = volume_profile(data.iloc[-strategy.params["poc_lookback"]:], strategy.params["poc_bins"])
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
            "POC": round(vp["poc"], 1),
            "vs POC": f"{100 * (last['close'] / vp['poc'] - 1):+.1f}%",
            "buyers": f"{vp['buy_pct']:.0f}%",
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
        if hourly_cfg.get("enabled"):
            result = hourly_action(df, symbol, hourly_cfg, strategy.params["exit_ema"])
            rows[-1]["1h trigger"] = result[1] if result else "no 1h data"
            if result:
                rows[-1]["action"] = result[0]
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
