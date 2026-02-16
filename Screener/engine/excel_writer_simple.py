"""Excel output - includes risk state, CVaR, strike prices"""
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

    # Sort by Z-score (most oversold first)
    df = df.sort_values('z_score')

    # Column order for easy scanning
    column_order = [
        # Identity
        'ticker',
        'signal',
        'sector',

        # Earnings safety
        'earnings_in_window',
        'days_to_earnings',
        'earnings_date',

        # Statistical dislocation
        'z_score',
        'distance_from_mean_pct',

        # Volume context
        'volume_surge',

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

        # Valuation
        'pe_ratio',
        'forward_pe',

        # Volume
        'avg_volume',
    ]

    available_cols = [col for col in column_order if col in df.columns]
    df = df[available_cols]

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # All results
        df.to_excel(writer, index=False, sheet_name='All Results')

        # Oversold (Z < -2)
        oversold = df[df['signal'] == 'OVERSOLD'].copy()
        if len(oversold) > 0:
            oversold.to_excel(writer, index=False, sheet_name='Oversold')

        # Oversold + no earnings in trade window
        if 'earnings_in_window' in df.columns:
            safe_oversold = df[
                (df['signal'] == 'OVERSOLD') &
                (df['earnings_in_window'] == False)
            ].copy()
            if len(safe_oversold) > 0:
                safe_oversold.to_excel(writer, index=False, sheet_name='Oversold No Earnings')

        # Overbought (Z > 2)
        overbought = df[df['signal'] == 'OVERBOUGHT'].copy()
        if len(overbought) > 0:
            overbought.to_excel(writer, index=False, sheet_name='Overbought')

        # Elevated regime (risk state > 65)
        if 'risk_state_score' in df.columns:
            elevated = df[df['regime'] == 'Elevated'].copy()
            if len(elevated) > 0:
                elevated.to_excel(writer, index=False, sheet_name='Elevated Regime')

    n_safe = len(safe_oversold) if 'earnings_in_window' in df.columns and len(df[df['signal'] == 'OVERSOLD']) > 0 else 0

    print(f"\nResults saved to: {output_path}")
    print(f"  Total results: {len(df)}")
    print(f"  Oversold: {len(df[df['signal'] == 'OVERSOLD'])}")
    print(f"  Oversold (no earnings): {n_safe}")
    print(f"  Overbought: {len(df[df['signal'] == 'OVERBOUGHT'])}")
    if 'regime' in df.columns:
        print(f"  Elevated regime: {len(df[df['regime'] == 'Elevated'])}")