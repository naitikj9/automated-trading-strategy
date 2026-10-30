"""Vectorised backtester with commission and slippage."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .metrics import summary


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series
    stats: dict


def run_backtest(
    data: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 100_000,
    commission_pct: float = 0.0,
    slippage_pct: float = 0.0,
) -> BacktestResult:
    # Act on the next bar so a signal never uses the close it was computed from.
    positions = signals.shift(1).fillna(0)
    asset_returns = data["close"].pct_change().fillna(0)
    turnover = positions.diff().fillna(positions).abs()
    returns = positions * asset_returns - turnover * (commission_pct + slippage_pct)
    equity = initial_capital * (1 + returns).cumprod()
    return BacktestResult(equity, returns, positions, summary(returns, equity, positions))
