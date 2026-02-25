"""
Deep Value Capital Deployment Screener
Main Controller — Graceful Shutdown + Autosave + Crash Safe

Compatible with:
- engine/screener_engine_simple.py
- engine/excel_writer_simple.py
- engine/ticker_loader.py
"""

import sys
import signal
import time
from pathlib import Path

# ============================================================
# ADD ENGINE DIRECTORY TO PATH
# ============================================================

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

AUTOSAVE_INTERVAL = 25
REQUEST_DELAY = 0.15


# ============================================================
# GLOBAL STATE
# ============================================================

RESULTS = []
INTERRUPTED = False


# ============================================================
# GRACEFUL SHUTDOWN HANDLER
# ============================================================

def signal_handler(sig, frame):

    global INTERRUPTED

    print("\n\nCtrl+C detected.")
    print("Finishing current ticker, then saving safely...")

    INTERRUPTED = True


signal.signal(signal.SIGINT, signal_handler)


# ============================================================
# SAFE SAVE FUNCTION
# ============================================================

def safe_save():

    if not RESULTS:
        print("No results to save.")
        return

    try:

        print(f"\nSaving {len(RESULTS)} results...")

        write_results_to_excel(RESULTS, OUTPUT_FILE)

        print("Save completed successfully.")

    except Exception as e:

        print("Save failed:", str(e))


# ============================================================
# MAIN CONTROLLER
# ============================================================

def main():

    global RESULTS
    global INTERRUPTED

    print("\n" + "="*70)
    print("DEEP VALUE CAPITAL DEPLOYMENT SCREENER")
    print("="*70)

    tickers = load_tickers(TICKER_FILE)

    total = len(tickers)

    print(f"\nLoaded {total} tickers\n")

    start_time = time.time()

    # ========================================================
    # MAIN LOOP
    # ========================================================

    for i, ticker in enumerate(tickers, 1):

        if INTERRUPTED:
            break

        print(f"[{i}/{total}] {ticker}...", end=" ", flush=True)

        try:

            result = analyze_stock(ticker)

            if result.get("success"):

                RESULTS.append(result)

                score = result.get("deep_value_score")
                mos = result.get("margin_of_safety_%")
                signal_label = result.get("signal")

                mos_str = (
                    f"{mos:.1f}%"
                    if isinstance(mos, (int, float))
                    else "NA"
                )

                print(
                    f"✓ Score={score}, MOS={mos_str}, Signal={signal_label}"
                )

            else:

                print(f"✗ {result.get('error')}")

        except Exception as e:

            print(f"✗ Exception: {str(e)}")


        # ====================================================
        # AUTOSAVE
        # ====================================================

        if i % AUTOSAVE_INTERVAL == 0 and RESULTS:

            print("\nAutosaving progress...")

            safe_save()

            print("Continuing...\n")


        # Prevent Yahoo rate limits
        time.sleep(REQUEST_DELAY)


    # ========================================================
    # FINAL SAVE
    # ========================================================

    print("\nLoop finished.")

    safe_save()

    elapsed = time.time() - start_time

    print(f"\nCompleted in {elapsed:.1f} seconds")
    print(f"Total successful results: {len(RESULTS)}")

    print("\nDone.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()