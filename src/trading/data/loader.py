"""Market data loading."""
from __future__ import annotations

import pandas as pd

OHLCV = ["open", "high", "low", "close", "volume"]


def load_csv(path: str) -> pd.DataFrame:
    """Load OHLCV data from a CSV whose first column is the date."""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    return df[OHLCV]


def load_yfinance(symbol: str, start: str, end: str | None = None, interval: str = "1d") -> pd.DataFrame:
    """Download OHLCV data from Yahoo Finance."""
    import yfinance as yf

    df = yf.download(symbol, start=start, end=end, interval=interval, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    return df[OHLCV].dropna()


def load_yfinance_hourly(symbol: str, days: int = 730) -> pd.DataFrame:
    """Hourly OHLCV in Indian time. Yahoo keeps about two years (730 days) of hourly bars."""
    import yfinance as yf

    df = yf.download(symbol, period=f"{days}d", interval="1h", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df = df[OHLCV].dropna()
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("Asia/Kolkata")
    return df
