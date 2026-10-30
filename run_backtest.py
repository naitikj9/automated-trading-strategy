"""Run a backtest from config/config.yaml."""
import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent / "src"))

from trading.backtest.engine import run_backtest  # noqa: E402
from trading.data.loader import load_csv, load_yfinance  # noqa: E402
from trading.strategies import get_strategy  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--csv", help="Use a local OHLCV CSV instead of downloading")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    if args.csv:
        data = load_csv(args.csv)
    else:
        data = load_yfinance(cfg["symbol"], cfg["start"], cfg.get("end"), cfg["interval"])

    strategy = get_strategy(cfg["strategy"]["name"], **cfg["strategy"]["params"])
    result = run_backtest(data, strategy.generate_signals(data), **cfg["backtest"])

    print(f"Strategy: {strategy.name} on {cfg['symbol']}")
    for key, value in result.stats.items():
        print(f"  {key:>14}: {value:.4f}" if isinstance(value, float) else f"  {key:>14}: {value}")


if __name__ == "__main__":
    main()
