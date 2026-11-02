# Automated Trading Strategy

A modular Python framework for designing, backtesting and (eventually) live-trading systematic strategies.

## Strategy: DMI + MACD trend following

Daily candles. A signal forms at the close. One position at a time. ✅ on in [`config/config.yaml`](config/config.yaml), ⚪ in the code but off.

### Buy entry
All four must hold, plus a MACD pattern (rule 12):

1. ✅ **+DI above −DI** (DMI 14, 14 is the main indicator)
2. ✅ **ADX at least 15 and rising**
3. ✅ **MACD (12, 26, 9) above its signal line.** The last crossover is graded: above zero is super strong, near zero is strong, below zero is normal.
4. ✅ **Close above EMA 20, and at least 2% above EMA 50** (the 2% buffer applies to every entry, so a trade does not open right on the exit line)

Re-entries, which skip the ADX and MACD checks because the trend is already established:

5. ✅ **+DI cross:** in an uptrend, +DI crosses back above −DI
6. ✅ **EMA 20 reclaim:** the pullback held EMA 50, and the close moves back above EMA 20, with +DI above −DI
7. ✅ **EMA 20 bounce:** the low comes within 2% of EMA 20, then the close tops the previous high, with +DI above −DI
8. ✅ **1-hour EMA cross:** while flat and the daily trend is intact, the 1-hour EMA 20 crosses above EMA 50 (enters during the day, not at the close)

Optional:

8a. ⚪ **EMA 20/50 golden cross:** buy when EMA 20 crosses above EMA 50 (`ema_cross_entry`)
9. ⚪ **Accumulation breakout:** 60 days inside a range no wider than 25%, then a close above it on 1.5× volume
10. ⚪ **POC retest:** after breaking above the value area, price bounces off the volume POC
11. ⚪ **POC filter:** buy only above POC
12. ✅ **MACD pattern required:** a double dip or divergence must be present for the main entry (re-entries skip it)

### Sell entry (⚪ off, since positional shorts need futures)
The buy rules mirrored. Every sell entry, re-entries included, needs **ADX at least 15 and rising**.

### Exit
- ✅ **Long:** the close falls below EMA 50
- ✅ **Short:** the close rises above EMA 50
- ⚪ **Divergence exit:** exit a long on a new bearish MACD divergence (`exit_on_divergence`; off, because it cut winners short on all three indices)
- ⚪ **DI exit:** also exit on the opposite DI cross (`exit_on_di_cross`; off, because exiting on EMA 50 alone did better on unseen data)

### Shown in the scanner
- MACD double dip / double top, regular and hidden divergence, confirmed without lookahead
- Accumulation range ("in base") and breakouts
- Volume profile: POC, value area, estimated buyer share
- Market Profile (TPO) POC

Indicator values match TradingView's built-in DMI, MACD and Stochastic.

## Worked example: Laurus Labs, 2026

```bash
python research/trade_example.py LAURUSLABS.NS --start 2026-01-01
```

| Entry | Why | Exit | Why | Return |
|---|---|---|---|---|
| 25 Feb, ₹1,075 | Trend entry: ADX 17.8 rising, +DI 28.8 vs −DI 16.5, MACD bullish with a pattern | 9 Mar, ₹1,020 | Close below EMA 50 | −5.1% |
| **23 Apr, ₹1,128** | **EMA 20 pullback rejected: ADX 19.3, +DI 26.5 vs −DI 17.5** | **open** | Price never closed below EMA 50 | **+113.3%** |

![Laurus Labs trades](docs/example_lauruslabs.png)

The pattern is typical of trend following: small losses while no trend forms, then one trade that rides the whole move. The same script on Nifty Pharma gives 4 trades and +10.0%, with the 29 Apr to 15 Sep trade making +12.6% ([chart](docs/example_cnxpharma.png)).

## Research

All studies run every stock in an NSE index as an equal-weight portfolio, with costs. Rules are judged on two periods:

- **Train:** 2018–2023
- **Test:** 2024–Oct 2026, unseen while the rules were built

### Current rules vs buy and hold

| Universe | Test CAGR | Test Sharpe | Test max DD | Buy & hold Sharpe | Buy & hold max DD |
|---|---|---|---|---|---|
| Smallcap 100 | 10.2% | 1.22 | −7.7% | 1.16 | −23.8% |
| Midcap 100 | 6.7% | 0.85 | −6.4% | 0.84 | −20.5% |
| Nifty 50 | 3.3% | 0.55 | −7.5% | 0.79 | −16.4% |

On small and midcaps the strategy matches or beats buy-and-hold on risk-adjusted return with a third of the drawdown. Raw return is lower everywhere, because capital sits idle more than half the time.

Across all trades since 2018, 27–33% of trades win. Winners average +15% to +27% and last about 58 days. Losers average −3% to −5% and last about 9 days.

### Which rules earn their place?

[`research/rule_ablation.py`](research/rule_ablation.py) flips one rule at a time against the config as it stood before the two audit fixes (the last two rows before shorts), which are now on. The table shows the change in **test-period Sharpe**; positive means the change helped.

| Change from the current config | Smallcap | Midcap | Nifty 50 | Verdict |
|---|---|---|---|---|
| Remove +DI cross re-entry | −0.13 | −0.19 | +0.07 | Keep: carries small and midcaps |
| Remove EMA 20 bounce entry | −0.01 | −0.06 | −0.05 | Keep |
| Remove EMA 20 reclaim re-entry | 0.00 | −0.01 | +0.01 | Neutral; it overlaps the +DI cross |
| ADX floor 15 → 0 | +0.04 | +0.04 | 0.00 | Small gain; the floor stays as a design choice |
| Skip re-entries inside a base | +0.03 | −0.01 | +0.11 | Mixed |
| POC filter | −0.09 | +0.09 | +0.01 | Mixed |
| POC retest entry | +0.05 | +0.01 | +0.01 | Small gain, mainly smallcaps |
| Accumulation breakout entry | −0.02 | +0.01 | −0.05 | Off |
| Exit on new bearish MACD divergence | −0.06 | −0.08 | −0.08 | Off: exits too early in strong trends |
| Buy on EMA 20/50 golden cross | −0.15 | +0.05 | −0.01 | Off: mixed, and drawdown rose everywhere |
| Exit on EMA 20/50 death cross | 0.00 | 0.00 | 0.00 | No effect: the EMA 50 exit always fires first |
| ✅ Re-entries also need +DI > −DI | 0.00 | 0.00 | 0.00 | On: neutral, but removes 17 smallcap entries that went against DMI |
| ✅ Long entry at least 2% above EMA 50 | +0.05 | +0.07 | +0.03 | On: helps everywhere, cuts one-day whipsaw trades |
| Allow shorts | −0.84 | −0.58 | −0.58 | Keep shorts off |
| Shorts without the MACD pattern (vs shorts with it) | −0.35 | −0.20 | −0.20 | If shorts are used, keep the pattern |

The two switches already on were measured against the config before them: requiring a MACD pattern added +0.08 / +0.09 / +0.04, and exiting on EMA 50 alone added +0.08 / +0.21 / +0.37.

### 1-hour re-entries

[`research/hourly_reentry_study.py`](research/hourly_reentry_study.py) keeps the daily entries and exits, and lets a flat position re-enter on a 1-hour trigger while the daily trend is intact. Yahoo keeps about two years of hourly data, so this covers 2024 onwards only.

| Universe | Daily only | 1h +DI cross | 1h EMA 20/50 cross | Either |
|---|---|---|---|---|
| Smallcap 100 | 9.9%, Sharpe 1.19 | 10.9%, 1.21 | 10.7%, 1.22 | 11.3%, 1.23 |
| Midcap 100 | 6.6%, 0.90 | 7.2%, 0.93 | 7.2%, 0.94 | 7.2%, 0.91 |
| Nifty 50 | 2.0%, 0.33 | 2.2%, 0.35 | 2.8%, 0.44 | 2.7%, 0.42 |

Hourly re-entries helped on every index. The EMA 20/50 cross gave the best Sharpe with the smallest rise in drawdown, so it is the one switched on. With only two years of hourly data there is no separate unseen period, so treat this gain as provisional.

### Audit

[`research/audit.py`](research/audit.py) checks the live config for two things:

- **Lookahead:** reruns the strategy on history cut at six dates, with every optional rule on, and confirms no earlier signal changes. None did.
- **Contradictions:** across 3,031 smallcap entries, none entered below EMA 50. 17 (0.6%) entered while −DI was above +DI, all through the EMA 20 reclaim/bounce re-entries. 255 (8.4%) lasted one bar; those entered a median 1.4% above EMA 50, against 4.5% for the rest.
- **Fixes, now on:** re-entries also need +DI > −DI, and every entry needs the close 2% above EMA 50. Rerun after the fixes: 2,620 entries, 0 against DMI, 0 below EMA 50, one-bar trades down from 255 to 94 (3.6%). Together they raised test Sharpe from 1.17 / 0.78 / 0.53 to 1.22 / 0.85 / 0.55 (smallcap / midcap / Nifty 50) and trimmed drawdown.

```bash
python research/rule_ablation.py --universe smallcap100   # or midcap100, nifty50
python research/hourly_reentry_study.py --universe smallcap100
python research/audit.py --universe smallcap100
python research/index_study.py --universe smallcap100     # parameter grid search
```

Caveat: these are today's index members, so earlier years carry survivorship bias. Daily bars approximate the volume and market profiles; TradingView uses intraday data.

### Five-year market study

[`docs/five_year_study.md`](docs/five_year_study.md) covers Nov 2021 to Oct 2026: Nifty, 15 sector indices, market regimes, and every strategy 1 trade broken down by year, regime, VIX, breadth, entry rule, ADX and sector. In short:

- 70% of the profit came from trades opened in 2023, and the best 10% of trades made all of it.
- The strategy captures roughly half of a bull market and loses far less than buy & hold in chop.
- A trailing exit and dropping the weakest entry rule were both tested; both made returns worse, so the rules stay as they are.

```bash
python research/five_year_study.py    # market, sectors and trade breakdown
python research/weakness_tests.py     # the fixes that were tested
```

The findings also feed a Claude Code skill, [`.claude/skills/stock-broker`](.claude/skills/stock-broker/SKILL.md), which answers market and trade questions from this data (`/stock-broker`).

## Strategy 2: DMI pullback

A second strategy, kept apart in [`strategy_2_pullback/`](strategy_2_pullback/README.md): it buys stochastic dips inside a DMI uptrend and books the bounce at a 2 ATR target. Its win rate is higher (45–53% on unseen data against ~30%), but its returns are far lower, so strategy 1 stays the live one.

## Paper trading

[`paper_trade.py`](paper_trade.py) runs the live config on fresh Yahoo data and keeps a saved book in `paper/` (`state.json`, `orders.csv`, `trades.csv`). The rules, fills and costs are the backtest's. Universe, capital and position limit are under `paper:` in the config.

```bash
python paper_trade.py daily    # after 15:45 IST: daily exits, then entries
python paper_trade.py hourly   # during the session, hourly: 1h EMA cross re-entries while flat
python paper_trade.py report   # open positions, closed trades, win rate, equity
```

Re-running is safe, because a bar that has already been acted on is skipped. Use `--folder` to dry-run without touching the real book.

**Mirror it in TradingView.** Each run prints its new orders as `BUY 24 x NSE:SYNGENE ~Rs 402.90`. In TradingView, open the trading panel, connect **Paper Trading**, and place the same market order. The script's book is the reference; TradingView lets you watch the same trades on the chart.

**Run it automatically on Windows.** [`run_paper.bat`](run_paper.bat) runs one check and appends the output to `logs/paper.log`. Clone the repo to a permanent folder, then schedule it from that folder:

```bat
schtasks /create /tn "PaperTrade daily" /tr "C:\path\to\repo\run_paper.bat daily" /sc weekly /d MON,TUE,WED,THU,FRI /st 16:00
schtasks /create /tn "PaperTrade hourly" /tr "C:\path\to\repo\run_paper.bat hourly" /sc weekly /d MON,TUE,WED,THU,FRI /st 10:20 /ri 60 /du 05:00
```

Limits: if the PC is off on a day, that day's daily signals are missed (the next run acts only on the latest bar). Yahoo prices arrive with a short delay. `max_positions: 10` puts capital in 10 equal slots (about Rs 1 lakh each), strongest ADX first. That sizing was backtested in [`strategy_2_pullback/improve.py`](strategy_2_pullback/README.md): about 37% CAGR on smallcaps in 2024–26, with drawdown up to −24%. Set it to `null` to split capital across every stock instead, as in the plain backtests.

## Daily scanner

```bash
python scan.py                      # watchlist from config
python scan.py BSE.NS LUPIN.NS      # or any symbols
```

Prints +DI, −DI, ADX, POC, buyer share, the MACD grade, patterns and today's action (BUY / EXIT / HOLD) for each stock.

## Features

- **Pluggable strategies** — subclass `Strategy`, implement `generate_signals`, register it.
- **Vectorised backtester** — next-bar execution (no look-ahead), commission and slippage.
- **Metrics** — total return, CAGR, Sharpe, max drawdown, trade count.
- **Risk manager** — position sizing and stop-loss levels.
- **Broker interface** — paper broker now; live broker adapters plug into the same API.
- **Config-driven** — symbol, dates, strategy params and costs live in `config/config.yaml`.
- **Tested** — pytest suite run on every push via GitHub Actions.

## Project structure

```
src/trading/
  indicators.py DMI/ADX, MACD, EMA, Stochastic, volume and market profile
  data/         market data loaders (Yahoo Finance, CSV)
  strategies/   Strategy base class + implementations
  backtest/     engine and performance metrics
  risk/         position sizing, stops
  broker/       broker interface, paper broker
config/         run configuration
research/       index studies, rule ablation, worked trade example
docs/           charts
tests/          unit tests
```

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
python run_backtest.py
pytest -q
```

## Adding a strategy

1. Create `src/trading/strategies/my_strategy.py` subclassing `Strategy`.
2. Add it to `REGISTRY` in `src/trading/strategies/__init__.py`.
3. Set `strategy.name` and `params` in `config/config.yaml`.

## Roadmap

- [x] DMI + MACD strategy and daily scanner
- [ ] Use Stochastic (14, 3, 3) as an entry filter
- [x] Train/test validation on Nifty 50, Midcap 100, Smallcap 100
- [ ] Rolling walk-forward validation
- [x] Per-trade reports with entry and exit reasons
- [ ] Live broker adapter
- [ ] Scheduling and alerts

## Disclaimer

For research and educational purposes. Not financial advice. Trading involves risk of loss.
