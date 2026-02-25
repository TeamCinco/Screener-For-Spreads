"""
Deep Value Stock Screener — Main Controller
Runs the screener across all tickers with autosave and crash protection.

Usage:
    1. Update TICKER_FILE and OUTPUT_FILE paths below
    2. Run: python main_enhanced.py
    3. Ctrl+C to stop early — progress is saved automatically
"""

import sys
import signal
import time
from pathlib import Path

# Add engine directory to import path
sys.path.insert(0, str(Path(__file__).parent / "engine"))

from engine.ticker_loader import load_tickers
from engine.screener_engine_simple import analyze_stock
from engine.excel_writer_simple import write_results_to_excel


# ============================================================
# CONFIG — UPDATE THESE PATHS FOR YOUR MACHINE
# ============================================================

TICKER_FILE = "/Users/jazzhashzzz/Desktop/Screener For Spreads/ticker_filtered.txt"
OUTPUT_FILE = "/Users/jazzhashzzz/Desktop/Screener For Spreads/output/screener_results.xlsx"

AUTOSAVE_EVERY = 25       # Save progress every N tickers
DELAY_SECONDS = 0.15      # Pause between API calls to avoid rate limits


# ============================================================
# GLOBAL STATE
# ============================================================

RESULTS = []
INTERRUPTED = False


def handle_interrupt(sig, frame):
    """Catch Ctrl+C — finish current ticker, then save and exit."""
    global INTERRUPTED
    print("\n\nCtrl+C detected. Saving progress...")
    INTERRUPTED = True


signal.signal(signal.SIGINT, handle_interrupt)


def save_progress():
    """Write current results to Excel."""
    if not RESULTS:
        print("Nothing to save yet.")
        return
    try:
        write_results_to_excel(RESULTS, OUTPUT_FILE)
    except Exception as e:
        print(f"Save failed: {e}")


# ============================================================
# MAIN LOOP
# ============================================================

def main():
    global RESULTS, INTERRUPTED

    print("\n" + "=" * 60)
    print("DEEP VALUE STOCK SCREENER")
    print("=" * 60)

    tickers = load_tickers(TICKER_FILE)
    total = len(tickers)
    print(f"\nLoaded {total} tickers\n")

    start = time.time()

    for i, ticker in enumerate(tickers, 1):

        if INTERRUPTED:
            break

        print(f"[{i}/{total}] {ticker}...", end=" ", flush=True)

        try:
            result = analyze_stock(ticker)

            if result.get("success"):
                RESULTS.append(result)
                score = result.get("deep_value_score", 0)
                sig = result.get("signal", "?")
                print(f"Score={score}  Signal={sig}")
            else:
                print(f"SKIP — {result.get('error', 'unknown error')}")

        except Exception as e:
            print(f"ERROR — {e}")

        # Autosave checkpoint
        if i % AUTOSAVE_EVERY == 0 and RESULTS:
            print("\n--- Autosaving ---")
            save_progress()
            print("")

        time.sleep(DELAY_SECONDS)

    # Final save
    print("\nDone scanning.")
    save_progress()

    elapsed = time.time() - start
    print(f"\nFinished in {elapsed:.1f}s")
    print(f"Results: {len(RESULTS)} / {total} tickers")


if __name__ == "__main__":
    main()