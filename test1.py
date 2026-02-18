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
    # SECTOR CRASH STUDY
    # =====================================================

    print("\nRunning sector crash analysis...")

    results = []

    for sector in fundamentals_df["sector"].unique():
        
        sector_tickers = fundamentals_df[
            fundamentals_df["sector"] == sector
        ]["ticker"].values

        if len(sector_tickers) < 3:
            continue

        # Get prices for this sector
        # intersection with columns to be safe
        available_tickers = [t for t in sector_tickers if t in price_data.columns]
        if not available_tickers:
            continue
            
        sector_prices = price_data[available_tickers].dropna()

        if sector_prices.empty:
            continue

        # Calculate Sector Return
        sector_returns = sector_prices.pct_change(LOOKBACK_DAYS)

        # Iterate through dates
        for date in sector_returns.index:
            
            # Mean return of the sector on this date (trailing 20 days)
            sector_ret = sector_returns.loc[date].mean()

            if sector_ret < SECTOR_CRASH_THRESHOLD:

                for ticker in available_tickers:
                    try:
                        entry_price = sector_prices.loc[date, ticker]
                        
                        # Find exit index
                        loc_idx = sector_prices.index.get_loc(date)
                        exit_idx = loc_idx + FORWARD_DAYS

                        if exit_idx >= len(sector_prices.index):
                            continue

                        exit_date = sector_prices.index[exit_idx]
                        exit_price = sector_prices.loc[exit_date, ticker]

                        fwd_return = (exit_price / entry_price) - 1

                        stock_fund = fundamentals_df[
                            fundamentals_df["ticker"] == ticker
                        ].iloc[0]

                        results.append({
                            "sector": sector,
                            "ticker": ticker,
                            "forward_return": fwd_return,
                            "pe": stock_fund["pe"],
                            "revenue_growth": stock_fund["revenue_growth"]
                        })

                    except KeyError:
                        continue
                    except Exception:
                        continue

    results_df = pd.DataFrame(results)

    # =====================================================
    # ANALYSIS
    # =====================================================

    if results_df.empty:
        print("\nNo sector crash events found.")
    else:
        median_pe = results_df["pe"].median()

        # Define Strong: Low PE + Positive Growth
        results_df["strong"] = (
            (results_df["pe"] < median_pe) &
            (results_df["revenue_growth"] > 0)
        )

        strong = results_df[results_df["strong"]]["forward_return"]
        weak = results_df[~results_df["strong"]]["forward_return"]

        print("\n====================================")
        print("SECTOR CRASH FUNDAMENTAL RESULTS")
        print("====================================")
        print(f"Total Observations: {len(results_df)}")

        if len(strong) > 0:
            print("\nStrong Fundamentals:")
            print("Mean:", round(strong.mean(), 4))
            print("Median:", round(strong.median(), 4))
            print("Win Rate:", round((strong > 0).mean(), 4))

        if len(weak) > 0:
            print("\nWeak Fundamentals:")
            print("Mean:", round(weak.mean(), 4))
            print("Median:", round(weak.median(), 4))
            print("Win Rate:", round((weak > 0).mean(), 4))

        if len(strong) > 0 and len(weak) > 0:
            print("\nDifference (Strong - Weak Mean):",
                  round(strong.mean() - weak.mean(), 4))