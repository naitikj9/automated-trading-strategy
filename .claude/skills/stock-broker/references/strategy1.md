# Strategy 1: DMI + MACD trend following (the user's own strategy)

Config: `config/config.yaml`. Code: `src/trading/strategies/dmi_macd.py`. The rules must not change unless the user asks.

## Rules

Daily candles, signal at the close, long only.

**Main entry**, all of:
1. +DI above −DI (DMI 14, 14)
2. ADX at least 15 and rising
3. MACD (12, 26, 9) above its signal line, with a MACD double dip or bullish divergence
4. Close above EMA 20 and at least 2% above EMA 50

**Re-entries** in an established uptrend (skip the ADX and MACD checks, still need +DI > −DI and the 2% buffer):
- +DI crosses back above −DI
- EMA 20 reclaim: pullback held EMA 50, close back above EMA 20
- EMA 20 bounce ("pullback rejected"): low within 2% of EMA 20, close tops the previous high
- 1-hour EMA 20 crosses above EMA 50 while flat and the daily trend is intact (intraday)

**Exit:** the daily close falls below EMA 50. Nothing else: no target, no stop, no trailing.

## Paper trading

`paper_trade.py`, smallcap 100, ₹10 lakh, 10 slots of ~₹1 lakh, strongest ADX first when signals outnumber free slots. Windows tasks run the hourly check (10:20–15:20) and the daily check (16:00). The book lives in the Desktop clone's `paper/` folder. Orders are mirrored by hand in TradingView Paper Trading. Started 2 Nov 2026.

## Backtest results

Test period 2024 to Oct 2026, unseen while the rules were built (train 2018–2023):

| Universe | One slot per stock: CAGR / Sharpe / max DD | 10 slots: CAGR / max DD | Last year (Nov 2025–Oct 2026), 10 slots |
|---|---|---|---|
| Smallcap 100 | 10.2% / 1.22 / −7.7% | 36.8% / −23.5% | +38.2% |
| Midcap 100 | 6.7% / 0.85 / −6.4% | 18.0% / −20.5% | +4.7% |
| Nifty 50 | 3.3% / 0.55 / −7.5% | 7.2% / −16.4% | +0.1% |

Win rate about 30%. Average win +15% to +22%, average loss −4% to −5% (smallcap/midcap).

## Five-year trade study (Nov 2021 to Oct 2026, 4,072 trades)

**Where the money comes from:**
- 70% of all profit came from trades opened in 2023.
- The best 10% of trades made 147% of the total; the other 90% lose money together.
- Trades held over 30 bars: 91% win, all of the profit. Trades held 30 bars or less: 6–18% win, all net losers.

**Strategy vs equal-weight buy & hold by year (smallcap):** 2022 +4% vs +15%, 2023 +47% vs +79%, 2024 +15% vs +44%, 2025 +3% vs +11%, 2026 +11% vs +17%. One slot per stock, invested about 38% of the time.

**Weaknesses:**
1. Chop: repeated failed breakouts at about −4.5% each. 55% of losers never rose above +2%.
2. Long flat spells: 2022 and 2025 were near flat while buy & hold made 9–15%.
3. Giveback: trades that reached +10% peaked at +37% on average and closed at +20%; winners keep a median 43% of their peak gain.
4. The EMA 20 reclaim re-entry is the weakest rule: 26% win rate, profit factor 1.2.
5. Entries with ADX 25–35 were the weakest (profit factor 1.6); ADX 15–20 and above 35 were best.
6. Construction Materials, Textiles, Power and Chemicals barely broke even. Capital Goods made 27% of all profit.

**Strengths:**
- EMA 20 bounce is the best entry: 41% win rate, profit factor 3.1.
- Extended entries worked: 10–20% above EMA 50 won 43%, over 20% above won 50%. Momentum persisted.
- Low VIX (<12) gave the best trades (profit factor 3.6).
- Breadth extremes (<30% or >70% of stocks above EMA 50) beat the middle.
- Loses far less than buy & hold in chop and down regimes.

## Fixes tested and rejected

From `research/weakness_tests.py`, test-period CAGR:

| Variant | Smallcap, all | Smallcap, 10 slots | Midcap, 10 slots | Nifty, 10 slots |
|---|---|---|---|---|
| Live config | 9.7% | 36.8% | 18.0% | 7.2% |
| Drop EMA 20 reclaim | 9.7% | 34.6% | 15.3% | 7.2% |
| Trailing EMA 20 exit once +20% | 7.0% | 32.5% | 15.7% | 3.2% |
| Same, once +50% | 8.6% | 35.6% | 13.5% | 3.8% |

A trailing exit throws out the few trades that go +100%, which pay for everything else. Earlier tests also rejected: MACD divergence exit, DI-cross exit, golden-cross entry, shorts, a market-breadth filter.

## Strategy 2 (for comparison)

`strategy_2_pullback/`: stochastic pullback in a DMI trend, 2 ATR target and stop. Win rate 45–53%, but CAGR only about 1% (one slot per stock) or 4–10% (10 slots), below strategy 1 on every index. A higher win rate did not mean more money.

## How to talk about a single trade

- One trade proves nothing; the edge shows over 30+ trades.
- Expect most trades to stop out near −4% to −5% within days to a few weeks.
- The trades that matter run for months, so an open winner should be left alone until the close breaks EMA 50.
