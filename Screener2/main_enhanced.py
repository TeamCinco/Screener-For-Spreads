"""
Monte Carlo Capital Deployment Screener
Stable Main Controller
"""

import sys
import signal
import time
from pathlib import Path

# Add engine directory to path
engine_path = Path(__file__).parent / "engine"
sys.path.insert(0, str(engine_path))

from engine.ticker_loader import load_tickers
from engine.screener_engine_simple import analyze_stock
from engine.excel_writer_simple import write_results_to_excel

# ============================================================
# CONFIG
# ============================================================

TICKER_FILE = "/Users/jazzhashzzz/Desktop/Screener For Spreads/ticker_filtered.txt"
OUTPUT_FILE = "/Users/jazzhashzzz/Desktop/Screener For Spreads/output/screener_results.xlsx"

DAYS_TO_SIMULATE = 90
NUM_SIMULATIONS = 5000
HISTORICAL_WINDOW = 252 * 3

RESULTS = []

# ============================================================
# CTRL+C SAVE
# ============================================================

def signal_handler(sig, frame):
    print("\n\nInterrupted. Saving partial results...")
    if RESULTS:
        write_results_to_excel(RESULTS, OUTPUT_FILE)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ============================================================
# MAIN
# ============================================================

def main():

    global RESULTS

    print("\n" + "="*70)
    print("CAPITAL DEPLOYMENT MONTE CARLO SCREENER")
    print("="*70)

    tickers = load_tickers(TICKER_FILE)
    print(f"\nLoaded {len(tickers)} tickers")

    for i, ticker in enumerate(tickers, 1):

        print(f"[{i}/{len(tickers)}] {ticker}...", end=" ", flush=True)

        result = analyze_stock(
            ticker,
            days_to_simulate=DAYS_TO_SIMULATE,
            num_simulations=NUM_SIMULATIONS,
            historical_window=HISTORICAL_WINDOW
        )

        if result.get("success"):
            RESULTS.append(result)
            print(f"✓ Z={result['z_score']:.2f}, DD={result['drop_from_high_pct']:.1f}%")
        else:
            print(f"✗ {result.get('error')}")

        time.sleep(0.2)  # prevent Yahoo rate limits

        # autosave every 50
        if i % 50 == 0 and RESULTS:
            print("\nAuto-saving...")
            write_results_to_excel(RESULTS, OUTPUT_FILE)

    print("\nFinished.")
    if RESULTS:
        write_results_to_excel(RESULTS, OUTPUT_FILE)
    else:
        print("No successful results.")

if __name__ == "__main__":
    main()
