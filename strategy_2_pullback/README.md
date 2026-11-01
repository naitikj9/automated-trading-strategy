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

```bash
python strategy_2_pullback/study.py          # comparison table
python strategy_2_pullback/study.py --grid   # re-tune on 2018-2023
```
