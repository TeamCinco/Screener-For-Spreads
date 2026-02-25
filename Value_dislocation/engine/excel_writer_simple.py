"""
Excel Writer — Deep Value Screener
Writes screening results to Excel with multiple tabs.
"""

import pandas as pd
import numpy as np
from pathlib import Path


def write_results_to_excel(results, output_path):
    """Save screener results to Excel with filtered tabs."""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if not results:
        print("No results to save.")
        return

    df = pd.DataFrame(results)

    # Keep only successful pulls
    if "success" in df.columns:
        df = df[df["success"] == True].copy()

    if df.empty:
        print("No successful results to save.")
        return

    # Clean infinities
    df = df.replace([np.inf, -np.inf], np.nan)

    # Fill missing labels
    df["ticker"] = df["ticker"].fillna("UNKNOWN")
    df["sector"] = df["sector"].fillna("Unknown")
    df["industry"] = df["industry"].fillna("Unknown")
    df["signal"] = df["signal"].fillna("NEUTRAL")

    # Convert numerics
    numeric_cols = [
        "current_price", "market_cap",
        "fcf", "fcf_yield_%",
        "ev_ebitda", "net_debt_ebitda", "fcf_to_debt",
        "earnings_yield_%",
        "deep_value_score",
        "pe_ratio", "forward_pe", "pe_recovery_ratio",
        "avg_volume",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sort by score — best candidates first
    if "deep_value_score" in df.columns:
        df = df.sort_values("deep_value_score", ascending=False)

    # Column order for output
    column_order = [
        # Identity
        "ticker", "signal", "sector", "industry",
        # Price
        "current_price", "market_cap",
        # Core value metrics
        "fcf", "fcf_yield_%",
        "ev_ebitda", "net_debt_ebitda", "fcf_to_debt",
        "earnings_yield_%",
        # Score
        "deep_value_score", "high_conviction",
        # Supporting
        "pe_ratio", "forward_pe", "pe_recovery_ratio",
        # Liquidity
        "avg_volume",
        # Calendar
        "earnings_date", "ex_dividend_date",
    ]

    available = [c for c in column_order if c in df.columns]
    df_out = df[available].copy().round(4)

    # Write
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:

            df_out.to_excel(writer, index=False, sheet_name="All Results")

            # High conviction tab
            if "high_conviction" in df_out.columns:
                hc = df_out[df_out["high_conviction"] == True]
                if not hc.empty:
                    hc.to_excel(writer, index=False, sheet_name="High Conviction")

            # Deep value tab
            dv = df_out[df_out["signal"] == "DEEP_VALUE"]
            if not dv.empty:
                dv.to_excel(writer, index=False, sheet_name="Deep Value")

        print(f"\nSaved to: {output_path}")
        print(f"Total: {len(df_out)}")
        if "high_conviction" in df_out.columns:
            print(f"High conviction: {df_out['high_conviction'].fillna(False).sum()}")
        if "signal" in df_out.columns:
            print(f"Deep value: {(df_out['signal'] == 'DEEP_VALUE').sum()}")

    except Exception as e:
        backup = str(output_path).replace(".xlsx", "_BACKUP.xlsx")
        df_out.to_excel(backup, index=False)
        print(f"Excel write failed. Backup saved to: {backup}")
        print(f"Error: {e}")