"""
ULTRA PRESCREENER - Quality + Dislocation
Cuts 12k → 1k–3k intelligently before heavy analysis
"""

import yfinance as yf
import pandas as pd
import json
from pathlib import Path
import math
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# ============================================================
# CONFIG
# ============================================================

INPUT_JSON = "/Users/jazzhashzzz/Desktop/Screener For Spreads/ticker.json"
OUTPUT_TICKERS = "/Users/jazzhashzzz/Desktop/Screener For Spreads/ticker_filtered.txt"

BATCH_SIZE = 100
MIN_PRICE = 5
MIN_AVG_VOL = 800_000
MIN_DRAWDOWN = -8    # Require at least 15% below 1Y high
LOOKBACK_DAYS = 252    # 1 year lookback

# ============================================================
# LOAD TICKERS
# ============================================================

def load_tickers_from_json(path):
    with open(path, 'r') as f:
        data = json.load(f)

    tickers = []
    for key in data:
        if 'ticker' in data[key]:
            ticker = data[key]['ticker'].strip().upper()
            tickers.append(ticker)

    return tickers

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# ============================================================
# LIGHT FUNDAMENTAL FILTER
# ============================================================

def quick_fundamental_check(ticker):
    """
    Lightweight quality gate.
    Avoid deep calls — just eliminate obvious junk.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.fast_info  # much faster than full .info

        # fallback if needed
        if info is None:
            return False

        # basic profitability proxy
        pe = stock.info.get("trailingPE", None)
        revenue_growth = stock.info.get("revenueGrowth", None)

        if pe is None or pe <= 0:
            return False

        if revenue_growth is not None and revenue_growth < -0.15:
            return False

        return True

    except:
        return False

# ============================================================
# MAIN
# ============================================================

def main():

    print("\n" + "=" * 60)
    print("CAPITAL-READY PRESCREENER")
    print("=" * 60)

    tickers = load_tickers_from_json(INPUT_JSON)
    print(f"\nLoaded {len(tickers):,} tickers")

    passed_price = []
    passed_final = []

    total_batches = math.ceil(len(tickers) / BATCH_SIZE)
    print(f"\nProcessing {total_batches} batches...")

    # --------------------------------------------------------
    # STEP 1: BULK PRICE + LIQUIDITY + DRAWDOWN
    # --------------------------------------------------------

    for i, batch in enumerate(chunk(tickers, BATCH_SIZE), 1):

        print(f"Batch {i:3d}/{total_batches}", end=" ", flush=True)

        try:
            data = yf.download(
                batch,
                period="1y",
                group_by="ticker",
                auto_adjust=True,
                threads=False,
                progress=False
            )
        except:
            print("✗ Download failed")
            continue

        batch_passed = 0

        for ticker in batch:
            try:
                if len(batch) == 1:
                    df = data
                else:
                    df = data[ticker]

                if len(df) < 60:
                    continue

                price = df["Close"].iloc[-1]
                avg_vol = df["Volume"].mean()

                # 1Y high drawdown
                high_1y = df["Close"].max()
                drawdown = (price - high_1y) / high_1y * 100

                if (
                    price >= MIN_PRICE and
                    avg_vol >= MIN_AVG_VOL and
                    drawdown <= MIN_DRAWDOWN
                ):
                    passed_price.append(ticker)
                    batch_passed += 1

            except:
                continue

        print(f"✓ {batch_passed}")

    print(f"\nAfter price/dislocation filter: {len(passed_price):,}")

    # --------------------------------------------------------
    # STEP 2: LIGHT FUNDAMENTAL GATE
    # --------------------------------------------------------

    print("\nRunning light fundamental checks...")

    for i, ticker in enumerate(passed_price, 1):
        print(f"[{i}/{len(passed_price)}] {ticker}", end=" ", flush=True)

        if quick_fundamental_check(ticker):
            passed_final.append(ticker)
            print("✓")
        else:
            print("✗")

    # --------------------------------------------------------
    # SAVE OUTPUT
    # --------------------------------------------------------

    Path(OUTPUT_TICKERS).parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_TICKERS, "w") as f:
        for t in passed_final:
            f.write(f"{t}\n")

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Initial universe: {len(tickers):,}")
    print(f"After price + drawdown: {len(passed_price):,}")
    print(f"After quality gate: {len(passed_final):,}")
    print(f"Reduction: {(1 - len(passed_final)/len(tickers))*100:.1f}%")
    print(f"\nSaved to: {OUTPUT_TICKERS}")
    print("=" * 60)

# ============================================================

if __name__ == "__main__":
    main()
