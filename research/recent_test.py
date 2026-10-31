"""The live setup over a recent window: daily entries and exits, 1-hour EMA cross re-entries.

Every stock in the index trades on its own with equal weight. Reports the portfolio return against
buy-and-hold, and trade stats (win rate, average win and loss) for trades opened inside the window.

    python research/recent_test.py --universe smallcap100 --start 2025-10-31
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research"))

from hourly_reentry_study import load_hourly  # noqa: E402
from index_study import COSTS, UNIVERSES, constituents, load_universe  # noqa: E402
from trading.backtest.metrics import max_drawdown  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402
from trading.strategies.mtf import mtf_positions  # noqa: E402


def trades(m: pd.DataFrame, start: str) -> list[float]:
    """Net return of each trade opened on or after `start` (open trades marked at the last close)."""
    pos, close = m["position"].to_numpy(), m["close"].to_numpy()
    cost = 2 * (COSTS["commission_pct"] + COSTS["slippage_pct"])
    first = m.index.searchsorted(pd.Timestamp(start, tz=m.index.tz))
    out, entry = [], None
    for i in range(max(first, 1), len(m)):
        if pos[i] == 1 and pos[i - 1] == 0:
            entry = close[i]
        elif pos[i] == 0 and pos[i - 1] == 1 and entry is not None:
            out.append(close[i] / entry - 1 - cost)
            entry = None
    if entry is not None:
        out.append(close[-1] / entry - 1 - cost)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=UNIVERSES, default="smallcap100")
    parser.add_argument("--start", default="2025-10-31")
    args = parser.parse_args()

    with open(ROOT / "config" / "config.yaml") as f:
        config = yaml.safe_load(f)
    params, triggers = config["strategy"]["params"], tuple(config["hourly"]["triggers"])
    strategy = get_strategy("dmi_macd", **params)
    daily_data = load_universe(args.universe)

    rets, bh, results = {}, {}, []
    for sym in constituents(args.universe):
        hourly = load_hourly(sym) if sym in daily_data else None
        if hourly is None or len(hourly) < 500:
            continue
        hourly.index = pd.to_datetime(hourly.index, utc=True).tz_convert("Asia/Kolkata")
        m = mtf_positions(strategy.analyze(daily_data[sym]), hourly, exit_ema=params["exit_ema"], triggers=triggers)
        turnover = m["position"].diff().abs().fillna(0)
        r = m["position"].shift(1).fillna(0) * m["close"].pct_change().fillna(0) \
            - turnover * (COSTS["commission_pct"] + COSTS["slippage_pct"])
        rets[sym] = r.loc[args.start:]
        bh[sym] = m["close"].pct_change().loc[args.start:]
        results += trades(m, args.start)

    def stats(frame):
        equity = (1 + pd.DataFrame(frame).mean(axis=1, skipna=True).fillna(0)).cumprod()
        return equity.iloc[-1] - 1, max_drawdown(equity)

    (s_ret, s_dd), (b_ret, b_dd) = stats(rets), stats(bh)
    t = pd.Series(results)
    wins, losses = t[t > 0], t[t <= 0]
    print(f"{args.universe}: {len(rets)} stocks, {args.start} to {pd.DataFrame(rets).index[-1].date()}")
    print(f"  strategy     return {s_ret:+.1%}  max DD {s_dd:.1%}")
    print(f"  buy & hold   return {b_ret:+.1%}  max DD {b_dd:.1%}")
    print(f"  trades {len(t)}, win rate {len(wins) / len(t):.0%}, avg win {wins.mean():+.1%}, "
          f"avg loss {losses.mean():+.1%}, profit factor {wins.sum() / -losses.sum():.2f}")
    print(f"  best trade {t.max():+.1%}, worst {t.min():+.1%}, still open counted at the last close")


if __name__ == "__main__":
    main()
