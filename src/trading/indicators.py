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


def atr(data: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average true range (TradingView `ta.atr`: rma of the true range)."""
    prev_close = data["close"].shift(1)
    true_range = pd.concat([data["high"] - data["low"], (data["high"] - prev_close).abs(),
                            (data["low"] - prev_close).abs()], axis=1).max(axis=1)
    true_range.iloc[0] = data["high"].iloc[0] - data["low"].iloc[0]
    return rma(true_range, length)


def stochastic(data: pd.DataFrame, k_length: int = 14, k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
    low_min = data["low"].rolling(k_length).min()
    high_max = data["high"].rolling(k_length).max()
    raw_k = 100 * (data["close"] - low_min) / (high_max - low_min)
    k = raw_k.rolling(k_smooth).mean()
    return pd.DataFrame({"stoch_k": k, "stoch_d": k.rolling(d_smooth).mean()})


def _profile(h, l, c, v, bins: int, value_area: float):
    """Core of `volume_profile` on numpy arrays: bin edges, total and buy volume per bin, POC and value area."""
    edges = np.linspace(l.min(), h.max(), bins + 1)

    # bars x bins: the fraction of each bar's range that falls in each price bin
    span = (h - l)[:, None]
    overlap = np.clip(np.minimum(edges[1:], h[:, None]) - np.maximum(edges[:-1], l[:, None]), 0, None)
    flat = span[:, 0] == 0
    share = np.divide(overlap, span, out=np.zeros_like(overlap), where=~flat[:, None])
    share[flat, np.clip(np.digitize(c[flat], edges[1:-1]), 0, bins - 1)] = 1.0
    buy_frac = np.where(flat, 0.5, (c - l) / np.where(flat, 1, h - l))

    total = v @ share
    buy = (v * buy_frac) @ share

    poc = int(np.argmax(total))
    lo_i = hi_i = poc
    while total[lo_i:hi_i + 1].sum() < value_area * total.sum():
        below = total[lo_i - 1] if lo_i > 0 else -1
        above = total[hi_i + 1] if hi_i < bins - 1 else -1
        if above >= below:
            hi_i += 1
        else:
            lo_i -= 1
    return edges, total, buy, poc, lo_i, hi_i


def _ohlcv_arrays(data: pd.DataFrame):
    return (data["high"].to_numpy(dtype=float), data["low"].to_numpy(dtype=float),
            data["close"].to_numpy(dtype=float), np.nan_to_num(data["volume"].to_numpy(dtype=float)))


def volume_profile(data: pd.DataFrame, bins: int = 24, value_area: float = 0.70) -> dict:
    """Volume traded at each price level over `data`, split into estimated buying and selling.

    Daily bars carry no tick data, so each bar's volume is spread evenly across its high-low range,
    and the buying share is estimated from where the close sits in that range (close at the high = all buying).
    """
    edges, total, buy, poc, lo_i, hi_i = _profile(*_ohlcv_arrays(data), bins, value_area)
    mid = (edges[:-1] + edges[1:]) / 2
    levels = pd.DataFrame({"price": mid, "volume": total, "buy": buy, "sell": total - buy})
    levels["buy_pct"] = 100 * levels["buy"] / levels["volume"].replace(0, np.nan)
    return {
        "levels": levels,
        "poc": mid[poc],
        "vah": edges[hi_i + 1],
        "val": edges[lo_i],
        "buy_pct": 100 * buy.sum() / total.sum(),
    }


def rolling_poc(data: pd.DataFrame, lookback: int = 120, bins: int = 24, value_area: float = 0.70) -> pd.DataFrame:
    """POC, value area and buyer % of the last `lookback` bars up to and including each bar (no lookahead)."""
    h, l, c, v = _ohlcv_arrays(data)
    out = np.full((len(data), 4), np.nan)
    for i in range(lookback, len(data) + 1):
        s = slice(i - lookback, i)
        if np.isnan(h[s]).any() or np.isnan(l[s]).any():
            continue
        edges, total, buy, poc, lo_i, hi_i = _profile(h[s], l[s], c[s], v[s], bins, value_area)
        out[i - 1] = [(edges[poc] + edges[poc + 1]) / 2, edges[hi_i + 1], edges[lo_i], 100 * buy.sum() / total.sum()]
    return pd.DataFrame(out, index=data.index, columns=["poc", "vah", "val", "buy_pct"])


def market_profile(data: pd.DataFrame, bins: int = 24, value_area: float = 0.70) -> dict:
    """Market Profile (TPO): like the volume profile, but counts time spent at each price instead of volume.

    True TPO uses 30-minute periods; with daily bars each day counts as one period spread across its range.
    """
    profile = volume_profile(data.assign(volume=1.0), bins, value_area)
    profile["levels"] = profile["levels"].rename(columns={"volume": "tpo"})[["price", "tpo"]]
    del profile["buy_pct"]
    return profile
