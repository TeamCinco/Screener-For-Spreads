"""
Excel output - includes risk state, CVaR, strike prices, industry context
FULL CRASH-PROOF VERSION
"""

import pandas as pd
import numpy as np
from pathlib import Path


def write_results_to_excel(results, output_path):
    """Write screening results to Excel with full risk context"""

    # =====================================================
    # Ensure directory exists
    # =====================================================

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # =====================================================
    # Convert results safely
    # =====================================================

    if not results:
        print("No results provided")
        return

    df = pd.DataFrame(results)

    # Filter successful only if exists
    if 'success' in df.columns:
        df = df[df['success'] == True].copy()

    if len(df) == 0:
        print("No successful results to save")
        return

    # =====================================================
    # GLOBAL SANITATION (CRITICAL)
    # =====================================================

    df = df.replace([np.inf, -np.inf], np.nan)

    # Ensure required structural columns exist
    for col in ['sector', 'industry', 'signal']:
        if col not in df.columns:
            df[col] = "Unknown"

    df['sector'] = df['sector'].fillna("Unknown")
    df['industry'] = df['industry'].fillna("Unknown")
    df['signal'] = df['signal'].fillna("NEUTRAL")

    # Ensure ticker exists
    if 'ticker' not in df.columns:
        df['ticker'] = "UNKNOWN"

    # =====================================================
    # SECTOR OVERSOLD COUNT (SAFE VERSION)
    # =====================================================

    oversold_mask = df['signal'] == 'OVERSOLD'

    if oversold_mask.any():

        sector_counts = (
            df.loc[oversold_mask]
            .groupby('sector')['ticker']
            .count()
        )

        df['sector_oversold_count'] = (
            df['sector']
            .map(sector_counts)
            .fillna(0)
            .astype(int)
        )

    else:
        df['sector_oversold_count'] = 0

    # =====================================================
    # INDUSTRY OVERSOLD COUNT (SAFE VERSION)
    # =====================================================

    if oversold_mask.any():

        industry_counts = (
            df.loc[oversold_mask]
            .groupby('industry')['ticker']
            .count()
        )

        df['industry_oversold_count'] = (
            df['industry']
            .map(industry_counts)
            .fillna(0)
            .astype(int)
        )

    else:
        df['industry_oversold_count'] = 0

    # =====================================================
    # Ensure numeric columns safe
    # =====================================================

    numeric_cols = [

        'z_score',
        'distance_from_mean_pct',

        'risk_state_score',
        'vol_regime_ratio',
        'tail_thickness',

        'current_price',
        'recent_high',
        'drop_from_high_pct',

        'p1', 'p5', 'p10', 'p25', 'p50',

        'strike_p5',
        'strike_p10',
        'spread_width',

        'var_95',
        'cvar_95',
        'var_99',
        'cvar_99',

        'volatility',
        'downside_vol',
        'vol_skew_ratio',

        'pe_ratio',
        'forward_pe',

        'avg_volume',

        'revenue_yoy_%',
        'revenue_cagr_%',

        'current_ratio',
        'cash_reserves'

    ]

    for col in numeric_cols:

        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # =====================================================
    # Sort properly
    # =====================================================

    if 'z_score' in df.columns:
        df = df.sort_values('z_score', ascending=True)

    # =====================================================
    # Column order
    # =====================================================

    column_order = [

        # Identity
        'ticker',
        'signal',
        'sector',
        'industry',

        # Earnings
        'earnings_soon',
        'earnings_in_window',
        'earnings_date',
        'ex_dividend_date',

        # Statistical dislocation
        'z_score',
        'distance_from_mean_pct',

        # Volume context
        'volume_surge',

        # Relative pressure
        'sector_oversold_count',
        'industry_oversold_count',

        # Risk state
        'risk_state_score',
        'regime',
        'vol_regime_ratio',
        'tail_thickness',

        # Price context
        'current_price',
        'recent_high',
        'drop_from_high_pct',

        # Forward distribution
        'p1',
        'p5',
        'p10',
        'p25',
        'p50',

        # Strike placement
        'strike_p5',
        'strike_p10',
        'spread_width',

        # Tail risk
        'var_95',
        'cvar_95',
        'var_99',
        'cvar_99',
        'volatility',
        'downside_vol',
        'vol_skew_ratio',

        # Valuation
        'pe_ratio',
        'forward_pe',

        # Volume
        'avg_volume',

        # Fundamentals
        'revenue_yoy_%',
        'revenue_cagr_%',
        'current_ratio',
        'cash_reserves'

    ]

    available_cols = [col for col in column_order if col in df.columns]

    df_out = df[available_cols].copy()

    # Round cleanly
    df_out = df_out.round(6)

    # =====================================================
    # Write Excel safely
    # =====================================================

    try:

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:

            df_out.to_excel(
                writer,
                index=False,
                sheet_name='All Results'
            )

            # Oversold
            if 'signal' in df_out.columns:

                oversold = df_out[df_out['signal'] == 'OVERSOLD']

                if len(oversold) > 0:
                    oversold.to_excel(
                        writer,
                        index=False,
                        sheet_name='Oversold'
                    )

                overbought = df_out[df_out['signal'] == 'OVERBOUGHT']

                if len(overbought) > 0:
                    overbought.to_excel(
                        writer,
                        index=False,
                        sheet_name='Overbought'
                    )

            # Elevated regime
            if 'regime' in df_out.columns:

                elevated = df_out[df_out['regime'] == 'Elevated']

                if len(elevated) > 0:
                    elevated.to_excel(
                        writer,
                        index=False,
                        sheet_name='Elevated Regime'
                    )

        # =====================================================
        # Summary print
        # =====================================================

        print(f"\nResults saved to: {output_path}")
        print(f"Total results: {len(df_out)}")

        if 'signal' in df_out.columns:

            print(f"Oversold: {(df_out['signal'] == 'OVERSOLD').sum()}")
            print(f"Overbought: {(df_out['signal'] == 'OVERBOUGHT').sum()}")

        if 'regime' in df_out.columns:

            print(f"Elevated regime: {(df_out['regime'] == 'Elevated').sum()}")

        if 'earnings_soon' in df_out.columns:

            print(f"Earnings soon: {df_out['earnings_soon'].fillna(False).sum()}")

    except Exception as e:

        print("Excel write failed, saving emergency backup...")

        backup_path = str(output_path).replace(".xlsx", "_BACKUP.xlsx")

        df_out.to_excel(backup_path, index=False)

        print(f"Backup saved to: {backup_path}")
        print("Error:", str(e))