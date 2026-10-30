"""Performance metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def sharpe(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    std = returns.std()
    return float(np.sqrt(periods) * returns.mean() / std) if std > 0 else 0.0


def summary(returns: pd.Series, equity: pd.Series, positions: pd.Series) -> dict:
    years = max(len(returns) / TRADING_DAYS, 1e-9)
    total = float((1 + returns).prod() - 1)
    return {
        "total_return": total,
        "cagr": float((1 + total) ** (1 / years) - 1),
        "sharpe": sharpe(returns),
        "max_drawdown": max_drawdown(equity),
        "trades": int((positions.diff().fillna(positions) != 0).sum()),
    }
