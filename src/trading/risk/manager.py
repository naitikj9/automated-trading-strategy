"""Position sizing and risk limits."""
from __future__ import annotations


class RiskManager:
    def __init__(self, max_position_pct: float = 1.0, stop_loss_pct: float | None = None):
        self.max_position_pct = max_position_pct
        self.stop_loss_pct = stop_loss_pct

    def position_size(self, capital: float, price: float) -> int:
        """Units to buy given capital and the per-trade allocation cap."""
        return int(capital * self.max_position_pct // price)

    def stop_price(self, entry_price: float, side: int = 1) -> float | None:
        if self.stop_loss_pct is None:
            return None
        return entry_price * (1 - side * self.stop_loss_pct)
