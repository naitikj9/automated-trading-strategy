"""Broker interface. Live brokers (Zerodha, Upstox, Alpaca, ...) implement this."""
from __future__ import annotations

from abc import ABC, abstractmethod


class Broker(ABC):
    @abstractmethod
    def place_order(self, symbol: str, qty: int, side: str, order_type: str = "MARKET") -> str: ...

    @abstractmethod
    def get_position(self, symbol: str) -> int: ...


class PaperBroker(Broker):
    """In-memory broker for paper trading."""

    def __init__(self):
        self.positions: dict[str, int] = {}
        self.orders: list[dict] = []

    def place_order(self, symbol, qty, side, order_type="MARKET"):
        sign = 1 if side.upper() == "BUY" else -1
        self.positions[symbol] = self.positions.get(symbol, 0) + sign * qty
        self.orders.append({"symbol": symbol, "qty": qty, "side": side, "type": order_type})
        return str(len(self.orders))

    def get_position(self, symbol):
        return self.positions.get(symbol, 0)
