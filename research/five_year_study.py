"""Five-year study: how the Indian market and its sectors behaved, and where strategy 1 makes and loses money.

Part 1, market: Nifty 50, sector indices and equal-weight midcap/smallcap baskets, Nov 2021 onwards.
    Yearly returns, drawdowns, volatility, and how often each one was in a trend (close above EMA 200).
Part 2, strategy: every strategy 1 trade (daily rules, live config) in the three universes over the same
    five years, tagged with what was true at entry: market regime, India VIX, breadth, sector, entry rule,
    ADX, distance above EMA 50. Then win rate, average return and total contribution for each group.

    python research/five_year_study.py      # writes results/five_year/*.csv and prints the tables

Caveat: the midcap/smallcap baskets and the trade lists use today's index members (survivorship bias).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import yfinance as yf

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research"))

from index_study import CACHE, COSTS, UNIVERSES, load_universe  # noqa: E402
from trading.backtest.metrics import max_drawdown  # noqa: E402
from trading.indicators import ema  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402

START = "2021-11-01"
OUT = ROOT / "results" / "five_year"
COST = 2 * (COSTS["commission_pct"] + COSTS["slippage_pct"])
INDICES = {
    "Nifty 50": "^NSEI", "Bank": "^NSEBANK", "Fin services": "NIFTY_FIN_SERVICE.NS", "PSU bank": "^CNXPSUBANK",
    "IT": "^CNXIT", "Pharma": "^CNXPHARMA", "Auto": "^CNXAUTO", "FMCG": "^CNXFMCG", "Metal": "^CNXMETAL",
    "Realty": "^CNXREALTY", "Energy": "^CNXENERGY", "Infra": "^CNXINFRA", "PSE": "^CNXPSE",
    "Consumption": "^CNXCONSUM", "MNC": "^CNXMNC", "Next 50": "^NSMIDCP",
}


def load_indices() -> tuple[pd.DataFrame, pd.Series]:
    raw = yf.download(list(INDICES.values()) + ["^INDIAVIX"], start="2020-11-01", progress=False,
                      auto_adjust=False)["Close"]
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    closes = raw[list(INDICES.values())].rename(columns={v: k for k, v in INDICES.items()})
    return closes.ffill(), raw["^INDIAVIX"].ffill()


def basket(universe: dict) -> pd.Series:
    """Equal-weight index of a universe, rebalanced daily, from 2020-11 so EMA 200 is warm by the start."""
    rets = pd.DataFrame({s: d["close"].pct_change() for s, d in universe.items()}).loc["2020-11-01":]
    return (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()


def market_tables(closes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    yearly, summary = {}, []
    for name, c in closes.items():
        c = c.dropna()
        trend = c > ema(c, 200)
        c, trend = c.loc[START:], trend.loc[START:]
        years = len(c) / 252
        rets = c.pct_change().dropna()
        summary.append({"index": name, "cagr": (c.iloc[-1] / c.iloc[0]) ** (1 / years) - 1,
                        "max_dd": max_drawdown(c / c.iloc[0]), "vol": rets.std() * np.sqrt(252),
                        "above_ema200": trend.mean()})
        yearly[name] = c.groupby(c.index.year).apply(lambda s: s.iloc[-1] / s.iloc[0] - 1)
    return pd.DataFrame(summary).set_index("index"), pd.DataFrame(yearly).T


def regime(nifty: pd.Series) -> pd.Series:
    """up: close and EMA 50 above EMA 200; down: both below; chop: anything in between."""
    e50, e200 = ema(nifty, 50), ema(nifty, 200)
    up = (nifty > e200) & (e50 > e200)
    down = (nifty < e200) & (e50 < e200)
    return pd.Series(np.select([up, down], ["up", "down"], "chop"), index=nifty.index)


def breadth(universe: dict) -> pd.Series:
    above = pd.DataFrame({s: d["close"] > ema(d["close"], 50) for s, d in universe.items()})
    return above.mean(axis=1)


def trades_for(name: str, df: pd.DataFrame) -> list[dict]:
    pos = df["position"].to_numpy()
    close = df["close"].to_numpy()
    rows = []
    i = 1
    while i < len(df):
        if pos[i] == 1 and pos[i - 1] == 0:
            j = i + 1
            while j < len(df) and pos[j] == 1:
                j += 1
            j = min(j, len(df) - 1)
            entry, path = close[i], close[i:j + 1]
            row = df.iloc[i]
            rows.append({
                "symbol": name, "entry": df.index[i], "exit": df.index[j], "bars": j - i,
                "ret": path[-1] / entry - 1 - COST, "mfe": path.max() / entry - 1, "mae": path.min() / entry - 1,
                "reason": row["long_reason"], "adx": row["adx"],
                "ext_ema50": row["close"] / row["ema_slow"] - 1, "day_move": row["close"] / close[i - 1] - 1,
                "open": j == len(df) - 1 and pos[j] == 1,
            })
            i = j
        i += 1
    return rows


def rule(reason: str) -> str:
    if reason.startswith("trend"):
        return "main: DI + ADX + MACD + EMA"
    return reason.split(" + ")[0]


def group(trades: pd.DataFrame, by) -> pd.DataFrame:
    g = trades.groupby(by, observed=True)["ret"]
    out = pd.DataFrame({
        "trades": g.size(), "win_rate": g.apply(lambda r: (r > 0).mean()), "avg_ret": g.mean(),
        "avg_win": g.apply(lambda r: r[r > 0].mean()), "avg_loss": g.apply(lambda r: r[r <= 0].mean()),
        "profit_factor": g.apply(lambda r: r[r > 0].sum() / -r[r <= 0].sum() if (r <= 0).any() else np.inf),
        "share_of_profit": g.sum() / trades["ret"].sum(),
    })
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

    with open(ROOT / "config" / "config.yaml") as f:
        params = yaml.safe_load(f)["strategy"]["params"]
    strategy = get_strategy("dmi_macd", **params)

    closes, vix = load_indices()
    universes = {u: load_universe(u) for u in UNIVERSES}
    for u in ("midcap100", "smallcap100"):
        closes[f"EW {u}"] = basket(universes[u]).reindex(closes.index).ffill()

    summary, yearly = market_tables(closes)
    summary.to_csv(OUT / "market_summary.csv")
    yearly.to_csv(OUT / "market_yearly.csv")
    print("== Market, Nov 2021 onwards ==")
    print(summary.sort_values("cagr", ascending=False).to_string())
    print("\n== Calendar-year returns ==")
    print(yearly.sort_values(yearly.columns[-1], ascending=False).to_string())

    nifty = closes["Nifty 50"].dropna()
    reg = regime(nifty)
    reg_5y = reg.loc[START:]
    print("\n== Nifty regime share of days ==")
    print(reg_5y.value_counts(normalize=True).to_string())
    print(reg_5y.groupby(reg_5y.index.year).value_counts(normalize=True).unstack().to_string())

    industry = {}
    for u, file in UNIVERSES.items():
        industry.update(pd.read_csv(CACHE / f"{file}.csv").set_index("Symbol")["Industry"].to_dict())

    all_trades, yearly_vs_bh = [], []
    for u, universe in universes.items():
        b = breadth(universe)
        strat_rets = {}
        for s, data in universe.items():
            df = strategy.analyze(data)
            for t in trades_for(s, df.loc["2021-06-01":]):
                if t["entry"] >= pd.Timestamp(START):
                    t["universe"] = u
                    all_trades.append(t)
            r = df["close"].pct_change() * df["position"].shift(1).fillna(0)
            r -= df["position"].diff().abs().fillna(0) * COST / 2
            strat_rets[s] = r
        sr = pd.DataFrame(strat_rets).loc[START:].mean(axis=1).fillna(0)
        bh = pd.DataFrame({s: d["close"].pct_change() for s, d in universe.items()}).loc[START:].mean(axis=1).fillna(0)
        for y in sorted(set(sr.index.year)):
            yearly_vs_bh.append({"universe": u, "year": y,
                                 "strategy": (1 + sr[sr.index.year == y]).prod() - 1,
                                 "buy_hold": (1 + bh[bh.index.year == y]).prod() - 1})
        by_regime = sr.groupby(reg.reindex(sr.index).ffill()).apply(lambda r: r.mean() * 252)
        bh_regime = bh.groupby(reg.reindex(bh.index).ffill()).apply(lambda r: r.mean() * 252)
        print(f"\n== {u}: annualised return by Nifty regime (strategy vs buy & hold) ==")
        print(pd.DataFrame({"strategy": by_regime, "buy_hold": bh_regime}).to_string())
        for t in all_trades:
            if t["universe"] == u:
                t["breadth"] = b.get(t["entry"], np.nan)

    yv = pd.DataFrame(yearly_vs_bh)
    yv.to_csv(OUT / "strategy_vs_bh_yearly.csv", index=False)
    print("\n== Strategy vs equal-weight buy & hold, by year ==")
    print(yv.pivot(index="year", columns="universe", values=["strategy", "buy_hold"]).to_string())

    trades = pd.DataFrame(all_trades)
    trades["year"] = trades["entry"].dt.year
    trades["regime"] = reg.reindex(trades["entry"]).to_numpy()
    trades["vix"] = vix.reindex(trades["entry"], method="ffill").to_numpy()
    trades["sector"] = trades["symbol"].map(industry)
    trades["rule"] = trades["reason"].map(rule)
    trades.to_csv(OUT / "trades.csv", index=False)

    cuts = {
        "year": "year", "regime": "regime", "rule": "rule",
        "vix": pd.cut(trades["vix"], [0, 12, 15, 20, 100], labels=["<12", "12-15", "15-20", ">20"]),
        "breadth": pd.cut(trades["breadth"], [0, .3, .5, .7, 1.01], labels=["<30%", "30-50%", "50-70%", ">70%"]),
        "adx": pd.cut(trades["adx"], [0, 20, 25, 35, 100], labels=["15-20", "20-25", "25-35", ">35"]),
        "ext_ema50": pd.cut(trades["ext_ema50"], [0, .05, .1, .2, 5], labels=["2-5%", "5-10%", "10-20%", ">20%"]),
        "day_move": pd.cut(trades["day_move"], [-1, 0, .02, .05, 1], labels=["down day", "0-2%", "2-5%", ">5%"]),
        "bars": pd.cut(trades["bars"], [-1, 3, 10, 30, 1000], labels=["1-3", "4-10", "11-30", ">30"]),
    }
    print(f"\n== {len(trades)} trades, win rate {(trades['ret'] > 0).mean():.0%}, avg {trades['ret'].mean():+.2%} ==")
    for name, by in cuts.items():
        for u in ["all"] + list(UNIVERSES):
            sub = trades if u == "all" else trades[trades["universe"] == u]
            key = by if isinstance(by, str) else by.loc[sub.index]
            table = group(sub, key)
            table.to_csv(OUT / f"by_{name}_{u}.csv")
            if u in ("all", "smallcap100"):
                print(f"\n-- by {name} ({u}) --")
                print(table.to_string())

    sec = group(trades, "sector")
    sec = sec[sec["trades"] >= 15].sort_values("avg_ret")
    sec.to_csv(OUT / "by_sector_all.csv")
    print("\n-- by sector (all universes, 15+ trades) --")
    print(sec.to_string())

    closed = trades[~trades["open"]]
    big = closed[closed["mfe"] >= 0.10]
    print("\n== Giveback ==")
    print(f"trades that were +10% or more at some point: {len(big)}, "
          f"ended as losers: {(big['ret'] <= 0).mean():.0%}, avg peak {big['mfe'].mean():+.1%}, "
          f"avg final {big['ret'].mean():+.1%}")
    winners = closed[closed["ret"] > 0]
    print(f"winners kept {(winners['ret'] / winners['mfe']).median():.0%} of their peak gain (median)")
    losers = closed[closed["ret"] <= 0]
    print(f"losers: median worst point {losers['mae'].median():+.1%}, median exit {losers['ret'].median():+.1%}, "
          f"never went above +2%: {(losers['mfe'] < 0.02).mean():.0%}")
    top = closed.sort_values("ret", ascending=False)
    n10 = max(1, len(top) // 10)
    print(f"top 10% of trades made {top['ret'].iloc[:n10].sum() / closed['ret'].sum():.0%} of the total return")


if __name__ == "__main__":
    main()
