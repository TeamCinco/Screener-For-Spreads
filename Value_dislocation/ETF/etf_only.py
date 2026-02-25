"""
Extract ETFs from SEC JSON universe
Handles lowercase structure:
{"0":{"cik_str":1045810,"ticker":"NVDA","title":"..."}}
"""

import json
import yfinance as yf
from pathlib import Path
import time

# ============================================================
# CONFIG
# ============================================================

INPUT_JSON = "/Users/jazzhashzzz/Desktop/Screener For Spreads/ticker.json"
OUTPUT_ETFS = "/Users/jazzhashzzz/Desktop/Screener For Spreads/etf_only.txt"

DELAY = 0.02  # Yahoo throttle protection

# ============================================================
# LOAD TICKERS
# ============================================================

def load_tickers_from_json(path):
    with open(path, "r") as f:
        data = json.load(f)

    tickers = []

    for key in data:
        entry = data[key]

        ticker = entry.get("ticker")
        if not ticker:
            continue

        ticker = ticker.strip().upper()

        # Skip obvious warrants/units/SPAC garbage
        if ticker.endswith(("W", "U", "R")):
            continue

        tickers.append(ticker)

    return list(set(tickers))


# ============================================================
# ETF DETECTION
# ============================================================

def is_etf(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        qt = info.get("quoteType", "")

        if qt.upper() == "ETF":
            return True

        # secondary fallback
        if info.get("fundFamily") is not None:
            return True

        return False

    except:
        return False


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n" + "="*60)
    print("ETF EXTRACTION")
    print("="*60)

    tickers = load_tickers_from_json(INPUT_JSON)
    print(f"\nLoaded {len(tickers)} cleaned tickers")

    etfs = []

    for i, ticker in enumerate(tickers, 1):

        print(f"[{i}/{len(tickers)}] {ticker}...", end=" ")

        if is_etf(ticker):
            etfs.append(ticker)
            print("✓ ETF")
        else:
            print("✗")

        time.sleep(DELAY)

    # Save
    Path(OUTPUT_ETFS).parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_ETFS, "w") as f:
        for etf in sorted(etfs):
            f.write(f"{etf}\n")

    print("\n" + "="*60)
    print(f"Found {len(etfs)} ETFs")
    print(f"Saved to: {OUTPUT_ETFS}")
    print("="*60)


if __name__ == "__main__":
    main()
