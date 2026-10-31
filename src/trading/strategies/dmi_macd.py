"""DMI + MACD trend strategy.

DMI (14, 14) is the main indicator:
  +DI (blue)  > -DI (orange)      -> buyers in control
  ADX (thick red) rising and >= 15 -> the trend is gaining strength

MACD (12, 26, 9) must be bullish (MACD above signal). The last crossover grades it:
  bullish crossover above the zero line  -> 3, super strong trend
  bullish crossover near the zero line   -> 2, strong trend
  bullish crossover below the zero line  -> 1, normal trend
All three grades are valid buys; `min_strength` filters weaker ones.

MACD patterns are flagged, and can be required with `require_pattern`:
  double dip          -> MACD retests its deepest recent low (within `dip_tolerance`)
  bullish divergence  -> price makes a lower low while MACD makes a higher low
  hidden bullish div. -> price makes a higher low while MACD retests or breaks its low

Price above EMA 20 and EMA 50 confirms the trend.

Re-entries, when the uptrend is intact (EMA 20 above EMA 50), without waiting for ADX or MACD:
  +DI cross    -> price above both EMAs and +DI crosses back above -DI
  EMA 20 reclaim -> the pullback's lows held above EMA 50 and the close moves back above EMA 20

Shorts mirror every rule.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import dmi, ema, macd, rolling_poc, stochastic
from .base import Strategy

STRENGTH_LABELS = {3: "super strong", 2: "strong", 1: "normal", 0: "-"}


class DMIMACDStrategy(Strategy):
    name = "dmi_macd"

    defaults = {
        "di_length": 14,
        "adx_smoothing": 14,
        "adx_min": 15.0,         # require ADX at least this high
        "adx_rising_bars": 1,    # ADX must be above its value this many bars ago
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "macd_lookback": None,   # None: any bar with MACD on the right side; N: crossover within N bars
        "zero_band_pct": 0.005,  # |MACD| within 0.5% of price counts as "near zero"
        "min_strength": 1,
        "pivot_bars": 5,         # a MACD low/high must be the extreme of this many bars on each side
        "pattern_lookback": 250, # how far back to look for the earlier low/high
        "pattern_min_gap": 15,   # minimum bars between the two lows/highs
        "dip_tolerance": 0.15,   # second dip at least 85% as deep as the first
        "pattern_valid_bars": 20,
        "require_pattern": False,
        "ema_fast": 20,
        "ema_slow": 50,
        "require_ema_trend": True,
        "di_cross_reentry": True,  # buy a +DI cross while the EMA uptrend is intact
        "ema_reclaim_reentry": True,  # buy a close back above EMA 20 after a pullback that held EMA 50
        "reclaim_lookback": 10,    # bars of pullback that must have held EMA 50
        "ema_pullback_entry": False,  # enter when a pullback to EMA 20 is rejected
        "ema_touch_pct": 0.02,     # "touching" EMA 20 means coming within 2% of it
        "touch_bars": 3,           # the touch must be within the last 3 bars
        "base_bars": 60,           # accumulation: price stayed inside a tight range this long
        "base_max_range": 0.25,    # ...where the range (high / low - 1) is at most 25%
        "breakout_volume_mult": 1.5,  # breakout volume vs 50-day average; 0 to skip the check
        "accumulation_breakout": False,  # buy when price closes above an accumulation range
        "skip_inside_base": False,  # ignore re-entries while price is still inside the range
        "poc_lookback": 120,       # volume profile window for POC / value area
        "poc_bins": 24,
        "poc_filter": False,       # longs only above POC (buyers in control), shorts only below
        "poc_retest_entry": False, # after breaking above the value area, buy a bounce off POC
        "poc_touch_pct": 0.03,     # "touching" POC means a low within 3% of it
        "breakout_memory": 30,     # the value-area breakout must be within this many bars
        "exit_on_di_cross": True,  # exit when -DI crosses above +DI
        "exit_ema": 50,        # exit when close crosses back through this EMA; None to disable
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

        df["bull_strength"] = self._grade(df, bull_cross, above, bullish=True)
        df["bear_strength"] = self._grade(df, bear_cross, ~above, bullish=False)
        df["bull_pattern"] = self._patterns(df["macd"], df["low"], bullish=True)
        df["bear_pattern"] = self._patterns(-df["macd"], -df["high"], bullish=False)

        trend_up = df["close"] > df[["ema_fast", "ema_slow"]].max(axis=1)
        trend_down = df["close"] < df[["ema_fast", "ema_slow"]].min(axis=1)
        if not p["require_ema_trend"]:
            trend_up = trend_down = pd.Series(True, index=df.index)

        df["long_setup"] = (df["plus_di"] > df["minus_di"]) & adx_rising & trend_up & above \
            & (df["bull_strength"] >= p["min_strength"])
        df["short_setup"] = (df["minus_di"] > df["plus_di"]) & adx_rising & trend_down & ~above \
            & (df["bear_strength"] >= p["min_strength"])
        if p["require_pattern"]:
            df["long_setup"] &= df["bull_pattern"] != ""
            df["short_setup"] &= df["bear_pattern"] != ""
        triggers = {"trend: DI + ADX + MACD + EMA": (df["long_setup"].copy(), df["short_setup"].copy())}

        # Comparisons with NaN are False, so the first bar with DI values never counts as a cross.
        prev_plus, prev_minus = df["plus_di"].shift(1), df["minus_di"].shift(1)
        di_cross_up = (df["plus_di"] > df["minus_di"]) & (prev_plus <= prev_minus)
        di_cross_down = (df["minus_di"] > df["plus_di"]) & (prev_minus <= prev_plus)
        up_trend = (df["close"] > df[["ema_fast", "ema_slow"]].max(axis=1)) & (df["ema_fast"] > df["ema_slow"])
        down_trend = (df["close"] < df[["ema_fast", "ema_slow"]].min(axis=1)) & (df["ema_fast"] < df["ema_slow"])
        prev_close, prev_fast = df["close"].shift(1), df["ema_fast"].shift(1)
        n = p["reclaim_lookback"]
        held_above_slow = (df["low"] - df["ema_slow"]).rolling(n).min() > 0
        held_below_slow = (df["high"] - df["ema_slow"]).rolling(n).max() < 0
        reclaim_up = (df["close"] > df["ema_fast"]) & (prev_close <= prev_fast) & held_above_slow \
            & (df["ema_fast"] > df["ema_slow"])
        reclaim_down = (df["close"] < df["ema_fast"]) & (prev_close >= prev_fast) & held_below_slow \
            & (df["ema_fast"] < df["ema_slow"])

        # Pullback rejection: price comes back to EMA 20, fails there, and breaks the previous bar.
        touch, m = p["ema_touch_pct"], p["touch_bars"]
        dipped_to_fast = (df["low"] <= df["ema_fast"] * (1 + touch)).rolling(m).max().astype(bool)
        rallied_to_fast = (df["high"] >= df["ema_fast"] * (1 - touch)).rolling(m).max().astype(bool)
        bounce_up = dipped_to_fast & (df["close"] > df["high"].shift(1)) & (df["close"] > df["ema_fast"]) \
            & held_above_slow & (df["ema_fast"] > df["ema_slow"])
        reject_down = rallied_to_fast & (df["close"] < df["low"].shift(1)) & (df["close"] < df["ema_fast"]) \
            & held_below_slow & (df["ema_fast"] < df["ema_slow"])

        df["long_reentry"] = (di_cross_up & up_trend & p["di_cross_reentry"]) \
            | (reclaim_up & p["ema_reclaim_reentry"]) | (bounce_up & p["ema_pullback_entry"])
        df["short_reentry"] = (di_cross_down & down_trend & p["di_cross_reentry"]) \
            | (reclaim_down & p["ema_reclaim_reentry"]) | (reject_down & p["ema_pullback_entry"])
        self._accumulation(df)
        if p["skip_inside_base"]:
            df["long_reentry"] &= ~df["in_base"]
            df["short_reentry"] &= ~df["in_base"]
        allowed_long = ~df["in_base"] if p["skip_inside_base"] else True
        allowed_short = allowed_long
        if p["di_cross_reentry"]:
            triggers["+DI cross re-entry"] = (di_cross_up & up_trend & allowed_long, di_cross_down & down_trend & allowed_short)
        if p["ema_reclaim_reentry"]:
            triggers["EMA 20 reclaim (held EMA 50)"] = (reclaim_up & allowed_long, reclaim_down & allowed_short)
        if p["ema_pullback_entry"]:
            triggers["EMA 20 pullback rejected"] = (bounce_up & allowed_long, reject_down & allowed_short)
        df["long_setup"] |= df["long_reentry"]
        df["short_setup"] |= df["short_reentry"]
        if p["accumulation_breakout"]:
            df["long_setup"] |= df["base_breakout"]
            df["short_setup"] |= df["base_breakdown"]
            triggers["accumulation breakout"] = (df["base_breakout"], df["base_breakdown"])
        if p["poc_filter"] or p["poc_retest_entry"]:
            self._poc_rules(df)
            if p["poc_retest_entry"]:
                triggers["POC retest"] = (df["poc_retest_up"], df["poc_retest_down"])
        df["long_reason"] = self._reasons(df["long_setup"], {k: v[0] for k, v in triggers.items()})
        df["short_reason"] = self._reasons(df["short_setup"], {k: v[1] for k, v in triggers.items()})
        df["position"] = self._positions(df)
        return df

    @staticmethod
    def _reasons(setup: pd.Series, triggers: dict) -> pd.Series:
        """Name the rules behind each setup bar, e.g. 'trend: ... + POC retest'."""
        names = pd.Series("", index=setup.index, dtype=object)
        for name, fired in triggers.items():
            hit = setup & fired.fillna(False).astype(bool)
            names[hit] = names[hit].where(names[hit] == "", names[hit] + " + ") + name
        return names

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        return self.analyze(data)["position"]

    def _grade(self, df: pd.DataFrame, cross: pd.Series, active: pd.Series, bullish: bool) -> pd.Series:
        """Grade each crossover by where MACD sat relative to zero, and carry it while it stays valid."""
        band = df["close"] * self.params["zero_band_pct"]
        level = df["macd"] if bullish else -df["macd"]
        grade = np.select([level > band, level >= -band], [3, 2], default=1)
        graded = pd.Series(np.where(cross, grade, np.nan), index=df.index)
        lookback = self.params["macd_lookback"]
        graded = graded.ffill(limit=lookback - 1 if lookback else None)
        return graded.where(active).fillna(0).astype(int)

    def _patterns(self, osc: pd.Series, price: pd.Series, bullish: bool) -> pd.Series:
        """Label MACD double dips and divergences at troughs of `osc` (pass negated series for peaks).

        A trough is only known `pivot_bars` after it happens, so labels start then, never earlier.
        """
        p = self.params
        k, tol = p["pivot_bars"], p["dip_tolerance"]
        names = ("double dip", "bullish divergence", "hidden bullish divergence") if bullish \
            else ("double top", "bearish divergence", "hidden bearish divergence")

        values, lows = osc.to_numpy(), price.rolling(2 * k + 1, center=True, min_periods=1).min().to_numpy()
        is_trough = (osc == osc.rolling(2 * k + 1, center=True).min()) & (osc < 0)
        troughs = np.flatnonzero(is_trough.to_numpy())

        labels = np.full(len(osc), "", dtype=object)
        for t2 in troughs:
            earlier = troughs[(troughs >= t2 - p["pattern_lookback"]) & (troughs <= t2 - p["pattern_min_gap"])]
            if len(earlier) == 0:
                continue
            t1 = earlier[np.argmin(values[earlier])]
            m1, m2, l1, l2 = values[t1], values[t2], lows[t1], lows[t2]
            deep_retest = m2 <= m1 * (1 - tol)
            found = []
            if deep_retest:
                found.append(names[0])
            if l2 < l1 and m2 > m1:
                found.append(names[1])
            elif l2 > l1 and deep_retest:
                found.append(names[2])
            if found:
                start = t2 + k
                labels[start:start + p["pattern_valid_bars"]] = " + ".join(found)
        return pd.Series(labels, index=osc.index)

    def _accumulation(self, df: pd.DataFrame) -> None:
        """Mark tight sideways ranges and the first close that breaks out of one.

        Uses only the previous `base_bars` bars, so the breakout bar is compared with a range it is not part of.
        """
        p = self.params
        base_high = df["high"].rolling(p["base_bars"]).max().shift(1)
        base_low = df["low"].rolling(p["base_bars"]).min().shift(1)
        tight = (base_high / base_low - 1) <= p["base_max_range"]
        volume_ok = pd.Series(True, index=df.index)
        if p["breakout_volume_mult"]:
            volume_ok = df["volume"] > p["breakout_volume_mult"] * df["volume"].rolling(50).mean().shift(1)

        df["base_high"], df["base_low"] = base_high.where(tight), base_low.where(tight)
        df["in_base"] = tight & df["close"].between(base_low, base_high)
        df["base_breakout"] = tight & (df["close"] > base_high) & volume_ok
        df["base_breakdown"] = tight & (df["close"] < base_low) & volume_ok

    def _poc_rules(self, df: pd.DataFrame) -> None:
        """Volume profile rules: trade on the side of POC that holds control, and buy a POC retest."""
        p = self.params
        df[["poc", "vah", "val", "buy_pct"]] = rolling_poc(df, p["poc_lookback"], p["poc_bins"])
        if p["poc_retest_entry"]:
            touch, mem = p["poc_touch_pct"], p["breakout_memory"]
            broke_up = (df["close"] > df["vah"]).rolling(mem).max().fillna(0).astype(bool)
            broke_down = (df["close"] < df["val"]).rolling(mem).max().fillna(0).astype(bool)
            df["poc_retest_up"] = broke_up & (df["low"] <= df["poc"] * (1 + touch)) & (df["close"] > df["poc"]) \
                & (df["close"] > df["high"].shift(1)) & (df["ema_fast"] > df["ema_slow"])
            df["poc_retest_down"] = broke_down & (df["high"] >= df["poc"] * (1 - touch)) & (df["close"] < df["poc"]) \
                & (df["close"] < df["low"].shift(1)) & (df["ema_fast"] < df["ema_slow"])
            df["long_setup"] |= df["poc_retest_up"]
            df["short_setup"] |= df["poc_retest_down"]
        if p["poc_filter"]:
            df["long_setup"] &= df["close"] > df["poc"]
            df["short_setup"] &= df["close"] < df["poc"]

    def _positions(self, df: pd.DataFrame) -> pd.Series:
        use_di = self.params["exit_on_di_cross"]
        di_bull = (df["plus_di"] > df["minus_di"]).to_numpy() & use_di
        di_bear = (df["minus_di"] > df["plus_di"]).to_numpy() & use_di
        if self.params["exit_ema"]:
            exit_ema = ema(df["close"], self.params["exit_ema"])
            below_ema = (df["close"] < exit_ema).to_numpy()
            above_ema = (df["close"] > exit_ema).to_numpy()
        else:
            below_ema = above_ema = np.zeros(len(df), dtype=bool)
        long_setup = df["long_setup"].to_numpy()
        short_setup = df["short_setup"].to_numpy() & self.params["allow_short"]

        positions = np.zeros(len(df), dtype=int)
        pos = 0
        for i in range(len(df)):
            if (pos == 1 and (di_bear[i] or below_ema[i])) or (pos == -1 and (di_bull[i] or above_ema[i])):
                pos = 0
            if pos == 0:
                pos = 1 if long_setup[i] else -1 if short_setup[i] else 0
            positions[i] = pos
        return pd.Series(positions, index=df.index)
