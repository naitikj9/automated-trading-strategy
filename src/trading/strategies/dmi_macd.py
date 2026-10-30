"""DMI + MACD trend strategy.

DMI (14, 14) is the main indicator:
  +DI (blue)  > -DI (orange)  -> buyers in control
  ADX (thick red) rising      -> the trend is gaining strength

MACD (12, 26, 9) crossover times the entry and grades it:
  bullish crossover above the zero line  -> 3, super strong trend
  bullish crossover near the zero line   -> 2, strong trend
  bullish crossover below the zero line  -> 1, normal trend
All three grades are valid buys; `min_strength` filters weaker ones.

Price above EMA 20 and EMA 50 confirms the trend. Shorts mirror every rule.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import dmi, ema, macd, stochastic
from .base import Strategy

STRENGTH_LABELS = {3: "super strong", 2: "strong", 1: "normal", 0: "-"}


class DMIMACDStrategy(Strategy):
    name = "dmi_macd"

    defaults = {
        "di_length": 14,
        "adx_smoothing": 14,
        "adx_min": 0.0,          # require ADX at least this high
        "adx_rising_bars": 1,    # ADX must be above its value this many bars ago
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "macd_lookback": 5,      # a crossover within this many bars still counts
        "zero_band_pct": 0.005,  # |MACD| within 0.5% of price counts as "near zero"
        "min_strength": 1,
        "ema_fast": 20,
        "ema_slow": 50,
        "require_ema_trend": True,
        "exit_ema": 20,          # exit when close crosses back through this EMA; None to disable
        "allow_short": False,    # NSE cash shorts are intraday only; enable for F&O
    }

    def __init__(self, **params):
        super().__init__(**{**self.defaults, **params})

    def analyze(self, data: pd.DataFrame) -> pd.DataFrame:
        """All indicators plus setup, strength and position columns for each bar."""
        p = self.params
        df = pd.concat(
            [
                data[["open", "high", "low", "close", "volume"]],
                dmi(data, p["di_length"], p["adx_smoothing"]),
                macd(data["close"], p["macd_fast"], p["macd_slow"], p["macd_signal"]),
                stochastic(data),
            ],
            axis=1,
        )
        df["ema_fast"] = ema(df["close"], p["ema_fast"])
        df["ema_slow"] = ema(df["close"], p["ema_slow"])

        adx_rising = (df["adx"] > df["adx"].shift(p["adx_rising_bars"])) & (df["adx"] >= p["adx_min"])
        above = df["macd"] > df["signal"]
        bull_cross = above & ~above.shift(1, fill_value=False)
        bear_cross = ~above & above.shift(1, fill_value=True)

        df["bull_strength"] = self._grade(df, bull_cross, bullish=True)
        df["bear_strength"] = self._grade(df, bear_cross, bullish=False)

        trend_up = df["close"] > df[["ema_fast", "ema_slow"]].max(axis=1)
        trend_down = df["close"] < df[["ema_fast", "ema_slow"]].min(axis=1)
        if not p["require_ema_trend"]:
            trend_up = trend_down = pd.Series(True, index=df.index)

        df["long_setup"] = (df["plus_di"] > df["minus_di"]) & adx_rising & trend_up & above \
            & (df["bull_strength"] >= p["min_strength"])
        df["short_setup"] = (df["minus_di"] > df["plus_di"]) & adx_rising & trend_down & ~above \
            & (df["bear_strength"] >= p["min_strength"])
        df["position"] = self._positions(df)
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        return self.analyze(data)["position"]

    def _grade(self, df: pd.DataFrame, cross: pd.Series, bullish: bool) -> pd.Series:
        """Grade each crossover by where MACD sat relative to zero, and carry it for `macd_lookback` bars."""
        band = df["close"] * self.params["zero_band_pct"]
        level = df["macd"] if bullish else -df["macd"]
        grade = np.select([level > band, level >= -band], [3, 2], default=1)
        graded = pd.Series(np.where(cross, grade, np.nan), index=df.index)
        return graded.ffill(limit=self.params["macd_lookback"] - 1).fillna(0).astype(int)

    def _positions(self, df: pd.DataFrame) -> pd.Series:
        exit_ema = ema(df["close"], self.params["exit_ema"]) if self.params["exit_ema"] else None
        positions = np.zeros(len(df), dtype=int)
        pos = 0
        for i in range(len(df)):
            row = df.iloc[i]
            if pos == 1 and (row["minus_di"] > row["plus_di"]
                             or (exit_ema is not None and row["close"] < exit_ema.iloc[i])):
                pos = 0
            elif pos == -1 and (row["plus_di"] > row["minus_di"]
                                or (exit_ema is not None and row["close"] > exit_ema.iloc[i])):
                pos = 0
            if pos == 0:
                if row["long_setup"]:
                    pos = 1
                elif row["short_setup"] and self.params["allow_short"]:
                    pos = -1
            positions[i] = pos
        return pd.Series(positions, index=df.index)
