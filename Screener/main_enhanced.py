"""
Monte Carlo Stock Screener - Enhanced with P/E and Z-Score
Analyzes all stocks in ticker.txt and outputs to Excel
"""
import sys
import signal
from pathlib import Path

# Add engine directory to path
engine_path = Path(__file__).parent / "engine"
sys.path.insert(0, str(engine_path))

from engine.ticker_loader import load_tickers
from engine.screener_engine_simple import analyze_stock  # Updated import
from engine.excel_writer_simple import write_results_to_excel  # Updated import

# ============================================================================
# CONFIGURATION
# ============================================================================

TICKER_FILE = "/Users/jazzhashzzz/Desktop/Screener For Spreads/ticker_filtered.txt"
OUTPUT_FILE = "/Users/jazzhashzzz/Desktop/Screener For Spreads/output/screener_results_enhanced.xlsx"

DAYS_TO_SIMULATE = 90
NUM_SIMULATIONS = 10000
HISTORICAL_WINDOW = 252

# Global results list for signal handler
RESULTS = []

# ============================================================================
# SIGNAL HANDLER FOR CTRL+C
# ============================================================================

def signal_handler(sig, frame):
    """Save results when user hits Ctrl+C"""
    print("\n\n" + "="*80)
    print("INTERRUPTED - Saving partial results...")
    print("="*80)
    
    if RESULTS:
        try:
            write_results_to_excel(RESULTS, OUTPUT_FILE)
            print(f"\nSaved {len(RESULTS)} results before exit")
        except Exception as e:
            print(f"Error saving: {e}")
    else:
        print("No results to save")
    
    sys.exit(0)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)

# ============================================================================
# MAIN
# ============================================================================

def main():
    global RESULTS
    
    print("\n" + "="*80)
    print("MONTE CARLO STOCK SCREENER - Enhanced with P/E & Z-Score")
    print("="*80)
    print("\nTIP: Press Ctrl+C to save partial results and exit")
    
    # Load tickers
    print(f"\nLoading tickers from: {TICKER_FILE}")
    tickers = load_tickers(TICKER_FILE)
    print(f"Found {len(tickers)} tickers")
    
    # Run analysis
    print(f"\nRunning Monte Carlo analysis ({NUM_SIMULATIONS:,} simulations, {DAYS_TO_SIMULATE} days)")
    print("Now with: P/E ratios, Z-scores, and mean reversion signals")
    print("="*80)
    
    save_interval = 100  # Save every 100 stocks
    
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker}...", end=" ", flush=True)
        
        result = analyze_stock(
            ticker,
            days_to_simulate=DAYS_TO_SIMULATE,
            num_simulations=NUM_SIMULATIONS,
            historical_window=HISTORICAL_WINDOW
        )
        
        if result['success']:
            RESULTS.append(result)
            
            # Build compact status line
            signal_tag = f"[{result['signal']}]" if result.get('signal', 'NEUTRAL') != 'NEUTRAL' else ""
            z_str = f"Z={result['z_score']:.2f}" if result.get('z_score') is not None else "Z=N/A"
            pe_str = f"P/E={result['pe_ratio']:.1f}" if result.get('pe_ratio') is not None else "P/E=N/A"
            regime_str = result.get('regime', '')
            drop_str = f"drop={result['drop_from_high_pct']:.1f}%"
            
            # Earnings flag
            earn_flag = " ⚠️EARNINGS SOON" if result.get('earnings_soon') else ""
            
            print(f"✓ {signal_tag} {z_str}, {pe_str}, {drop_str}, {regime_str}{earn_flag}")
        else:
            print(f"✗ Failed")
        
        # Periodic save every 100 stocks
        if i % save_interval == 0 and RESULTS:
            print(f"\n[Auto-saving progress: {len(RESULTS)} stocks completed]")
            try:
                write_results_to_excel(RESULTS, OUTPUT_FILE)
            except Exception as e:
                print(f"Warning: Auto-save failed: {e}")
    
    # Final save and analysis
    print("\n" + "="*80)
    print(f"Successful: {len(RESULTS)}/{len(tickers)}")
    
    if RESULTS:
        import pandas as pd
        df = pd.DataFrame(RESULTS)
        
        # Show mean reversion opportunities
        print("\n" + "="*80)
        print("MEAN REVERSION OPPORTUNITIES (Value + Statistical Dislocation):")
        print("="*80)
        
        # Oversold stocks with reasonable P/E
        mean_reversion_long = df[
            (df['signal'] == 'OVERSOLD') &           # Z-score < -2
            (df['pe_ratio'].notna()) &                # Has P/E data
            (df['pe_ratio'] > 0) &                    # Profitable
            (df['pe_ratio'] < 30) &                   # Not overvalued
            (df['volatility'] >= 15) &                # Enough vol for options
            (df['volatility'] <= 40)                  # Not too crazy
        ]
        
        print(f"\nOversold + Reasonable Valuation: {len(mean_reversion_long)} candidates")
        print(f"  Criteria: Z < -2, P/E 0-30, Vol 15-40%\n")
        
        if len(mean_reversion_long) > 0:
            display_cols = ['ticker', 'signal', 'z_score', 'pe_ratio', 'current_price', 'drop_from_high_pct', 'p10']
            display = mean_reversion_long[display_cols].head(20)
            print(display.to_string(index=False))
        else:
            print("  None found matching all criteria")
        
        # Also show existing selling opportunities
        print("\n" + "="*80)
        print("SELLING OPPORTUNITIES (Original Logic):")
        print("="*80)
        
        selling_zone = df[
            (df['drop_from_high_pct'] <= -10) &  # Already dropped 10%+
            (df['p10'] >= -10) &                  # Limited forward downside
            (df['p10'] <= -5) &
            (df['volatility'] >= 15) &            # Enough vol for premium
            (df['volatility'] <= 30)              # Not too crazy
        ]
        
        print(f"\nFound {len(selling_zone)} candidates:")
        print(f"  Criteria: Dropped 10%+, forward p10 -5% to -10%, vol 15-30%\n")
        
        if len(selling_zone) > 0:
            display = selling_zone[['ticker', 'current_price', 'drop_from_high_pct', 'p10', 'pe_ratio']].head(20)
            print(display.to_string(index=False))
        
        # Write final Excel
        write_results_to_excel(RESULTS, OUTPUT_FILE)
    
    print("\n" + "="*80)
    print("DONE - Open Excel and filter by:")
    print("  - Signal column for OVERSOLD/OVERBOUGHT")
    print("  - P/E ratio for valuation")
    print("  - Z-score for deviation magnitude")
    print("="*80)

if __name__ == "__main__":
    main()