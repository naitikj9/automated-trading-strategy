"""Walk through every trade the strategy took on one symbol: why it entered, why it exited, and the P&L.

    python research/trade_example.py LAURUSLABS.NS --start 2026-01-01

Prints a trade log and saves docs/example_<symbol>.png with entries, exits, EMAs, POC, DMI and MACD.
Trades are priced at the signal day's close, which is what the backtester assumes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading.data.loader import load_yfinance  # noqa: E402
from trading.indicators import market_profile, volume_profile  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402


def exit_reason(row: pd.Series, side: int, exit_ema: float) -> str:
    if side == 1:
        return "-DI crossed above +DI" if row["minus_di"] > row["plus_di"] else f"close below EMA {exit_ema}"
    return "+DI crossed above -DI" if row["plus_di"] > row["minus_di"] else f"close above EMA {exit_ema}"


def trade_log(df: pd.DataFrame, exit_ema: int) -> pd.DataFrame:
    trades, open_trade = [], None
    pos = df["position"]
    for t, (prev, cur) in zip(df.index[1:], zip(pos.iloc[:-1], pos.iloc[1:])):
        row = df.loc[t]
        if open_trade and cur != prev:
            side = open_trade["side"]
            pnl = side * (row["close"] / open_trade["entry_price"] - 1)
            trades.append({**open_trade, "exit_date": t.date(), "exit_price": row["close"],
                           "exit_reason": exit_reason(row, side, exit_ema), "return_%": 100 * pnl})
            open_trade = None
        if cur != 0 and cur != prev:
            open_trade = {"side": cur, "entry_date": t.date(), "entry_price": row["close"],
                          "entry_reason": row["long_reason"] if cur == 1 else row["short_reason"],
                          "adx": row["adx"], "+di": row["plus_di"], "-di": row["minus_di"]}
    if open_trade:
        last = df.iloc[-1]
        trades.append({**open_trade, "exit_date": "open", "exit_price": last["close"], "exit_reason": "still open",
                       "return_%": 100 * open_trade["side"] * (last["close"] / open_trade["entry_price"] - 1)})
    return pd.DataFrame(trades)


def plot(df: pd.DataFrame, trades: pd.DataFrame, symbol: str, vp: dict, mp: dict, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax, ax_dmi, ax_macd) = plt.subplots(3, 1, figsize=(12, 9), sharex=True,
                                              gridspec_kw={"height_ratios": [3, 1, 1]})
    ax.plot(df.index, df["close"], color="black", lw=1, label="close")
    ax.plot(df.index, df["ema_fast"], color="tab:blue", lw=1, label="EMA 20")
    ax.plot(df.index, df["ema_slow"], color="tab:green", lw=1, label="EMA 50")
    ax.axhline(vp["poc"], color="gold", lw=1.5, ls="--", label=f"volume POC {vp['poc']:.0f}")
    ax.axhline(mp["poc"], color="purple", lw=1, ls=":", label=f"TPO POC {mp['poc']:.0f}")
    for _, tr in trades.iterrows():
        entry = pd.Timestamp(tr["entry_date"])
        long = tr["side"] == 1
        ax.scatter(entry, tr["entry_price"], marker="^" if long else "v", s=120, zorder=5,
                   color="green" if long else "red")
        ax.annotate(f"{'BUY' if long else 'SELL'} {tr['entry_price']:.0f}", (entry, tr["entry_price"]),
                    textcoords="offset points", xytext=(0, -18 if long else 12), ha="center", fontsize=8)
        if tr["exit_date"] != "open":
            ex = pd.Timestamp(tr["exit_date"])
            ax.scatter(ex, tr["exit_price"], marker="x", s=90, color="black", zorder=5)
            ax.annotate(f"EXIT {tr['exit_price']:.0f}\n{tr['return_%']:+.1f}%", (ex, tr["exit_price"]),
                        textcoords="offset points", xytext=(0, 12), ha="center", fontsize=8)
    ax.set_title(f"{symbol}: DMI + MACD strategy trades")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)

    ax_dmi.plot(df.index, df["plus_di"], color="tab:blue", lw=1, label="+DI")
    ax_dmi.plot(df.index, df["minus_di"], color="tab:orange", lw=1, label="-DI")
    ax_dmi.plot(df.index, df["adx"], color="crimson", lw=2, label="ADX")
    ax_dmi.axhline(15, color="grey", lw=0.8, ls="--")
    ax_dmi.legend(loc="upper left", fontsize=8)
    ax_dmi.grid(alpha=0.3)

    ax_macd.plot(df.index, df["macd"], color="tab:blue", lw=1, label="MACD")
    ax_macd.plot(df.index, df["signal"], color="tab:orange", lw=1, label="signal")
    ax_macd.bar(df.index, df["hist"], color=["teal" if h >= 0 else "salmon" for h in df["hist"]], width=1)
    ax_macd.axhline(0, color="grey", lw=0.8)
    ax_macd.legend(loc="upper left", fontsize=8)
    ax_macd.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out, dpi=110)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol")
    parser.add_argument("--start", default="2026-01-01")
    args = parser.parse_args()

    with open(ROOT / "config" / "config.yaml") as f:
        params = yaml.safe_load(f)["strategy"]["params"]
    strategy = get_strategy("dmi_macd", **params)
    data = load_yfinance(args.symbol, "2024-01-01")  # extra history so indicators are warm
    df = strategy.analyze(data).loc[args.start:]
    trades = trade_log(df, strategy.params["exit_ema"])

    pd.set_option("display.width", 250)
    print(trades.round(1).to_string(index=False))
    closed = trades[trades["exit_date"] != "open"]
    if len(closed):
        wins = (closed["return_%"] > 0).mean()
        print(f"\n{len(trades)} trades, {wins:.0%} of closed trades won, "
              f"compounded return {((1 + trades['return_%'] / 100).prod() - 1):+.1%}")

    vp, mp = volume_profile(data.loc[args.start:]), market_profile(data.loc[args.start:])
    out = ROOT / "docs" / f"example_{args.symbol.replace('^', '').replace('.NS', '').lower()}.png"
    out.parent.mkdir(exist_ok=True)
    plot(df, trades, args.symbol, vp, mp, out)
    print(f"chart: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
