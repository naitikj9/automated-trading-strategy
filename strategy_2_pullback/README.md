# Strategy 2: DMI pullback

A second strategy, built for a higher win rate. Strategy 1 (`dmi_macd`, `config/config.yaml`) and its paper trading are unchanged.

Code: [`src/trading/strategies/pullback.py`](../src/trading/strategies/pullback.py) · settings: [`config.yaml`](config.yaml) · study: [`study.py`](study.py)

## Rules (daily close)

**Buy**, all of:
1. Close above EMA 50, and EMA 20 above EMA 50
2. +DI above −DI, and ADX at least 15
3. Stochastic (14, 3, 3) %K dipped below 40 within the last 5 bars
4. %K crosses back above %D

**Sell**, whichever comes first:
- Target: close 2 ATR above the entry
- Stop: close 2 ATR below the entry, or below EMA 50
- Stochastic %K above 80
- 20 bars held

The idea: buy a dip inside a trend that is already strong, and book the bounce instead of riding the whole trend.

## Results vs strategy 1

Equal-weight portfolio of each index, daily bars, with costs. Settings were tuned on 2018–2023 only (`study.py --grid`, 96 combinations), then tested on 2024–Oct 2026 and on the last year (31 Oct 2025 – 30 Oct 2026).

| Index | Period | Strategy | Win rate | Avg win | Avg loss | CAGR | Sharpe | Max DD | Time in market |
|---|---|---|---|---|---|---|---|---|---|
| Smallcap 100 | test | 1 | 30% | +21.9% | −5.1% | 10.2% | 1.22 | −7.7% | 38% |
| | | **2** | **45%** | +7.0% | −5.1% | 1.2% | 0.62 | −2.7% | 7% |
| | last year | 1 | 33% | +23.3% | −5.1% | 10.1% | 1.37 | −4.5% | 35% |
| | | **2** | **41%** | +6.8% | −4.7% | −0.3% | −0.15 | −1.8% | 7% |
| Midcap 100 | test | 1 | 30% | +15.4% | −4.3% | 6.7% | 0.85 | −6.4% | 39% |
| | | **2** | **49%** | +5.4% | −4.8% | 0.8% | 0.52 | −2.2% | 6% |
| Nifty 50 | test | 1 | 32% | +9.2% | −3.7% | 3.3% | 0.55 | −7.5% | 39% |
| | | **2** | **53%** | +3.9% | −3.6% | 0.8% | 0.68 | −1.9% | 5% |

## Verdict

- **Win rate goes up**, from about 30% to 45–53% on unseen data (51–58% on the training years).
- **Returns go down a lot.** Winners are much smaller (+4% to +7% instead of +9% to +22%), so each trade earns little after costs. The capital also sits in the market only 5–7% of the time.
- **The last year was negative** on every index, while strategy 1 made +10% on smallcaps.

So a higher win rate here does not mean more money. Strategy 1 stays the main strategy. Strategy 2 is kept as a tested alternative and as a base for further work, such as a market filter or putting all the capital into the few open trades.

## Improvement attempt: market filter and concentrated capital

[`portfolio.py`](portfolio.py) adds two layers on top of either strategy, and [`improve.py`](improve.py) tests them:

- **Market filter:** new entries only while at least X% of the index's stocks close above their EMA 50 (tried 40/50/60%).
- **Slots:** capital in 5, 10 or 20 equal parts instead of one part per stock. When more stocks signal than there are free slots, the strongest ADX goes first.

Chosen on 2018–2023: **10 slots, no market filter**. Every filter level lowered training Sharpe, although in the last year a 50% filter did cut the loss.

| Index | Period | Strategy 2, all stocks | **Strategy 2, 10 slots** | Strategy 1, all stocks | Strategy 1, 10 slots |
|---|---|---|---|---|---|
| Smallcap 100 | test | 1.0%, DD −2.7% | **10.0%, DD −19.9%** | 9.7%, DD −7.3% | 36.8%, DD −23.5% |
| | last year | −0.3% | **+0.2%** | +10.1% | +38.2% |
| Midcap 100 | test | 0.7%, DD −2.2% | **4.0%, DD −20.2%** | 6.4%, DD −6.3% | 18.0%, DD −20.5% |
| | last year | −1.2% | **−12.3%** | +0.4% | +4.7% |
| Nifty 50 | test | 0.8%, DD −1.9% | **4.6%, DD −9.2%** | 3.3%, DD −7.5% | 7.2%, DD −16.4% |
| | last year | −1.8% | **−8.8%** | −2.4% | +0.1% |

CAGR, daily bars, with costs. Win rates do not change with slots: strategy 2 stays at 45–54%, strategy 1 at about 30%.

**Verdict.**
- Concentrating capital raises strategy 2's return about tenfold, from about 1% to 4–10% a year. It also raises drawdown to 9–20%.
- Strategy 2 still loses to strategy 1 in every index, and it lost money in the last year in midcaps and Nifty 50.
- The same 10-slot sizing lifts strategy 1 far more: 37% CAGR on smallcaps in 2024–26 and +38% in the last year. Drawdown also rises to −24%.
- Caveat: these are today's index members, and holding only 10 stocks magnifies that survivorship bias. Treat the 10-slot numbers as an upper bound until paper trading confirms them.

```bash
python strategy_2_pullback/study.py          # comparison table
python strategy_2_pullback/study.py --grid   # re-tune on 2018-2023
python strategy_2_pullback/improve.py        # slots x market filter
```
