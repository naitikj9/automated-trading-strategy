"""Example strategy used to exercise the engine; to be replaced by the real one."""
from __future__ import annotations

import pandas as pd

from .base import Strategy


class SMACrossover(Strategy):
    name = "sma_crossover"

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        fast = data["close"].rolling(self.params.get("fast", 20)).mean()
        slow = data["close"].rolling(self.params.get("slow", 50)).mean()
        return (fast > slow).astype(int)
