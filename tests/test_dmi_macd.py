import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from trading.indicators import dmi, rma  # noqa: E402
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


def test_min_strength_filters_weaker_crossovers():
    data = trend_data(0.01)
    loose = get_strategy("dmi_macd", min_strength=1).analyze(data)["long_setup"].sum()
    strict = get_strategy("dmi_macd", min_strength=3).analyze(data)["long_setup"].sum()
    assert strict <= loose
