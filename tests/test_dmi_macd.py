import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from trading.indicators import dmi, rma, rolling_poc, volume_profile  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402


def trend_data(drift, n=200, seed=1):
    """Flat for half the period, then a steady trend with `drift` per bar."""
    rng = np.random.default_rng(seed)
    steps = np.concatenate([np.zeros(n // 2), np.full(n - n // 2, drift)]) + rng.normal(0, 0.003, n)
    close = 100 * np.cumprod(1 + steps)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": close, "high": close * 1.005, "low": close * 0.995, "close": close, "volume": 1000}, index=idx
    )


def test_rma_seeds_with_sma():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = rma(s, 3)
    assert out.iloc[:2].isna().all()
    assert out.iloc[2] == 2.0
    assert np.isclose(out.iloc[3], (2.0 * 2 + 4.0) / 3)


def test_dmi_reads_direction_and_stays_in_range():
    up = dmi(trend_data(0.01)).dropna()
    down = dmi(trend_data(-0.01)).dropna()
    assert up["plus_di"].iloc[-1] > up["minus_di"].iloc[-1]
    assert down["minus_di"].iloc[-1] > down["plus_di"].iloc[-1]
    assert up["adx"].between(0, 100).all()


def test_goes_long_in_uptrend():
    positions = get_strategy("dmi_macd").generate_signals(trend_data(0.01))
    assert positions.iloc[-1] == 1
    assert (positions.iloc[:100] == 0).mean() > 0.8


def test_shorts_only_when_allowed():
    data = trend_data(-0.01)
    assert (get_strategy("dmi_macd").generate_signals(data) >= 0).all()
    assert get_strategy("dmi_macd", allow_short=True).generate_signals(data).iloc[-1] == -1


def test_adx_floor_blocks_weak_trends():
    data = trend_data(0.01)
    strategy = get_strategy("dmi_macd", adx_min=101, di_cross_reentry=False, ema_reclaim_reentry=False)
    assert not strategy.analyze(data)["long_setup"].any()


def test_di_cross_reenters_uptrend_without_adx():
    data = trend_data(0.01)
    df = get_strategy("dmi_macd", adx_min=101, ema_reclaim_reentry=False).analyze(data)
    assert (df["long_setup"] == df["long_reentry"]).all()  # ADX floor blocks every other entry
    for i in np.flatnonzero(df["long_reentry"]):
        row, prev = df.iloc[i], df.iloc[i - 1]
        assert row["plus_di"] > row["minus_di"] and prev["plus_di"] <= prev["minus_di"]
        assert row["close"] > row["ema_fast"] > row["ema_slow"]


def pullback_data():
    """Steady 0.3% a bar uptrend with a 4-bar, ~4.5% dip at bar 120 that stays above EMA 50."""
    steps = np.full(160, 0.003)
    steps[120:124] = -0.0115
    close = 100 * np.cumprod(1 + steps)
    idx = pd.date_range("2024-01-01", periods=len(close), freq="B")
    return pd.DataFrame(
        {"open": close, "high": close * 1.002, "low": close * 0.998, "close": close, "volume": 1000}, index=idx
    )


def test_ema_reclaim_reentry_after_pullback_that_held_ema50():
    data = pullback_data()
    df = get_strategy("dmi_macd", adx_min=101, di_cross_reentry=False).analyze(data)
    hits = np.flatnonzero(df["long_reentry"])
    assert len(hits) > 0
    for i in hits:
        row, prev = df.iloc[i], df.iloc[i - 1]
        assert row["close"] > row["ema_fast"] > row["ema_slow"] and prev["close"] <= prev["ema_fast"]
        assert (df["low"].iloc[i - 9:i + 1] > df["ema_slow"].iloc[i - 9:i + 1]).all()


def test_pullback_rejection_short_in_downtrend():
    up = pullback_data()
    down = up.iloc[::-1].copy()  # mirror the uptrend-with-dip into a downtrend-with-rally
    down.index = up.index
    df = get_strategy("dmi_macd", adx_min=101, di_cross_reentry=False, ema_reclaim_reentry=False,
                      ema_pullback_entry=True).analyze(down)
    hits = np.flatnonzero(df["short_reentry"])
    assert len(hits) > 0
    for i in hits:
        row, prev = df.iloc[i], df.iloc[i - 1]
        assert row["close"] < prev["low"] and row["close"] < row["ema_fast"] < row["ema_slow"]
        recent = df.iloc[i - 2:i + 1]
        assert (recent["high"] >= recent["ema_fast"] * 0.98).any()


def base_then_breakout():
    """80 flat bars oscillating between 95 and 105, then a high-volume close at 110."""
    n = 81
    close = 100 + 5 * np.sin(np.arange(n) / 3.0)
    close[-1] = 110.0
    volume = np.full(n, 1000.0)
    volume[-1] = 5000.0
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close, "volume": volume},
                        index=idx)


def test_accumulation_breakout_needs_tight_range_and_volume():
    data = base_then_breakout()
    df = get_strategy("dmi_macd").analyze(data)
    assert df["in_base"].iloc[-2] and df["base_breakout"].iloc[-1]
    assert not df["base_breakout"].iloc[:-1].any()

    quiet = data.copy()
    quiet.loc[quiet.index[-1], "volume"] = 1000.0
    assert not get_strategy("dmi_macd").analyze(quiet)["base_breakout"].iloc[-1]

    loose = get_strategy("dmi_macd", base_max_range=0.05).analyze(data)
    assert not loose["base_breakout"].any()


def test_volume_profile_finds_heavy_level_and_buyer_share():
    idx = pd.date_range("2024-01-01", periods=4, freq="B")
    data = pd.DataFrame({
        "high": [101.0, 101.0, 111.0, 121.0],
        "low": [99.0, 99.0, 109.0, 119.0],
        "close": [101.0, 101.0, 109.0, 119.0],  # buyers at 100, sellers higher up
        "volume": [1000.0, 1000.0, 100.0, 100.0],
    }, index=idx)
    vp = volume_profile(data, bins=11)
    assert abs(vp["poc"] - 100) < 2
    assert vp["val"] <= 100 <= vp["vah"]
    assert np.isclose(vp["buy_pct"], 100 * 2000 / 2200)


def test_rolling_poc_uses_only_past_bars():
    data = trend_data(0.01)
    full = rolling_poc(data, lookback=50)
    cut = rolling_poc(data.iloc[:120], lookback=50)
    pd.testing.assert_frame_equal(full.iloc[:120], cut)
    assert full["poc"].iloc[:49].isna().all()


def test_poc_filter_keeps_longs_above_poc():
    df = get_strategy("dmi_macd", poc_filter=True, poc_lookback=50).analyze(trend_data(0.01))
    assert (df.loc[df["long_setup"], "close"] > df.loc[df["long_setup"], "poc"]).all()


def dip_series(second_low, second_price):
    """Oscillator with a low of -10 at bar 20 and `second_low` at bar 60; prices at those bars set separately."""
    n = 100
    x = np.arange(n)
    osc = -10 * np.exp(-((x - 20) / 4.0) ** 2) + second_low * np.exp(-((x - 60) / 4.0) ** 2) + 0.5
    price = pd.Series(100.0, index=range(n))
    price[20], price[60] = 90.0, second_price
    return pd.Series(osc, index=range(n)), price


def test_double_dip_with_higher_price_low_is_hidden_divergence():
    osc, price = dip_series(second_low=-9.5, second_price=95.0)
    labels = get_strategy("dmi_macd")._patterns(osc, price, bullish=True)
    assert labels[60 + 5] == "double dip + hidden bullish divergence"
    assert (labels[:65] == "").all()  # nothing before the second low is confirmed


def test_lower_price_low_with_higher_macd_low_is_divergence():
    osc, price = dip_series(second_low=-4.0, second_price=85.0)
    labels = get_strategy("dmi_macd")._patterns(osc, price, bullish=True)
    assert labels[65] == "bullish divergence"


def test_min_strength_filters_weaker_crossovers():
    data = trend_data(0.01)
    loose = get_strategy("dmi_macd", min_strength=1).analyze(data)["long_setup"].sum()
    strict = get_strategy("dmi_macd", min_strength=3).analyze(data)["long_setup"].sum()
    assert strict <= loose
