"""Technical indicators, matching TradingView's built-in definitions."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder's moving average (TradingView `ta.rma`): SMA seed, then alpha = 1/length."""
    values = series.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    valid = np.flatnonzero(~np.isnan(values))
    if len(valid) < length:
        return pd.Series(out, index=series.index)
    start = valid[0]
    prev = values[start:start + length].mean()
    out[start + length - 1] = prev
    for i in range(start + length, len(values)):
        prev = (prev * (length - 1) + values[i]) / length
        out[i] = prev
    return pd.Series(out, index=series.index)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def dmi(data: pd.DataFrame, di_length: int = 14, adx_smoothing: int = 14) -> pd.DataFrame:
    """Directional Movement Index: +DI, -DI and ADX."""
    high, low, close = data["high"], data["low"], data["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    plus_dm.iloc[0] = minus_dm.iloc[0] = float("nan")

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    tr.iloc[0] = float("nan")

    atr = rma(tr, di_length)
    plus_di = 100 * rma(plus_dm, di_length) / atr
    minus_di = 100 * rma(minus_dm, di_length) / atr
    total = (plus_di + minus_di).replace(0, 1)
    adx = 100 * rma((plus_di - minus_di).abs() / total, adx_smoothing)
    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx})


def stochastic(data: pd.DataFrame, k_length: int = 14, k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
    low_min = data["low"].rolling(k_length).min()
    high_max = data["high"].rolling(k_length).max()
    raw_k = 100 * (data["close"] - low_min) / (high_max - low_min)
    k = raw_k.rolling(k_smooth).mean()
    return pd.DataFrame({"stoch_k": k, "stoch_d": k.rolling(d_smooth).mean()})
