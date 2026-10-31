"""Paper trade the live config on fresh Yahoo data, and list the orders to copy into TradingView.

    python paper_trade.py daily    # after the close (15:45 IST or later): daily exits and entries
    python paper_trade.py hourly   # during the session, once an hour: 1-hour re-entries while flat
    python paper_trade.py report   # open positions, closed trades, equity

Every run prints the new orders as NSE:SYMBOL lines, ready to place in TradingView's Paper Trading account.
The book is saved in the `paper.folder` from the config (see src/trading/paper.py).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research"))

from trading.data.loader import load_yfinance, load_yfinance_hourly  # noqa: E402
from trading.paper import PaperBook, daily_step, hourly_step  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402

IST = "Asia/Kolkata"
DAILY_READY = pd.Timedelta(hours=15, minutes=45)  # Yahoo's daily bar is final a little after the 15:30 close


def symbols(cfg: dict) -> list[str]:
    universe = cfg["paper"]["universe"]
    if universe == "watchlist":
        names = cfg["watchlist"]
    else:
        from index_study import constituents

        names = constituents(universe)
    # Indices (^CNXPHARMA) cannot be bought, so they stay scanner-only
    return [n if n.endswith(".NS") else f"{n}.NS" for n in names if not n.startswith("^")]


def tradingview(symbol: str) -> str:
    return "NSE:" + symbol.removesuffix(".NS")


def print_orders(orders: list[dict]) -> None:
    if not orders:
        print("No new orders.")
        return
    print("New orders, place these in TradingView Paper Trading (market orders):")
    for o in orders:
        print(f"  {o['side']:4} {o['qty']:>6} x {tradingview(o['symbol']):22} ~Rs {o['price']:>10,.2f}   {o['reason']}")


def load_daily(symbol: str, cfg: dict, now: pd.Timestamp) -> pd.DataFrame | None:
    try:
        data = load_yfinance(symbol, cfg["start"])
    except Exception as exc:
        print(f"skip {symbol}: {exc}")
        return None
    today = now.normalize().tz_localize(None)
    if len(data) and data.index[-1] >= today and now - now.normalize() < DAILY_READY:
        data = data.iloc[:-1]  # today's bar is still forming
    return data if len(data) > 250 else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["daily", "hourly", "report"])
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--folder", help="Book folder, overriding paper.folder (handy for a dry run)")
    args = parser.parse_args()

    with open(ROOT / args.config) as f:
        cfg = yaml.safe_load(f)
    pcfg, params = cfg["paper"], cfg["strategy"]["params"]
    names = symbols(cfg)
    book = PaperBook(Path(args.folder) if args.folder else ROOT / pcfg["folder"], pcfg["capital"], pcfg.get("max_positions") or len(names),
                     cfg["backtest"]["commission_pct"], cfg["backtest"]["slippage_pct"])
    strategy = get_strategy(cfg["strategy"]["name"], **params)
    now = pd.Timestamp.now(tz=IST)

    if args.mode == "report":
        report(book)
        return

    daily = {}
    for s in names if args.mode == "daily" else [n for n in names if n not in book.positions]:
        data = load_daily(s, cfg, now)
        if data is not None:
            daily[s] = strategy.analyze(data)

    if args.mode == "daily":
        orders = daily_step(book, daily, params["exit_ema"])
    else:
        if not cfg.get("hourly", {}).get("enabled"):
            print("hourly re-entries are off in the config")
            return
        hourly = {}
        for s in daily:
            try:
                hourly[s] = load_yfinance_hourly(s, days=60)
            except Exception as exc:
                print(f"skip {s}: {exc}")
        orders = hourly_step(book, daily, hourly, now, tuple(cfg["hourly"]["triggers"]), params["exit_ema"])
    book.save()
    print(f"{now:%Y-%m-%d %H:%M} IST, {args.mode} check of {len(daily)} stocks")
    print_orders(orders)
    print(f"Cash Rs {book.cash:,.0f}, open positions {len(book.positions)}/{book.slots}")


def report(book: PaperBook) -> None:
    rows, prices = [], {}
    for s, p in book.positions.items():
        try:
            prices[s] = float(load_yfinance(s, (pd.Timestamp.now() - pd.Timedelta(days=10)).strftime("%Y-%m-%d"))["close"].iloc[-1])
        except Exception:
            prices[s] = p["entry_price"]
        rows.append({"symbol": tradingview(s), "since": p["entry_time"][:16], "qty": p["qty"],
                     "entry": round(p["entry_price"], 2), "last": round(prices[s], 2),
                     "return_%": round(100 * (prices[s] / p["entry_price"] - 1), 2), "why": p["reason"]})
    equity = book.equity(prices)
    print(f"Equity Rs {equity:,.0f} ({equity / book.capital - 1:+.2%} on Rs {book.capital:,.0f}), cash Rs {book.cash:,.0f}\n")
    print("Open positions:" if rows else "No open positions.")
    if rows:
        print(pd.DataFrame(rows).to_string(index=False))
    trades = book.closed_trades()
    if len(trades):
        wins = trades[trades["pnl"] > 0]
        losses = trades[trades["pnl"] <= 0]
        pf = wins["pnl"].sum() / -losses["pnl"].sum() if len(losses) and losses["pnl"].sum() else float("inf")
        print(f"\nClosed trades {len(trades)}, win rate {len(wins) / len(trades):.0%}, "
              f"avg win {wins['return_pct'].mean():+.1f}%, avg loss {losses['return_pct'].mean():+.1f}%, "
              f"profit factor {pf:.2f}, realised P&L Rs {trades['pnl'].sum():,.0f}")
        print(trades.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()
