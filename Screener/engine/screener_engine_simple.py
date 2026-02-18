"""
Screener Engine - Lean Monte Carlo analysis for bulk screening
Runs base case simulation only (no stress ladder, no visualization)
Adds risk state score and CVaR to output for spread placement context
"""
import sys
from pathlib import Path
import yfinance as yf
import numpy as np
from datetime import date, timedelta
import pandas as pd
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# LEAN MONTE CARLO (no stress ladder, no viz, no paths stored)
# ============================================================================

def run_lean_simulation(stock_price, mu, sigma, days_to_simulate, num_simulations,
                        jump_prob=0.02, jump_magnitude=-0.04, df=5, lambda_=0.94):
    """
    Single vol scenario Monte Carlo with Student-t, EWMA, jumps.
    Returns only final prices and returns (no full path storage).
    """
    # Student-t shocks scaled to unit variance
    z = np.random.standard_t(df, size=(days_to_simulate, num_simulations))
    z = z / np.sqrt(df / (df - 2))

    # EWMA volatility clustering
    sigma_t = np.zeros((days_to_simulate, num_simulations))
    sigma_t[0] = sigma

    for t in range(1, days_to_simulate):
        sigma_t[t] = np.sqrt(
            lambda_ * sigma_t[t-1]**2 +
            (1 - lambda_) * (sigma_t[t-1] * z[t-1])**2
        )

    # Daily returns
    daily_returns = mu / 252 + sigma_t / np.sqrt(252) * z

    # Distributed jumps
    if jump_prob > 0:
        jump_matrix = np.random.rand(days_to_simulate, num_simulations) < jump_prob
        daily_returns[jump_matrix] += jump_magnitude

    # Final prices only (don't store full paths)
    final_prices = stock_price * np.prod(1 + daily_returns, axis=0)
    final_returns = (final_prices / stock_price - 1) * 100

    return final_prices, final_returns


def calculate_risk_state(stock_data, final_returns, cvar):
    """
    4-component risk state score. Same logic as mc_risk_state.py
    but inline to avoid import dependency.
    """
    returns = stock_data['Close'].pct_change().dropna()

    # 1. Vol regime ratio
    vol_20 = returns.rolling(20).std().iloc[-1] * np.sqrt(252)
    vol_100 = returns.rolling(100).std().iloc[-1] * np.sqrt(252)
    vol_ratio = float(vol_20 / vol_100) if vol_100 != 0 else 1.0
    vol_score = min(max((vol_ratio - 0.7) / (1.5 - 0.7), 0), 1)

    # 2. Tail thickness
    var_99 = abs(cvar['var_99'])
    cvar_99 = abs(cvar['cvar_99'])
    tail_ratio = cvar_99 / var_99 if var_99 != 0 else 1.0
    tail_score = min(max((tail_ratio - 1.1) / (1.6 - 1.1), 0), 1)

    # 3. Jump frequency
    jump_days = (returns < -0.03).sum()
    jump_freq = float(jump_days / len(returns))
    jump_score = min(jump_freq / 0.03, 1)

    # 4. Distribution width
    width = abs(np.percentile(final_returns, 95) - np.percentile(final_returns, 5))
    width_score = min(max((width - 10) / (60 - 10), 0), 1)

    composite = np.mean([vol_score, tail_score, jump_score, width_score]) * 100

    return {
        'risk_state_score': composite,
        'vol_ratio': vol_ratio,
        'tail_ratio': tail_ratio,
        'jump_freq': jump_freq,
        'distribution_width': width,
    }


# ============================================================================
# FUNDAMENTALS + Z-SCORE
# ============================================================================

def get_simple_fundamentals(ticker):
    """Get valuation, earnings, dividend, sector/industry.
    Uses multiple yfinance methods as fallbacks since info can be empty."""
    from datetime import datetime

    try:
        stock = yf.Ticker(ticker)

        # --- Try info dict first ---
        try:
            info = stock.info
            if info is None or len(info) < 5:
                info = {}
        except:
            info = {}

        # --- Try fast_info as fallback for basic data ---
        try:
            fi = stock.fast_info
        except:
            fi = None

        # --- Valuation ---
        pe_raw = info.get('trailingPE') or info.get('trailingPe')
        fpe_raw = info.get('forwardPE') or info.get('forwardPe')

        # --- Sector / Industry ---
        sector = info.get('sector') or info.get('sectorDisp') or 'Unknown'
        industry = info.get('industry') or info.get('industryDisp') or 'Unknown'

        # --- Volume ---
        avg_volume = info.get('averageVolume') or info.get('averageDailyVolume10Day')
        if avg_volume is None and fi is not None:
            try:
                avg_volume = fi.get('averageVolume', None)
            except:
                pass

        # --- Earnings date ---
        earnings_date = None

        # Method 1: stock.calendar
        try:
            cal = stock.calendar
            if cal is not None:
                if isinstance(cal, dict):
                    for key in ['Earnings Date', 'Earnings Dates', 'earningsDate', 'earningsHigh', 'Earnings Average']:
                        if key in cal:
                            val = cal[key]
                            if isinstance(val, list) and len(val) > 0:
                                earnings_date = val[0]
                            elif val is not None:
                                earnings_date = val
                            break
                elif isinstance(cal, pd.DataFrame):
                    for col in cal.columns:
                        if 'earning' in col.lower():
                            earnings_date = cal[col].iloc[0]
                            break
                    if earnings_date is None and hasattr(cal, 'index'):
                        for idx in cal.index:
                            if 'earning' in str(idx).lower():
                                earnings_date = cal.loc[idx].iloc[0]
                                break
        except:
            pass

        # Method 2: earnings_dates property
        if earnings_date is None:
            try:
                ed = stock.earnings_dates
                if ed is not None and len(ed) > 0:
                    # Get the next future date, or most recent
                    future = ed[ed.index >= datetime.now()]
                    if len(future) > 0:
                        earnings_date = future.index[-1]  # earliest future date
                    else:
                        earnings_date = ed.index[0]  # most recent past
            except:
                pass

        # Method 3: info timestamps
        if earnings_date is None:
            for key in ['earningsTimestamp', 'earningsTimestampStart']:
                ts = info.get(key)
                if ts is not None:
                    try:
                        earnings_date = datetime.fromtimestamp(ts)
                        break
                    except:
                        pass

        # Clean earnings date to string
        if earnings_date is not None:
            try:
                if isinstance(earnings_date, str):
                    earnings_date = pd.to_datetime(earnings_date)
                earnings_date = pd.Timestamp(earnings_date)
            except:
                earnings_date = None

        # --- Ex-dividend date ---
        ex_dividend_date = None
        div_ts = info.get('exDividendDate')
        if div_ts is not None:
            try:
                ex_dividend_date = pd.Timestamp(datetime.fromtimestamp(div_ts))
            except:
                pass

        return {
            'pe_ratio': float(pe_raw) if pe_raw is not None else None,
            'forward_pe': float(fpe_raw) if fpe_raw is not None else None,
            'sector': sector,
            'industry': industry,
            'avg_volume': avg_volume,
            'earnings_date': earnings_date,
            'ex_dividend_date': ex_dividend_date,
        }
    except:
        return {
            'pe_ratio': None, 'forward_pe': None,
            'sector': 'Unknown', 'industry': 'Unknown',
            'avg_volume': None, 'earnings_date': None,
            'ex_dividend_date': None,
        }


def get_z_score(ticker, lookback_days=60):
    """Z-score for mean reversion signal"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days + 50)

        hist_data = yf.download(ticker, start=start_date, end=end_date,
                                progress=False, timeout=10)

        if hist_data is None or len(hist_data) < 30:
            return None

        if isinstance(hist_data.columns, pd.MultiIndex):
            hist_data.columns = hist_data.columns.get_level_values(0)

        actual_lookback = min(lookback_days, len(hist_data))
        recent_data = hist_data.tail(actual_lookback)

        rolling_mean = float(recent_data['Close'].mean())
        rolling_std = float(recent_data['Close'].std())
        current_price = float(recent_data['Close'].iloc[-1])

        if rolling_std > 0 and rolling_mean > 0:
            z_score = (current_price - rolling_mean) / rolling_std
            distance_pct = ((current_price - rolling_mean) / rolling_mean) * 100
        else:
            return None

        if z_score <= -2:
            signal = 'OVERSOLD'
        elif z_score >= 2:
            signal = 'OVERBOUGHT'
        else:
            signal = 'NEUTRAL'

        return {'z_score': z_score, 'distance_from_mean_pct': distance_pct, 'signal': signal}
    except:
        return None


# ============================================================================
# MAIN ANALYSIS FUNCTION
# ============================================================================

def analyze_stock(ticker, days_to_simulate=90, num_simulations=10000, historical_window=252*6):
    """
    Lean MC analysis per stock. Runs base case only.
    Returns percentiles, CVaR, risk state score, fundamentals, Z-score.
    """
    try:
        # Fundamentals + Z-score
        fundamentals = get_simple_fundamentals(ticker)
        z_data = get_z_score(ticker)

        if z_data:
            z_score = z_data['z_score']
            distance_from_mean_pct = z_data['distance_from_mean_pct']
            signal = z_data['signal']
        else:
            z_score = 0.0
            distance_from_mean_pct = 0.0
            signal = 'UNKNOWN'

        # Download price data
        calendar_days = int(historical_window * (365/252)) + 100
        start_date = date.today() - timedelta(days=calendar_days)
        stock_data = yf.download(ticker, start=start_date, progress=False, auto_adjust=True)

        if len(stock_data) == 0:
            raise ValueError(f"No data for {ticker}")

        if isinstance(stock_data.columns, pd.MultiIndex):
            stock_data.columns = stock_data.columns.get_level_values(0)

        # Current price
        close_value = stock_data['Close'].iloc[-1]
        stock_price = float(close_value.item() if hasattr(close_value, 'item') else close_value)

        # Volatility + drift
        prices = stock_data['Close'].iloc[-historical_window:]
        stock_returns = prices.pct_change().dropna()
        volatility = float(stock_returns.std() * np.sqrt(252))
        mu = 0.042  # risk-free proxy

        # Downside semi-variance
        down_returns = stock_returns[stock_returns < 0]
        downside_vol = float(down_returns.std() * np.sqrt(252)) if len(down_returns) > 10 else volatility
        vol_skew_ratio = downside_vol / volatility if volatility > 0 else 1.0

        # Run lean MC (base case only)
        np.random.seed(42)
        final_prices, final_returns = run_lean_simulation(
            stock_price, mu, volatility,
            days_to_simulate, num_simulations
        )

        # Percentiles
        p1 = float(np.percentile(final_returns, 1))
        p5 = float(np.percentile(final_returns, 5))
        p10 = float(np.percentile(final_returns, 10))
        p25 = float(np.percentile(final_returns, 25))
        p50 = float(np.percentile(final_returns, 50))

        # CVaR
        var_95 = np.percentile(final_returns, 5)
        var_99 = np.percentile(final_returns, 1)
        cvar_95 = float(final_returns[final_returns <= var_95].mean())
        cvar_99 = float(final_returns[final_returns <= var_99].mean())
        cvar = {'var_95': var_95, 'cvar_95': cvar_95, 'var_99': var_99, 'cvar_99': cvar_99}

        # Risk state score
        risk_state = calculate_risk_state(stock_data, final_returns, cvar)

        # 52-week high
        try:
            hist_1y = stock_data.iloc[-252:]
            if len(hist_1y) > 0:
                recent_high = float(hist_1y['High'].max())
                drop_from_high_pct = ((stock_price - recent_high) / recent_high) * 100
            else:
                recent_high = stock_price
                drop_from_high_pct = 0.0
        except:
            recent_high = stock_price
            drop_from_high_pct = 0.0

        # Volume surge ratio (recent 5d avg vs 60d avg)
        try:
            vol_data = stock_data['Volume'].dropna()
            vol_5d = float(vol_data.iloc[-5:].mean())
            vol_60d = float(vol_data.iloc[-60:].mean())
            volume_surge = vol_5d / vol_60d if vol_60d > 0 else 1.0
        except:
            volume_surge = None

        # Earnings proximity
        from datetime import datetime
        earnings_date = fundamentals['earnings_date']
        earnings_soon = False
        earnings_in_window = False
        if earnings_date is not None:
            try:
                days_to_earn = (pd.Timestamp(earnings_date) - pd.Timestamp(datetime.now())).days
                if 0 <= days_to_earn <= 20:
                    earnings_soon = True
                if 0 <= days_to_earn <= days_to_simulate:
                    earnings_in_window = True
            except:
                pass

        # Strike prices at key percentiles
        strike_p5 = stock_price * (1 + p5 / 100)
        strike_p10 = stock_price * (1 + p10 / 100)

        # Suggested spread width (gap between p5 and p10 strikes)
        spread_width = round(abs(strike_p10 - strike_p5), 2)

        # Regime classification
        rss = risk_state['risk_state_score']
        if rss >= 65:
            regime = 'Elevated'
        elif rss >= 35:
            regime = 'Neutral'
        else:
            regime = 'Compressed'

        return {
            'ticker': ticker,
            'current_price': stock_price,
            'recent_high': recent_high,
            'drop_from_high_pct': drop_from_high_pct,
            'volatility': volatility * 100,
            'downside_vol': downside_vol * 100,
            'vol_skew_ratio': vol_skew_ratio,

            # Percentiles
            'p1': p1,
            'p5': p5,
            'p10': p10,
            'p25': p25,
            'p50': p50,

            # Strike prices
            'strike_p5': strike_p5,
            'strike_p10': strike_p10,
            'spread_width': spread_width,

            # Risk metrics
            'var_95': cvar['var_95'],
            'cvar_95': cvar['cvar_95'],
            'var_99': cvar['var_99'],
            'cvar_99': cvar['cvar_99'],

            # Risk state
            'risk_state_score': risk_state['risk_state_score'],
            'regime': regime,
            'vol_regime_ratio': risk_state['vol_ratio'],
            'tail_thickness': risk_state['tail_ratio'],

            # Volume context
            'volume_surge': volume_surge,

            # Earnings
            'earnings_soon': earnings_soon,
            'earnings_in_window': earnings_in_window,
            'earnings_date': fundamentals['earnings_date'],

            # Dividend
            'ex_dividend_date': fundamentals['ex_dividend_date'],

            # Valuation
            'pe_ratio': fundamentals['pe_ratio'],
            'forward_pe': fundamentals['forward_pe'],
            'sector': fundamentals['sector'],
            'industry': fundamentals['industry'],
            'avg_volume': fundamentals['avg_volume'],

            # Z-score
            'z_score': z_score,
            'distance_from_mean_pct': distance_from_mean_pct,
            'signal': signal,

            'success': True
        }

    except Exception as e:
        return {
            'ticker': ticker,
            'success': False,
            'error': str(e)
        }