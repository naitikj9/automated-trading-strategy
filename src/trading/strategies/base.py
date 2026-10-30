"""Base class every strategy implements."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """A strategy turns OHLCV data into a position signal per bar.

    Signal values: 1 = long, 0 = flat, -1 = short.
    """

    name: str = "base"

    def __init__(self, **params):
        self.params = params

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Return a Series of positions aligned to data.index."""
