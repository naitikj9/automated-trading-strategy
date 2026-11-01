import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from trading.indicators import atr  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402


def ohlc(close):
    close = np.asarray(close, dtype=float)
    idx = pd.bdate_range("2024-01-01", periods=len(close))
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
                         "volume": 1e5}, index=idx)


def uptrend_with_dips(n=400, seed=1):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return ohlc(100 * np.exp(0.003 * t) * (1 + 0.04 * np.sin(t / 6)) * (1 + rng.normal(0, 0.003, n)))


def test_atr_of_constant_range():
    data = ohlc([100.0] * 50)
    assert np.isclose(atr(data).iloc[-1], 2.0)   # high - low = 1% above to 1% below


def test_entries_only_in_uptrend_after_a_dip():
    df = get_strategy("dmi_pullback").analyze(uptrend_with_dips())
    entries = df[(df["position"] == 1) & (df["position"].shift(1) == 0)]
    assert len(entries) > 0
    assert (entries["close"] > entries["ema_slow"]).all()
    assert (entries["plus_di"] > entries["minus_di"]).all()


def test_no_entries_in_downtrend():
    falling = ohlc(100 * np.exp(-0.003 * np.arange(400)) * (1 + 0.04 * np.sin(np.arange(400) / 6)))
    assert get_strategy("dmi_pullback").analyze(falling)["position"].sum() == 0


def test_every_exit_has_a_reason_and_time_stop_holds():
    df = get_strategy("dmi_pullback", max_bars=5, target_atr=100, stop_atr=100,
                      exit_on_ema=False, exit_on_overbought=False).analyze(uptrend_with_dips())
    pos = df["position"]
    exits = df[(pos == 0) & (pos.shift(1) == 1)]
    assert len(exits) > 0 and (exits["exit_reason"] == "time").all()
    runs = pos.groupby((pos != pos.shift()).cumsum()).sum()
    assert runs.max() <= 5


def test_no_lookahead():
    data = uptrend_with_dips()
    strategy = get_strategy("dmi_pullback")
    full = strategy.analyze(data)["position"]
    part = strategy.analyze(data.iloc[:300])["position"]
    assert full.iloc[:300].equals(part)
