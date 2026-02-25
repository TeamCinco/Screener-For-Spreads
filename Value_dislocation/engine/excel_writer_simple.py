"""
Excel output writer — Deep Value Screener Version
Crash-proof, clean valuation-focused output
"""

import pandas as pd
import numpy as np
from pathlib import Path


def write_results_to_excel(results, output_path):
    """Write deep value screener results safely to Excel"""

    # =====================================================
    # Ensure directory exists
    # =====================================================

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # =====================================================
    # Validate results
    # =====================================================

    if not results:
        print("No results provided")
        return

    df = pd.DataFrame(results)

    # Keep only successful results
    if 'success' in df.columns:
        df = df[df['success'] == True].copy()

    if df.empty:
        print("No successful results to save")
        return

    # =====================================================
    # GLOBAL SANITATION
    # =====================================================

    df = df.replace([np.inf, -np.inf], np.nan)

    # Ensure required structural columns exist
    required_cols = ['ticker', 'sector', 'industry', 'signal']

    for col in required_cols:
        if col not in df.columns:
            df[col] = "Unknown"

    df['ticker'] = df['ticker'].fillna("UNKNOWN")
    df['sector'] = df['sector'].fillna("Unknown")
    df['industry'] = df['industry'].fillna("Unknown")
    df['signal'] = df['signal'].fillna("NEUTRAL")

    # =====================================================
    # NUMERIC CONVERSION (VALUATION METRICS)
    # =====================================================

    numeric_cols = [

        'current_price',
        'market_cap',

        'fcf',
        'fcf_yield_%',

        'ev_ebitda',
        'net_debt_ebitda',

        'earnings_yield_%',

        'intrinsic_value',
        'intrinsic_value_per_share',
        'margin_of_safety_%',

        'deep_value_score',

        'pe_ratio',
        'forward_pe',
        'pe_recovery_ratio',

        'avg_volume'
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # =====================================================
    # SORT BY DEEP VALUE SCORE (MOST IMPORTANT FIRST)
    # =====================================================

    if 'deep_value_score' in df.columns:
        df = df.sort_values(
            by='deep_value_score',
            ascending=False
        )

    # =====================================================
    # CLEAN COLUMN ORDER (VALUATION PRIORITY ORDER)
    # =====================================================

    column_order = [

        # Identity
        'ticker',
        'signal',
        'sector',
        'industry',

        # Price context
        'current_price',
        'market_cap',

        # Core valuation metrics
        'fcf',
        'fcf_yield_%',

        'ev_ebitda',
        'net_debt_ebitda',

        'earnings_yield_%',

        # Intrinsic value calculations
        'intrinsic_value_per_share',
        'intrinsic_value',
        'margin_of_safety_%',

        # Composite scoring
        'deep_value_score',
        'high_conviction',

        # Supporting metrics
        'pe_ratio',
        'forward_pe',
        'pe_recovery_ratio',

        # Liquidity
        'avg_volume'
    ]

    available_cols = [col for col in column_order if col in df.columns]

    df_out = df[available_cols].copy()

    # Round for readability
    df_out = df_out.round(4)

    # =====================================================
    # WRITE TO EXCEL SAFELY
    # =====================================================

    try:

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:

            # Main results
            df_out.to_excel(
                writer,
                index=False,
                sheet_name='All Results'
            )

            # High conviction subset
            if 'high_conviction' in df_out.columns:

                high_conviction = df_out[
                    df_out['high_conviction'] == True
                ]

                if not high_conviction.empty:

                    high_conviction.to_excel(
                        writer,
                        index=False,
                        sheet_name='High Conviction'
                    )

            # Deep value subset
            deep_value = df_out[
                df_out['signal'] == 'DEEP_VALUE'
            ]

            if not deep_value.empty:

                deep_value.to_excel(
                    writer,
                    index=False,
                    sheet_name='Deep Value'
                )

        print(f"\nResults saved to: {output_path}")
        print(f"Total companies: {len(df_out)}")

        if 'high_conviction' in df_out.columns:
            print(
                f"High conviction: "
                f"{df_out['high_conviction'].fillna(False).sum()}"
            )

        if 'signal' in df_out.columns:
            print(
                f"Deep value: "
                f"{(df_out['signal'] == 'DEEP_VALUE').sum()}"
            )

    except Exception as e:

        print("Excel write failed — saving backup")

        backup_path = str(output_path).replace(
            ".xlsx",
            "_BACKUP.xlsx"
        )

        df_out.to_excel(backup_path, index=False)

        print(f"Backup saved to: {backup_path}")
        print("Error:", str(e))