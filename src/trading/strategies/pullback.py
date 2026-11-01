"""Strategy 2: buy short pullbacks inside a DMI uptrend, take profit on the bounce.

Built for a higher win rate than dmi_macd: it enters after a dip in a trend that is already strong, and
books the bounce instead of riding the whole trend. Entry and exits are on the daily close.

Entry (all of them):
  trend     close above EMA 50, EMA 20 above EMA 50, +DI above -DI, ADX at least `adx_min`
  pullback  stochastic %K was below `oversold` within the last `dip_bars` bars
  turn      %K crosses back above %D, and the close is above EMA 50
Exit (the first that fires):
  target    close at least `target_atr` x ATR above the entry
  stop      close at least `stop_atr` x ATR below the entry, or below EMA 50
  bounce    stochastic %K above `overbought`
  time      held `max_bars` bars
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import atr, dmi, ema, stochastic
from .base import Strategy


class PullbackStrategy(Strategy):
    name = "dmi_pullback"
    defaults = {
        "ema_fast": 20,
        "ema_slow": 50,
        "adx_min": 15,
        "oversold": 40,
        "overbought": 80,
        "dip_bars": 5,
        "atr_length": 14,
        "target_atr": 2.0,
        "stop_atr": 2.0,
        "exit_on_ema": True,     # also exit on a close below EMA 50
        "exit_on_overbought": True,
        "max_bars": 20,
    }

    def __init__(self, **params):
        super().__init__(**{**self.defaults, **params})

    def analyze(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df = pd.concat([data[["open", "high", "low", "close", "volume"]], dmi(data), stochastic(data)], axis=1)
        df["ema_fast"], df["ema_slow"] = ema(df["close"], p["ema_fast"]), ema(df["close"], p["ema_slow"])
        df["atr"] = atr(data, p["atr_length"])
        trend = (df["close"] > df["ema_slow"]) & (df["ema_fast"] > df["ema_slow"]) \
            & (df["plus_di"] > df["minus_di"]) & (df["adx"] >= p["adx_min"])
        dipped = (df["stoch_k"] < p["oversold"]).rolling(p["dip_bars"]).max().astype(bool)
        k_above = df["stoch_k"] > df["stoch_d"]
        turn = k_above & ~k_above.shift(1, fill_value=True)
        df["long_setup"] = trend & dipped & turn
        df["position"], df["exit_reason"] = self._positions(df)
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        return self.analyze(data)["position"]

    def _positions(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        p = self.params
        close, atr_ = df["close"].to_numpy(), df["atr"].to_numpy()
        below_ema = (df["close"] < df["ema_slow"]).to_numpy() & p["exit_on_ema"]
        overbought = (df["stoch_k"] > p["overbought"]).to_numpy() & p["exit_on_overbought"]
        setup = df["long_setup"].to_numpy()
        positions = np.zeros(len(df), dtype=int)
        reasons = np.full(len(df), "", dtype=object)
        pos, entry, risk, held = 0, 0.0, 0.0, 0
        for i in range(len(df)):
            if pos:
                held += 1
                move = close[i] - entry
                reason = "target" if move >= p["target_atr"] * risk else \
                    "stop" if move <= -p["stop_atr"] * risk else \
                    "below EMA 50" if below_ema[i] else \
                    "stochastic overbought" if overbought[i] else \
                    "time" if held >= p["max_bars"] else ""
                if reason:
                    pos, reasons[i] = 0, reason
            elif setup[i] and not np.isnan(atr_[i]):
                pos, entry, risk, held = 1, close[i], atr_[i], 0
            positions[i] = pos
        return pd.Series(positions, index=df.index), pd.Series(reasons, index=df.index)
