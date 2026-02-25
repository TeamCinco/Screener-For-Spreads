"""
This screener may be a little 
to expensive and not fast at all, but well see. 
Structural filter only.
Everything heavy stays in main screener.
"""

import yfinance as yf
import pandas as pd
import json
from pathlib import Path
import math
import warnings
warnings.filterwarnings("ignore")

# ============================================================
# CONFIG
# ============================================================

INPUT_JSON = "/Users/jazzhashzzz/Desktop/Screener For Spreads/ticker.json"
OUTPUT_TICKERS = "/Users/jazzhashzzz/Desktop/Screener For Spreads/ticker_filtered.txt"

BATCH_SIZE = 100
MIN_PRICE = 5
MIN_AVG_VOL = 4_000_000
MIN_DRAWDOWN = -4
MIN_CURRENT_RATIO = 0.8

# ============================================================
# LOAD TICKERS
# ============================================================

def load_tickers_from_json(path):
    with open(path, 'r') as f:
        data = json.load(f)

    tickers = []
    for key in data:
        ticker = data[key].get("ticker")
        if ticker:
            tickers.append(ticker.strip().upper())

    return list(set(tickers))


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# ============================================================
# LIGHT FUNDAMENTAL FILTER (Moved from main screener)
# ============================================================

def structural_fundamental_gate(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        pe = info.get("trailingPE")
        revenue_growth = info.get("revenueGrowth")

        # Must be profitable
        if pe is None or pe <= 0:
            return False

        # Avoid severe revenue collapse
        if revenue_growth is not None and revenue_growth < -0.25:
            return False

        # Basic liquidity sanity
        try:
            balance = stock.balance_sheet
            if balance is not None and not balance.empty:

                current_assets = balance.loc["Total Current Assets"].iloc[0]
                current_liabilities = balance.loc["Total Current Liabilities"].iloc[0]

                if current_liabilities and current_liabilities != 0:
                    current_ratio = current_assets / current_liabilities
                    if current_ratio < MIN_CURRENT_RATIO:
                        return False
        except:
            pass

        return True

    except:
        return False


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n" + "="*60)
    print("ULTRA PRESCREENER")
    print("="*60)

    tickers = load_tickers_from_json(INPUT_JSON)
    print(f"\nLoaded {len(tickers):,} tickers")

    passed_price = []
    passed_final = []

    total_batches = math.ceil(len(tickers) / BATCH_SIZE)

    print(f"\nProcessing {total_batches} batches...")

    # --------------------------------------------------------
    # STEP 1: BULK PRICE FILTER
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
            print("✗")
            continue

        batch_passed = 0

        for ticker in batch:
            try:
                df = data if len(batch) == 1 else data[ticker]

                if len(df) < 60:
                    continue

                price = df["Close"].iloc[-1]
                avg_vol = df["Volume"].mean()
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

    print(f"\nAfter structural price filter: {len(passed_price):,}")

    # --------------------------------------------------------
    # STEP 2: STRUCTURAL FUNDAMENTAL FILTER
    # --------------------------------------------------------

    print("\nRunning structural fundamental filter...")

    for i, ticker in enumerate(passed_price, 1):
        print(f"[{i}/{len(passed_price)}] {ticker}", end=" ")

        if structural_fundamental_gate(ticker):
            passed_final.append(ticker)
            print("✓")
        else:
            print("✗")

    # Save output
    Path(OUTPUT_TICKERS).parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_TICKERS, "w") as f:
        for t in passed_final:
            f.write(f"{t}\n")

    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"Initial universe: {len(tickers):,}")
    print(f"After structural filter: {len(passed_final):,}")
    print(f"Reduction: {(1 - len(passed_final)/len(tickers))*100:.1f}%")
    print(f"\nSaved to: {OUTPUT_TICKERS}")
    print("="*60)


if __name__ == "__main__":
    main()
