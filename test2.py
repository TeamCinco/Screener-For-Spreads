"""
Sector Crash Fundamental Study
Hypothesis Tested
The script tests whether fundamental quality acts as a safety net. 
Specifically: Do stocks with strong valuation and growth metrics outperform 
weaker stocks during the rebound phase of a sector-wide panic?
"""

import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path
import time
import warnings

# Suppress the messy YF warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# =====================================================
# CONFIG
# =====================================================

TICKER_FILE = "/Users/jazzhashzzz/Desktop/Screener For Spreads/ticker_filtered.txt"

START_DATE = "2020-01-01"
END_DATE = "2025-01-01"

LOOKBACK_DAYS = 90
FORWARD_DAYS = 45
SECTOR_CRASH_THRESHOLD = -0.10  # -10%
CHUNK_SIZE = 100

# =====================================================
# LOAD TICKERS
# =====================================================

def load_tickers(file_path):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Ticker file not found: {file_path}")

    with open(path, "r") as f:
        tickers = [
            line.strip().upper()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

    # Remove obvious non-equity junk
    tickers = [
        t for t in tickers
        if "-" not in t and "." not in t and len(t) <= 5
    ]

    return list(set(tickers))

print("\nLoading tickers...")
TICKERS = load_tickers(TICKER_FILE)
print(f"Loaded {len(TICKERS)} cleaned tickers")

# =====================================================
# DOWNLOAD PRICE DATA (ROBUST VERSION)
# =====================================================

print("\nDownloading price history in chunks...")

def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

all_prices = []

for i, chunk in enumerate(chunk_list(TICKERS, CHUNK_SIZE), 1):
    print(f"Chunk {i}... ({len(chunk)} tickers)")

    try:
        # FIX 1: Set auto_adjust=False to ensure 'Adj Close' exists
        # FIX 2: Enable threads for speed
        data = yf.download(
            chunk,
            start=START_DATE,
            end=END_DATE,
            progress=False,
            auto_adjust=False, 
            threads=True
        )

        if data.empty:
            continue

        # FIX 3: Safe column extraction
        # yfinance can return MultiIndex (Price, Ticker) or Single Index depending on results
        
        # Determine which column to grab
        target_col = None
        if "Adj Close" in data.columns:
            target_col = "Adj Close"
        elif "Close" in data.columns:
            target_col = "Close"
        
        if target_col is None:
            print(f"  > Warning: No price data found in Chunk {i}")
            continue

        # Extract the specific price column
        if isinstance(data.columns, pd.MultiIndex):
            adj_close = data[target_col]
        else:
            # If a single level index is returned, we must be careful.
            # Usually happens if only 1 ticker was requested or returned.
            adj_close = data[[target_col]]
            # If we submitted a list but got a single level, YF might have collapsed it.
            # In bulk downloads, it's safer to rely on the MultiIndex structure.
            # If this hits, we skip renaming to avoid the "Length mismatch" error.

        # Basic data validation
        if not adj_close.empty:
            # Drop columns that are entirely NaN (failed downloads in the batch)
            adj_close = adj_close.dropna(axis=1, how='all')
            
            if not adj_close.empty:
                all_prices.append(adj_close)
                print(f"  > Success: Added {len(adj_close.columns)} tickers")

    except Exception as e:
        print(f"Chunk failed: {e}")

if len(all_prices) == 0:
    raise ValueError("No price data downloaded. Check your internet or ticker list.")

print("\nAggregating data...")
price_data = pd.concat(all_prices, axis=1)

# Remove duplicate columns (tickers)
price_data = price_data.loc[:, ~price_data.columns.duplicated()]

# Final cleanup of empty columns
price_data = price_data.dropna(axis=1, how="all")

print(f"Final price universe: {len(price_data.columns)} tickers")

if price_data.empty:
    raise ValueError("Price data is empty after cleaning.")

# =====================================================
# PULL FUNDAMENTALS
# =====================================================

print("\nPulling fundamentals (this may take time)...")

fundamentals = []
valid_tickers_list = price_data.columns.tolist()

# Rate limit batching
for i, ticker in enumerate(valid_tickers_list):
    if i % 50 == 0 and i > 0:
        print(f"Processed {i}/{len(valid_tickers_list)}...")
        
    try:
        stock = yf.Ticker(ticker)
        # fast_info is often faster/more reliable than .info for some stats, 
        # but for PE/RevenueGrowth we need .info
        info = stock.info

        # Check if keys exist to avoid errors
        if 'sector' in info and 'trailingPE' in info:
            fundamentals.append({
                "ticker": ticker,
                "sector": info.get("sector"),
                "pe": info.get("trailingPE"),
                "revenue_growth": info.get("revenueGrowth", 0) # Default to 0 if missing
            })
    except:
        continue

fundamentals_df = pd.DataFrame(fundamentals)

if fundamentals_df.empty:
    print("Warning: No fundamentals found. Cannot proceed with analysis.")
else:
    fundamentals_df = fundamentals_df.dropna(subset=['sector', 'pe']) # strictly need these
    print(f"Tickers with usable fundamentals: {len(fundamentals_df)}")

    # Keep only valid tickers in price data
    valid_tickers = fundamentals_df["ticker"].tolist()
    price_data = price_data.loc[:, price_data.columns.isin(valid_tickers)]

    # =====================================================
    # INDIVIDUAL 2-SIGMA CRASH STUDY
    # =====================================================

    print("\nRunning 2-sigma crash analysis...")

    ROLLING_WINDOW = 60
    SIGMA_THRESHOLD = -2
    FORWARD_WINDOWS = [10, 21, 45]

    results = []

    for ticker in price_data.columns:

        prices = price_data[ticker].dropna()

        if len(prices) < ROLLING_WINDOW + max(FORWARD_WINDOWS):
            continue

        returns = prices.pct_change()

        rolling_mean = returns.rolling(ROLLING_WINDOW).mean()
        rolling_std = returns.rolling(ROLLING_WINDOW).std()

        z_scores = (returns - rolling_mean) / rolling_std

        crash_dates = z_scores[z_scores < SIGMA_THRESHOLD].index

        for date in crash_dates:

            try:
                entry_price = prices.loc[date]
                loc_idx = prices.index.get_loc(date)

                stock_fund = fundamentals_df[
                    fundamentals_df["ticker"] == ticker
                ]

                if stock_fund.empty:
                    continue

                stock_fund = stock_fund.iloc[0]

                for fw in FORWARD_WINDOWS:

                    exit_idx = loc_idx + fw
                    if exit_idx >= len(prices.index):
                        continue

                    exit_price = prices.iloc[exit_idx]
                    fwd_return = (exit_price / entry_price) - 1

                    results.append({
                        "ticker": ticker,
                        "forward_days": fw,
                        "forward_return": fwd_return,
                        "pe": stock_fund["pe"],
                        "revenue_growth": stock_fund["revenue_growth"]
                    })

            except:
                continue

    results_df = pd.DataFrame(results)



# =====================================================
# ANALYSIS
# =====================================================

if results_df.empty:
    print("\nNo 2-sigma events found.")
else:

    print("\n====================================")
    print("2-SIGMA CRASH STUDY RESULTS")
    print("====================================")
    print(f"Total Events: {len(results_df)}")

    median_pe = results_df["pe"].median()

    results_df["strong"] = (
        (results_df["pe"] < median_pe) &
        (results_df["revenue_growth"] > 0)
    )

    for fw in sorted(results_df["forward_days"].unique()):

        subset = results_df[results_df["forward_days"] == fw]

        strong = subset[subset["strong"]]["forward_return"]
        weak = subset[~subset["strong"]]["forward_return"]

        print(f"\n--- Forward {fw} Days ---")

        if len(strong) > 0:
            print("Strong Fundamentals:")
            print("Mean:", round(strong.mean(), 4))
            print("Win Rate:", round((strong > 0).mean(), 4))
            print("Prob < -5%:", round((strong < -0.05).mean(), 4))

        if len(weak) > 0:
            print("\nWeak Fundamentals:")
            print("Mean:", round(weak.mean(), 4))
            print("Win Rate:", round((weak > 0).mean(), 4))
            print("Prob < -5%:", round((weak < -0.05).mean(), 4))
