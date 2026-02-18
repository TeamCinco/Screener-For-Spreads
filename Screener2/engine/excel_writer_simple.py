"""Excel output - includes risk state, CVaR, strike prices, industry context"""
import pandas as pd
from pathlib import Path

def write_results_to_excel(results, output_path):
    """Write screening results to Excel with full risk context"""

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(results)
    df = df[df['success'] == True].copy()

    if len(df) == 0:
        print("No successful results to save")
        return

    # --- Compute sector/industry oversold counts ---
    # How many oversold names in the same sector and industry
    oversold_mask = df['signal'] == 'OVERSOLD'

    if 'sector' in df.columns:
        sector_oversold = df[oversold_mask].groupby('sector')['ticker'].transform('count')
        df['sector_oversold_count'] = 0
        df.loc[oversold_mask, 'sector_oversold_count'] = sector_oversold.astype(int)
        # For non-oversold stocks, show how many oversold in their sector
        sector_counts = df[oversold_mask].groupby('sector')['ticker'].count().to_dict()
        df['sector_oversold_count'] = df['sector'].map(sector_counts).fillna(0).astype(int)

    if 'industry' in df.columns:
        industry_counts = df[oversold_mask].groupby('industry')['ticker'].count().to_dict()
        df['industry_oversold_count'] = df['industry'].map(industry_counts).fillna(0).astype(int)

    # Sort by Z-score (most oversold first)
    df = df.sort_values('z_score')

    # Column order
    column_order = [
        # Identity
        'ticker',
        'signal',
        'sector',
        'industry',

        # Earnings & dividend
        'earnings_soon',
        'earnings_in_window',
        'earnings_date',
        'ex_dividend_date',

        # Statistical dislocation
        'z_score',
        'distance_from_mean_pct',

        # Volume context
        'volume_surge',

        # Industry relative strength
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
    ]

    available_cols = [col for col in column_order if col in df.columns]
    df_out = df[available_cols]

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # All results
        df_out.to_excel(writer, index=False, sheet_name='All Results')

        # Oversold (Z < -2)
        oversold = df_out[df_out['signal'] == 'OVERSOLD'].copy()
        if len(oversold) > 0:
            oversold.to_excel(writer, index=False, sheet_name='Oversold')

        # Overbought (Z > 2)
        overbought = df_out[df_out['signal'] == 'OVERBOUGHT'].copy()
        if len(overbought) > 0:
            overbought.to_excel(writer, index=False, sheet_name='Overbought')

        # Elevated regime (risk state > 65)
        if 'risk_state_score' in df.columns:
            elevated = df_out[df_out['regime'] == 'Elevated'].copy()
            if len(elevated) > 0:
                elevated.to_excel(writer, index=False, sheet_name='Elevated Regime')

    print(f"\nResults saved to: {output_path}")
    print(f"  Total results: {len(df_out)}")
    print(f"  Oversold: {len(df_out[df_out['signal'] == 'OVERSOLD'])}")
    print(f"  Overbought: {len(df_out[df_out['signal'] == 'OVERBOUGHT'])}")
    if 'regime' in df.columns:
        print(f"  Elevated regime: {len(df_out[df_out['regime'] == 'Elevated'])}")
    if 'earnings_soon' in df.columns:
        print(f"  Earnings within 20d: {df['earnings_soon'].sum()}")