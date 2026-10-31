"""Multi-timeframe re-entry: the daily chart says the trend is intact, the 1-hour chart times the entry.

Runs on hourly bars. Daily decisions (main entry, daily re-entries, exits) are taken at each day's last
hourly bar, exactly as the daily strategy would at the close. On top of that, while flat, an hourly trigger
can re-enter during the day if the previous day's chart still showed an uptrend:

  daily trend intact  -> yesterday: EMA 20 above EMA 50, close above EMA 50
  hourly trigger      -> +DI crosses above -DI, or EMA 20 crosses above EMA 50, on the 1-hour chart
                         and the hourly close is above yesterday's daily EMA 50

Exits stay on the daily chart, so the only difference from the daily strategy is when re-entries happen.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import dmi, ema

HOURLY_TRIGGERS = ("di_cross", "ema_cross")


def hourly_triggers(hourly: pd.DataFrame, triggers=HOURLY_TRIGGERS) -> pd.DataFrame:
    """Hourly indicators and the bars where each re-entry trigger fires."""
    h = pd.concat([hourly[["open", "high", "low", "close", "volume"]], dmi(hourly)], axis=1)
    h["ema_fast"], h["ema_slow"] = ema(h["close"], 20), ema(h["close"], 50)
    fired = pd.Series(False, index=h.index)
    if "di_cross" in triggers:
        h["di_cross"] = (h["plus_di"] > h["minus_di"]) & (h["plus_di"].shift(1) <= h["minus_di"].shift(1))
        fired |= h["di_cross"]
    if "ema_cross" in triggers:
        h["ema_cross"] = (h["ema_fast"] > h["ema_slow"]) & (h["ema_fast"].shift(1) <= h["ema_slow"].shift(1))
        fired |= h["ema_cross"]
    h["trigger"] = fired
    return h


def session_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Calendar date of each hourly bar, without timezone, to line up with daily bars."""
    if index.tz is not None:
        index = index.tz_localize(None)
    return index.normalize()


def mtf_positions(daily: pd.DataFrame, hourly: pd.DataFrame, exit_ema: int = 50,
                  triggers=HOURLY_TRIGGERS, use_hourly: bool = True) -> pd.DataFrame:
    """Hourly positions from an analyzed daily frame (DMIMACDStrategy.analyze) plus hourly triggers.

    With `use_hourly=False` this reproduces the daily strategy on the hourly grid, for a fair comparison.
    """
    h = hourly_triggers(hourly, triggers)
    dates = session_dates(h.index)
    day = pd.DataFrame(index=daily.index)
    day["long_setup"] = daily["long_setup"]
    day["exit_ema"] = ema(daily["close"], exit_ema)
    day["exit_long"] = daily["close"] < day["exit_ema"]
    day["trend_ok"] = (daily["ema_fast"] > daily["ema_slow"]) & (daily["close"] > daily["ema_slow"])

    today = day.reindex(dates)                 # decided at today's close
    yesterday = day.shift(1).reindex(dates)    # known before today's session opens
    h["trend_ok"] = yesterday["trend_ok"].fillna(False).to_numpy() \
        & (h["close"] > yesterday["exit_ema"].to_numpy())
    h["day_close"] = np.r_[dates[1:] != dates[:-1], True]

    trigger = (h["trigger"] & h["trend_ok"]).to_numpy() & use_hourly
    day_close = h["day_close"].to_numpy()
    long_setup = today["long_setup"].fillna(False).to_numpy()
    exit_long = today["exit_long"].fillna(False).to_numpy()

    positions = np.zeros(len(h), dtype=int)
    source = np.full(len(h), "", dtype=object)
    pos = 0
    for i in range(len(h)):
        if pos == 0 and trigger[i] and not day_close[i]:
            pos, source[i] = 1, "1h trigger"
        if day_close[i]:
            if pos == 1 and exit_long[i]:
                pos, source[i] = 0, "daily exit"
            if pos == 0 and long_setup[i]:
                pos, source[i] = 1, "daily entry"
        positions[i] = pos
    h["position"], h["event"] = positions, source
    return h
