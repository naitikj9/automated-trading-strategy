import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from trading.paper import PaperBook, daily_step, hourly_step, mark_price  # noqa: E402


def frame(closes, long_setup=False, adx=20.0):
    """Analyzed-daily stand-in: just the columns the paper steps read."""
    idx = pd.bdate_range("2026-01-01", periods=len(closes))
    df = pd.DataFrame({"close": np.asarray(closes, dtype=float)}, index=idx)
    df["ema_fast"], df["ema_slow"] = df["close"] * 0.97, df["close"] * 0.95
    df["long_setup"], df["long_reason"], df["adx"] = False, "", adx
    df.iloc[-1, df.columns.get_loc("long_setup")] = long_setup
    df.iloc[-1, df.columns.get_loc("long_reason")] = "trend" if long_setup else ""
    return df


def book(tmp_path, capital=100_000, slots=2):
    return PaperBook(tmp_path, capital, slots, commission_pct=0.0, slippage_pct=0.0)


def test_entry_sizes_by_slot_and_saves(tmp_path):
    b = book(tmp_path)
    orders = daily_step(b, {"A.NS": frame([100] * 60, long_setup=True)})
    assert orders[0]["side"] == "BUY" and orders[0]["qty"] == 500   # 50,000 per slot at 100
    b.save()
    again = book(tmp_path)
    assert again.positions["A.NS"]["qty"] == 500 and again.cash == 50_000


def test_same_bar_is_not_acted_on_twice(tmp_path):
    b = book(tmp_path)
    frames = {"A.NS": frame([100] * 60, long_setup=True)}
    daily_step(b, frames)
    b.positions.clear()
    assert daily_step(b, frames) == []


def test_exit_below_ema_records_trade(tmp_path):
    b = book(tmp_path)
    daily_step(b, {"A.NS": frame([100] * 60, long_setup=True)})
    falling = frame([100] * 60 + [80])
    orders = daily_step(b, {"A.NS": falling})
    assert orders[0]["side"] == "SELL" and "A.NS" not in b.positions
    assert b.new_trades[0]["return_pct"] == -20.0


def test_more_signals_than_slots_takes_strongest_adx(tmp_path):
    b = book(tmp_path, slots=2)
    frames = {s: frame([100] * 60, long_setup=True, adx=a) for s, a in (("A.NS", 18), ("B.NS", 30), ("C.NS", 25))}
    bought = {o["symbol"] for o in daily_step(b, frames)}
    assert bought == {"B.NS", "C.NS"}


def hourly(day, closes):
    idx = pd.DatetimeIndex([pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(hours=k)
                            for k in range(len(closes))]).tz_localize("Asia/Kolkata")
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c, "volume": 1000.0}, index=idx)


def hourly_history(today, last_closes):
    """Ten falling sessions before `today`, then today's bars: the 1h EMA 20 crosses above EMA 50 today."""
    days = pd.bdate_range(end=pd.Timestamp(today) - pd.Timedelta(days=1), periods=10)
    past = pd.concat([hourly(d, np.linspace(110 - 2 * i, 108 - 2 * i, 7)) for i, d in enumerate(days)])
    return pd.concat([past, hourly(today, last_closes)])


def test_hourly_trigger_buys_only_on_completed_bars_in_trend(tmp_path):
    today = "2026-03-16"
    daily = frame([100] * 60)
    daily.index = pd.bdate_range(end="2026-03-13", periods=60)
    h = hourly_history(today, [95, 100, 108, 112, 115, 118])
    b = book(tmp_path)
    # the cross is on the 14:15 bar, which completes at 15:15
    early = pd.Timestamp(f"{today} 15:00", tz="Asia/Kolkata")
    assert hourly_step(b, {"A.NS": daily}, {"A.NS": h}, early) == []
    late = pd.Timestamp(f"{today} 15:20", tz="Asia/Kolkata")
    orders = hourly_step(b, {"A.NS": daily}, {"A.NS": h}, late)
    assert len(orders) == 1 and orders[0]["reason"].startswith("1h trigger")


def test_hourly_trigger_ignored_when_daily_trend_broken(tmp_path):
    today = "2026-03-16"
    daily = frame([100] * 60)
    daily.index = pd.bdate_range(end="2026-03-13", periods=60)
    daily["ema_fast"] = daily["ema_slow"] * 0.9          # EMA 20 below EMA 50
    h = hourly_history(today, [95, 100, 108, 112, 115, 118])
    late = pd.Timestamp(f"{today} 15:20", tz="Asia/Kolkata")
    assert hourly_step(book(tmp_path), {"A.NS": daily}, {"A.NS": h}, late) == []


def test_mark_price_ignores_bars_older_than_the_entry():
    pos = {"entry_price": 105.0, "entry_time": "2026-11-02"}
    stale = pd.Series([100.0, 101.0, np.nan], index=pd.to_datetime(["2026-10-29", "2026-10-30", "2026-11-02"]))
    assert mark_price(stale, pos) == (105.0, "2026-11-02")
    fresh = pd.Series([101.0, 104.0, 108.0], index=pd.to_datetime(["2026-10-30", "2026-11-02", "2026-11-03"]))
    assert mark_price(fresh, pos) == (108.0, "2026-11-03")
    assert mark_price(pd.Series(dtype=float), pos) == (105.0, "2026-11-02")
