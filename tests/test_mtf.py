import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from trading.strategies.mtf import mtf_positions, session_dates  # noqa: E402


def hourly_bars(days, closes_per_day):
    """7 hourly bars per session (09:15-15:15 IST), with the given closes."""
    idx = [pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(hours=k)
           for d in days for k in range(7)]
    idx = pd.DatetimeIndex(idx).tz_localize("Asia/Kolkata")
    close = np.asarray(closes_per_day, dtype=float).ravel()
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close, "volume": 1000.0},
                        index=idx)


def daily_frame(days, trend_ok=True, long_setup=False, close=100.0):
    df = pd.DataFrame(index=pd.DatetimeIndex(days))
    df["close"] = close
    df["ema_fast"] = 95.0 if trend_ok else 85.0
    df["ema_slow"] = 90.0
    df["long_setup"] = long_setup
    return df


def test_session_dates_drop_time_and_zone():
    idx = pd.DatetimeIndex(["2026-06-30 11:15"]).tz_localize("Asia/Kolkata")
    assert session_dates(idx)[0] == pd.Timestamp("2026-06-30")


def test_daily_only_trades_at_the_close():
    days = pd.bdate_range("2026-01-01", periods=80)
    closes = np.repeat(np.linspace(100, 120, 80)[:, None], 7, axis=1)
    hourly = hourly_bars(days, closes)
    daily = daily_frame(days, long_setup=False)
    daily.loc[days[70], "long_setup"] = True
    m = mtf_positions(daily, hourly, exit_ema=5, use_hourly=False)
    entries = m.index[m["event"] == "daily entry"]
    assert len(entries) == 1 and entries[0].hour == 15  # the session's last bar
    assert session_dates(entries)[0] == days[70]


def test_hourly_trigger_needs_yesterdays_uptrend():
    days = pd.bdate_range("2026-01-01", periods=80)
    # falling then rising intraday on the last day, so hourly +DI / EMA cross fire there
    closes = np.repeat(np.linspace(120, 100, 80)[:, None], 7, axis=1)
    closes[-1] = [100, 103, 106, 109, 112, 115, 118]
    hourly = hourly_bars(days, closes)

    with_trend = mtf_positions(daily_frame(days, trend_ok=True, close=95.0), hourly, exit_ema=5)
    without = mtf_positions(daily_frame(days, trend_ok=False, close=95.0), hourly, exit_ema=5)
    assert (without["event"] != "1h trigger").all()
    hits = with_trend.index[with_trend["event"] == "1h trigger"]
    assert len(hits) > 0 and all(t.hour < 15 for t in hits)
