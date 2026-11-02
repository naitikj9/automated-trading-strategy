"""Portfolio layer for strategy 2: a market filter and a fixed number of capital slots.

Market filter (breadth): the share of the index's stocks closing above their EMA 50. New entries are taken
only while it is at least `min_breadth`; exits are never blocked. It is known at each close, so no lookahead.

Slots: capital is split into `slots` equal parts instead of one part per stock in the index. A stock's own
strategy decides when it would enter and exit; the portfolio takes an entry only if a slot is free, the
strongest ADX first, and skips that trade otherwise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading.indicators import ema


def breadth(closes: pd.DataFrame, length: int = 50) -> pd.Series:
    """Share of stocks (with data that day) whose close is above their own EMA."""
    above = pd.DataFrame({s: c > ema(c.dropna(), length).reindex(c.index) for s, c in closes.items()})
    listed = closes.notna()
    return (above & listed).sum(axis=1) / listed.sum(axis=1).replace(0, np.nan)


def simulate(frames: dict[str, pd.DataFrame], slots: int, cost: float, market: pd.Series | None = None,
             min_breadth: float = 0.0) -> tuple[pd.Series, pd.DataFrame]:
    """Daily portfolio returns and the trade list. Each frame needs position, close and adx columns."""
    symbols = list(frames)
    pos = pd.DataFrame({s: f["position"] for s, f in frames.items()}).fillna(0).to_numpy()
    close_df = pd.DataFrame({s: f["close"] for s, f in frames.items()})
    dates = close_df.index
    close = close_df.ffill().to_numpy()
    rets = close_df.ffill().pct_change().fillna(0).to_numpy()
    adx = pd.DataFrame({s: f["adx"] for s, f in frames.items()}).fillna(0).to_numpy()
    ok = np.ones(len(dates), dtype=bool) if market is None else \
        (market.reindex(dates).fillna(0) >= min_breadth).to_numpy()

    held: dict[int, tuple[int, float]] = {}       # column -> (entry row, entry close)
    port = np.zeros(len(dates))
    trades = []
    for t in range(1, len(dates)):
        # today's return on what was held at yesterday's close
        port[t] = sum(rets[t, j] for j in held) / slots
        changes = 0
        for j in [j for j in held if pos[t, j] == 0]:
            i, entry = held.pop(j)
            trades.append((symbols[j], dates[i], dates[t], close[t, j] / entry - 1 - 2 * cost))
            changes += 1
        if ok[t] and len(held) < slots:
            new = np.flatnonzero((pos[t] == 1) & (pos[t - 1] == 0))
            for j in sorted((j for j in new if j not in held), key=lambda j: -adx[t, j])[:slots - len(held)]:
                held[j] = (t, close[t, j])
                changes += 1
        port[t] -= changes * cost / slots
    for j, (i, entry) in held.items():
        trades.append((symbols[j], dates[i], None, close[-1, j] / entry - 1 - 2 * cost))
    trade_df = pd.DataFrame(trades, columns=["symbol", "entry", "exit", "ret"])
    return pd.Series(port, index=dates), trade_df
