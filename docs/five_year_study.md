# Five-year study: the market, its sectors, and where strategy 1 falls short

Nov 2021 to Oct 2026, daily bars. Code: [`research/five_year_study.py`](../research/five_year_study.py) and [`research/weakness_tests.py`](../research/weakness_tests.py). Raw tables are in `results/five_year/`.

The midcap and smallcap baskets are equal-weight portfolios of today's index members, so they carry survivorship bias and look better than the real indices. The sector rows are NSE's own indices and have no such bias.

## 1. The market

### Five years in one table

| Index | CAGR | Max DD | Volatility | Days above EMA 200 |
|---|---|---|---|---|
| EW Smallcap 100* | 32.7% | −23.8% | 20.7% | 90% |
| PSU Bank | 24.1% | −29.7% | 27.2% | 84% |
| EW Midcap 100* | 21.2% | −20.5% | 18.2% | 85% |
| Auto | 17.7% | −28.2% | 19.4% | 83% |
| PSE | 17.7% | −31.3% | 21.1% | 77% |
| Metal | 15.8% | −33.7% | 25.5% | 81% |
| Pharma | 14.4% | −18.5% | 15.1% | 71% |
| Infra | 11.6% | −20.9% | 16.5% | 80% |
| Next 50 | 9.9% | −26.7% | 17.9% | 77% |
| Realty | 9.6% | −43.4% | 27.0% | 61% |
| Consumption | 9.4% | −22.1% | 14.1% | 75% |
| Energy | 8.4% | −33.3% | 19.7% | 69% |
| MNC | 8.3% | −23.9% | 13.8% | 80% |
| Bank | 6.7% | −18.3% | 16.9% | 79% |
| Fin Services | 5.5% | −21.9% | 16.9% | 78% |
| **Nifty 50** | **5.3%** | −16.5% | 13.8% | 74% |
| FMCG | 2.5% | −35.6% | 14.1% | 61% |
| IT | −1.6% | −44.0% | 22.3% | 50% |

\* survivorship-biased basket, see above.

### Year by year

| | 2022 | 2023 | 2024 | 2025 | 2026 (to Oct) |
|---|---|---|---|---|---|
| Nifty 50 | +2.7% | +19.4% | +8.8% | +10.1% | **−11.8%** |
| Best sector | PSU Bank +67% | Realty +80% | Pharma +39% | PSU Bank +31% | Pharma +19% |
| Worst sector | IT −27% | Bank +12% | FMCG −0% | Realty −17% | FMCG −21% |
| Nifty regime: up / chop / down days | 66 / 16 / 18% | 88 / 10 / 2% | 98 / 2 / 0% | 70 / 17 / 14% | 18 / 12 / **71%** |

Regime: **up** = Nifty close and EMA 50 both above EMA 200, **down** = both below, **chop** = anything in between.

### What the five years say

1. **One giant year.** 2023 was the broad rally: smallcaps +78%, midcaps +60%, PSE +77%, Realty +80%. 2024 carried it on. Most of the five-year return came from these two years.
2. **2026 is a bear market for large caps.** Nifty spent 71% of 2026's days in the down regime and is −11.8% for the year. IT, FMCG, Fin Services and Bank are all negative. Pharma (+19%) and Metal (+6%) are the only sector indices up.
3. **Leadership rotates every year.** PSU banks led 2022, Realty and PSE led 2023, Pharma led 2024 and 2026, PSU banks again in 2025. No sector was in the top three every year. A strategy that is tied to one sector would have failed.
4. **Old leaders became laggards.** IT lost money over five years (−1.6% CAGR, −44% drawdown) and FMCG made 2.5% a year. The money was in PSU, capital goods, autos, metals and pharma: domestic capex and manufacturing, not software exports or staples.
5. **Smaller stocks trended far more.** The smallcap basket was above its EMA 200 on 90% of days, Nifty on 74%, IT on 50%. Trend following works best where trends are long, which is why strategy 1 does best on smallcaps.

## 2. Strategy 1 over the same five years

4,072 trades across the three universes (daily rules, live config, 1-hour re-entries not included): 33% win, average +3.65% per trade after costs.

### It earns most of its money in a few places

| Fact | Number |
|---|---|
| Share of all profit made by trades opened in 2023 | **70%** |
| Share of total return made by the best 10% of trades | **147%** (the other 90% lose money together) |
| Trades held 30 bars or less | 2,874, win rate 6–18%, all net losers |
| Trades held over 30 bars | 1,198, win rate 91%, all the profit |

This is the nature of trend following, not a bug: many small losses buy the ticket to a few huge winners. It does mean a quiet year can easily end flat.

### It captures only part of a bull market

| Year | Smallcap: strategy | Smallcap: buy & hold* | Midcap: strategy | Midcap: buy & hold* | Nifty: strategy | Nifty: buy & hold* |
|---|---|---|---|---|---|---|
| 2022 | +4.4% | +14.7% | −1.4% | +10.0% | 0.0% | +10.7% |
| 2023 | +46.9% | +79.3% | +32.6% | +61.2% | +21.3% | +40.6% |
| 2024 | +14.8% | +44.1% | +17.6% | +40.8% | +10.9% | +21.8% |
| 2025 | +3.0% | +11.2% | +3.1% | +9.4% | +1.3% | +13.9% |
| 2026 | +10.8% | +17.0% | −1.2% | −4.5% | −2.5% | −4.1% |

\* equal-weight basket of today's members, so buy & hold is flattered. One slot per stock, so the strategy is invested only about 38% of the time.

On a day-by-day basis by Nifty regime (annualised, smallcap universe): up days +21% vs +44% for buy & hold, chop days −12% vs −59%, down days +8% vs +33%. The strategy loses far less in chop, but it is out of the market for a large part of every rally.

### Where it is weak

1. **Chop.** In sideways phases it keeps buying breakouts that fail, losing about −4.5% each time. 55% of losing trades never rose above +2%. They were wrong from day one.
2. **Long dry spells.** 2022 and 2025 were near flat on every universe while buy & hold made 9–15%. Someone trading it live must sit through a year or more of small losses.
3. **Giveback.** Trades that reached +10% at some point peaked at +37% on average but closed at +20%. Winners kept a median of 43% of their peak gain, because the EMA 50 exit is far below the price in a strong trend.
4. **Weak entry rule.** The EMA 20 reclaim re-entry is the weakest rule: 126 trades, 26% win rate, profit factor 1.2, under 1% of the profit.
5. **Mid-strength ADX.** Entries with ADX 25–35 did worst (profit factor 1.6). ADX 15–20 (a trend just starting) and ADX above 35 (a very strong trend) did best.
6. **Weak sectors.** Construction Materials, Textiles, Power and Chemicals barely broke even. Capital Goods alone made 27% of all profit.

### Where it is strong

- **EMA 20 pullback rejected** is the best entry: 41% win rate, profit factor 3.1.
- **Extended entries are not bad entries.** Trades opened 10–20% above EMA 50 won 43% of the time and those over 20% above won 50%. Strong momentum kept going; "do not chase" would have hurt.
- **Low VIX (<12)** gave the best trades (profit factor 3.6). Calm markets let trends run.
- **Breadth extremes:** entries when under 30% or over 70% of stocks were above EMA 50 did best. The middle (30–70%) was the weakest.

## 3. Fixes tested, and why none went in

Each fix was judged on 2018–2023 and 2024 onwards, with all stocks and with 10 slots. CAGR, test period:

| Variant | Smallcap, all | Smallcap, 10 slots | Midcap, 10 slots | Nifty, 10 slots |
|---|---|---|---|---|
| **Live config** | **9.7%** | **36.8%** | **18.0%** | **7.2%** |
| A: drop EMA 20 reclaim | 9.7% | 34.6% | 15.3% | 7.2% |
| B: trailing exit on EMA 20 once +20% | 7.0% | 32.5% | 15.7% | 3.2% |
| B: same, once +30% | 7.2% | 29.7% | 17.4% | 3.2% |
| B: same, once +50% | 8.6% | 35.6% | 13.5% | 3.8% |
| A + B (+30%) | 7.2% | 24.6% | 12.7% | 3.0% |

- **The trailing exit made things worse everywhere.** The giveback is the price of staying in the few trades that go +100%; a tighter exit throws those out early.
- **Dropping the reclaim rule changed nothing** on all-stock portfolios and hurt with 10 slots. It is weak, but it fires rarely and does no harm.

**Strategy 1 stays exactly as it is.** Its weaknesses are the built-in costs of trend following: small losses in chop, long flat spells, and giving back part of each big win. The study shows them clearly so they are expected, not a surprise.

## 4. Lessons for a trader using it

1. Expect 7 of 10 trades to lose about 4–5%. Judge the system over 30+ trades, never over one.
2. Expect years like 2022 and 2025: flat while the index rises. That is when most people quit, right before a 2023.
3. Smallcaps suit it best; Nifty large caps the least. Keep paper trading on smallcap 100.
4. With 10 slots, drawdowns of about −24% are normal. Size real money so a −25% drop is bearable.
5. Sector leadership rotates every year, so let the scanner pick the stocks; do not lock in favourite sectors.
6. Nothing here guarantees future returns. All results are backtests on today's index members.
