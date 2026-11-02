"""Paper trading: run the live strategy on fresh bars and keep a saved book of fills.

The book is a folder (default paper/):
  state.json   cash, open positions, and the last bar each symbol was checked on
  orders.csv   every fill
  trades.csv   every closed trade

The rules are the backtest's: entries and exits on the daily close, plus the 1-hour re-entry while flat
(see strategies/mtf.py). Fills are the signal bar's close plus slippage, and pay commission, as in the backtests.
Each trade gets `capital / slots` of the starting capital, or whatever cash is left if that is less.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .indicators import ema
from .strategies.mtf import hourly_triggers, session_dates

ORDER_COLUMNS = ["time", "symbol", "side", "qty", "price", "value", "reason"]
TRADE_COLUMNS = ["symbol", "entry_time", "entry_price", "exit_time", "exit_price", "qty", "pnl", "return_pct",
                 "entry_reason", "exit_reason"]


class PaperBook:
    def __init__(self, folder: str | Path, capital: float, slots: int,
                 commission_pct: float = 0.0003, slippage_pct: float = 0.0005):
        self.folder = Path(folder)
        self.capital, self.slots = capital, slots
        self.commission, self.slippage = commission_pct, slippage_pct
        path = self.folder / "state.json"
        state = json.loads(path.read_text()) if path.exists() else {}
        self.cash = state.get("cash", capital)
        self.positions: dict[str, dict] = state.get("positions", {})
        self.last_daily: dict[str, str] = state.get("last_daily", {})
        self.last_hourly: dict[str, str] = state.get("last_hourly", {})
        self.new_orders: list[dict] = []
        self.new_trades: list[dict] = []

    def buy(self, symbol: str, price: float, when, reason: str) -> dict | None:
        if symbol in self.positions or len(self.positions) >= self.slots:
            return None
        fill = price * (1 + self.slippage)
        budget = min(self.capital / self.slots, self.cash)
        qty = int(budget / (fill * (1 + self.commission)))
        if qty <= 0:
            return None
        value = qty * fill
        self.cash -= value * (1 + self.commission)
        self.positions[symbol] = {"qty": qty, "entry_price": fill, "entry_time": str(when), "reason": reason}
        return self._order(when, symbol, "BUY", qty, fill, reason)

    def sell(self, symbol: str, price: float, when, reason: str) -> dict:
        pos = self.positions.pop(symbol)
        fill = price * (1 - self.slippage)
        value = pos["qty"] * fill
        self.cash += value * (1 - self.commission)
        cost = pos["qty"] * pos["entry_price"] * (1 + self.commission)
        pnl = value * (1 - self.commission) - cost
        self.new_trades.append({
            "symbol": symbol, "entry_time": pos["entry_time"], "entry_price": round(pos["entry_price"], 2),
            "exit_time": str(when), "exit_price": round(fill, 2), "qty": pos["qty"], "pnl": round(pnl, 2),
            "return_pct": round(100 * pnl / cost, 2), "entry_reason": pos["reason"], "exit_reason": reason,
        })
        return self._order(when, symbol, "SELL", pos["qty"], fill, reason)

    def _order(self, when, symbol, side, qty, fill, reason) -> dict:
        order = {"time": str(when), "symbol": symbol, "side": side, "qty": qty, "price": round(fill, 2),
                 "value": round(qty * fill, 2), "reason": reason}
        self.new_orders.append(order)
        return order

    def equity(self, last_prices: dict[str, float]) -> float:
        held = sum(p["qty"] * last_prices.get(s, p["entry_price"]) for s, p in self.positions.items())
        return self.cash + held

    def save(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        state = {"cash": self.cash, "positions": self.positions,
                 "last_daily": self.last_daily, "last_hourly": self.last_hourly}
        (self.folder / "state.json").write_text(json.dumps(state, indent=2))
        for name, rows, columns in (("orders.csv", self.new_orders, ORDER_COLUMNS),
                                    ("trades.csv", self.new_trades, TRADE_COLUMNS)):
            if rows:
                path = self.folder / name
                pd.DataFrame(rows, columns=columns).to_csv(path, mode="a", header=not path.exists(), index=False)
        self.new_orders, self.new_trades = [], []

    def closed_trades(self) -> pd.DataFrame:
        path = self.folder / "trades.csv"
        return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=TRADE_COLUMNS)


def mark_price(closes: pd.Series, position: dict) -> tuple[float, str]:
    """Latest close for valuing an open position, and the date it is from.

    Yahoo sometimes drops its newest daily bar for a while. The last close left can then be from before the
    entry, which would show a loss that never happened, so the entry price stands in until a newer bar arrives.
    """
    closes = closes.dropna()
    entry_day = pd.Timestamp(position["entry_time"][:10])
    if not len(closes) or closes.index[-1].tz_localize(None).normalize() < entry_day:
        return position["entry_price"], position["entry_time"][:10]
    return float(closes.iloc[-1]), f"{closes.index[-1]:%Y-%m-%d}"


def daily_step(book: PaperBook, frames: dict[str, pd.DataFrame], exit_ema: int = 50) -> list[dict]:
    """Act on each symbol's latest completed daily bar (frames from DMIMACDStrategy.analyze).

    Exits first, so freed cash and slots can take today's entries. When more symbols signal than there
    are free slots, the strongest ADX goes first. A bar already acted on is skipped, so re-running is safe.
    """
    orders, candidates = [], []
    for symbol, df in frames.items():
        day = str(df.index[-1].date())
        if book.last_daily.get(symbol, "") >= day:
            continue
        book.last_daily[symbol] = day
        last = df.iloc[-1]
        if symbol in book.positions:
            if last["close"] < ema(df["close"], exit_ema).iloc[-1]:
                orders.append(book.sell(symbol, last["close"], day, f"close below EMA {exit_ema}"))
        elif last["long_setup"]:
            candidates.append((last["adx"], symbol, last["close"], day, last["long_reason"]))
    for _, symbol, close, day, reason in sorted(candidates, reverse=True):
        order = book.buy(symbol, close, day, reason)
        if order:
            orders.append(order)
    return orders


def hourly_step(book: PaperBook, daily: dict[str, pd.DataFrame], hourly: dict[str, pd.DataFrame],
                now: pd.Timestamp, triggers=("ema_cross",), exit_ema: int = 50) -> list[dict]:
    """While flat, buy on a 1-hour trigger from today's completed bars, if yesterday's daily trend was intact.

    Same rule as mtf_positions: yesterday EMA 20 above EMA 50 and close above EMA 50, the hourly close above
    yesterday's EMA 50, and never on the session's last bar (the daily step decides at the close).
    """
    orders = []
    for symbol, h_raw in hourly.items():
        if symbol in book.positions or symbol not in daily:
            continue
        h = hourly_triggers(h_raw, triggers)
        h = h[h.index + pd.Timedelta(hours=1) <= now]           # drop the bar still forming
        if h.empty:
            continue
        dates = session_dates(h.index)
        today = dates[-1]
        seen = book.last_hourly.get(symbol)
        book.last_hourly[symbol] = str(h.index[-1])
        if today != session_dates(pd.DatetimeIndex([now]))[0]:
            continue
        d = daily[symbol]
        before = d[d.index < today]
        if before.empty:
            continue
        prev = before.iloc[-1]
        prev_exit = ema(before["close"], exit_ema).iloc[-1]
        if not (prev["ema_fast"] > prev["ema_slow"] and prev["close"] > prev["ema_slow"]):
            continue
        bars = h[(dates == today) & (h.index.time != pd.Timestamp("15:15").time())]
        if seen:
            bars = bars[bars.index > pd.Timestamp(seen)]
        fired = bars[bars["trigger"] & (bars["close"] > prev_exit)]
        if len(fired):
            order = book.buy(symbol, fired["close"].iloc[0], fired.index[0], "1h trigger: " + "/".join(triggers))
            if order:
                orders.append(order)
    return orders
