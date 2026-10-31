"""Does a 1-hour re-entry trigger beat waiting for the daily close?

Runs the config strategy on every stock in an index, on hourly bars from 2024 onwards (Yahoo keeps
about two years of hourly data). Every variant uses the same daily entries and exits; they differ only
in whether, and on which hourly signal, a flat position may re-enter during the day.

    python research/hourly_reentry_study.py --universe smallcap100
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research"))

from index_study import COSTS, UNIVERSES, constituents, load_universe  # noqa: E402
from trading.backtest.metrics import max_drawdown  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402
from trading.strategies.mtf import mtf_positions  # noqa: E402

START = "2024-01-01"
BARS_PER_YEAR = 252 * 7  # NSE: seven hourly bars a session
HOURLY_CACHE = ROOT / "data" / "cache" / "1h"

VARIANTS = {
    "daily only": {"use_hourly": False},
    "1h +DI cross": {"triggers": ("di_cross",)},
    "1h EMA 20/50 cross": {"triggers": ("ema_cross",)},
    "1h either": {"triggers": ("di_cross", "ema_cross")},
}


def load_hourly(name: str) -> pd.DataFrame | None:
    import yfinance as yf

    HOURLY_CACHE.mkdir(parents=True, exist_ok=True)
    path = HOURLY_CACHE / f"{name}.csv"
    if path.exists():
        return pd.read_csv(path, index_col=0, parse_dates=True)
    raw = yf.download(f"{name}.NS", period="730d", interval="1h", auto_adjust=True, progress=False)
    if raw.empty:
        return None
    raw.columns = [c.lower() for c in raw.columns.get_level_values(0)]
    data = raw[["open", "high", "low", "close", "volume"]].dropna()
    data.to_csv(path)
    return pd.read_csv(path, index_col=0, parse_dates=True)


def run(daily: pd.DataFrame, hourly: pd.DataFrame, **kwargs) -> tuple[pd.Series, int]:
    m = mtf_positions(daily, hourly, **kwargs)
    pos = m["position"].shift(1).fillna(0)
    turnover = m["position"].diff().abs().fillna(0)
    rets = pos * m["close"].pct_change().fillna(0) - turnover * (COSTS["commission_pct"] + COSTS["slippage_pct"])
    entries = int(((m["position"] == 1) & (m["position"].shift(1) == 0)).loc[START:].sum())
    return rets.loc[START:], entries


def portfolio(rets: pd.DataFrame) -> dict:
    r = rets.mean(axis=1, skipna=True).fillna(0)
    equity = (1 + r).cumprod()
    years = len(r) / BARS_PER_YEAR
    return {
        "cagr": equity.iloc[-1] ** (1 / years) - 1,
        "sharpe": float(np.sqrt(BARS_PER_YEAR) * r.mean() / r.std()) if r.std() > 0 else 0.0,
        "max_dd": max_drawdown(equity),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=UNIVERSES, default="smallcap100")
    name = parser.parse_args().universe

    with open(ROOT / "config" / "config.yaml") as f:
        params = yaml.safe_load(f)["strategy"]["params"]
    strategy = get_strategy("dmi_macd", **params)
    daily_data = load_universe(name)

    results = {v: {} for v in VARIANTS}
    trades = {v: 0 for v in VARIANTS}
    for sym in constituents(name):
        if sym not in daily_data:
            continue
        hourly = load_hourly(sym)
        if hourly is None or len(hourly) < 500:
            continue
        hourly.index = pd.to_datetime(hourly.index, utc=True).tz_convert("Asia/Kolkata")
        daily = strategy.analyze(daily_data[sym])
        for variant, kwargs in VARIANTS.items():
            rets, n = run(daily, hourly, exit_ema=params["exit_ema"], **kwargs)
            results[variant][sym] = rets
            trades[variant] += n
    n_stocks = len(results["daily only"])
    print(f"{name}: {n_stocks} stocks with hourly data, {START} onwards\n")

    rows = []
    for variant in VARIANTS:
        stats = portfolio(pd.DataFrame(results[variant]))
        rows.append({"variant": variant, **stats, "entries_per_stock": trades[variant] / n_stocks})
    table = pd.DataFrame(rows).set_index("variant")
    out = ROOT / "results" / name
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "hourly_reentry.csv")
    print(table.round(3).to_string())


if __name__ == "__main__":
    main()
