"""
Hardened Screener Engine
Stable, Safe, Production-Ready
"""

import yfinance as yf
import numpy as np
import pandas as pd
from datetime import date, timedelta
import warnings

warnings.filterwarnings("ignore")

# ============================================================
# MONTE CARLO
# ============================================================

def run_simulation(stock_price, mu, sigma, days, sims):

    z = np.random.standard_t(5, size=(days, sims))
    z = z / np.sqrt(5 / 3)

    sigma_t = np.zeros_like(z)
    sigma_t[0] = sigma

    for t in range(1, days):
        sigma_t[t] = np.sqrt(
            0.94 * sigma_t[t-1]**2 +
            0.06 * (sigma_t[t-1] * z[t-1])**2
        )

    daily_returns = mu/252 + sigma_t/np.sqrt(252) * z
    final_prices = stock_price * np.prod(1 + daily_returns, axis=0)
    final_returns = (final_prices / stock_price - 1) * 100

    return final_returns

# ============================================================
# ANALYZE STOCK
# ============================================================

def analyze_stock(ticker, days_to_simulate=90, num_simulations=5000, historical_window=252*3):

    try:

        start_date = date.today() - timedelta(days=int(historical_window * 1.5))

        data = yf.download(
            ticker,
            start=start_date,
            auto_adjust=True,
            progress=False,
            threads=False
        )

        if data is None or len(data) < 120:
            return {"ticker": ticker, "success": False, "error": "Insufficient price data"}

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        if "Close" not in data.columns:
            return {"ticker": ticker, "success": False, "error": "No Close column"}

        prices = data["Close"].dropna()

        if len(prices) < 120:
            return {"ticker": ticker, "success": False, "error": "Too few closes"}

        returns = prices.pct_change().dropna()

        if len(returns) < 60:
            return {"ticker": ticker, "success": False, "error": "Too few returns"}

        stock_price = float(prices.iloc[-1])

        volatility = float(returns.std() * np.sqrt(252))

        if np.isnan(volatility) or volatility <= 0:
            return {"ticker": ticker, "success": False, "error": "Invalid volatility"}

        downside = returns[returns < 0]
        downside_vol = float(downside.std() * np.sqrt(252)) if len(downside) > 5 else volatility
        vol_skew_ratio = downside_vol / volatility if volatility > 0 else 1.0

        mu = float(returns.mean() * 252)

        np.random.seed(42)
        final_returns = run_simulation(
            stock_price,
            mu,
            volatility,
            days_to_simulate,
            num_simulations
        )

        p5 = float(np.percentile(final_returns, 5))
        p10 = float(np.percentile(final_returns, 10))
        p50 = float(np.percentile(final_returns, 50))

        var_95 = np.percentile(final_returns, 5)
        cvar_95 = float(final_returns[final_returns <= var_95].mean())

        # Z-score
        rolling_mean = prices.rolling(60).mean()
        rolling_std = prices.rolling(60).std()

        if pd.isna(rolling_std.iloc[-1]) or rolling_std.iloc[-1] == 0:
            z_score = 0
        else:
            z_score = float(
                (prices.iloc[-1] - rolling_mean.iloc[-1]) /
                rolling_std.iloc[-1]
            )

        signal = (
            "OVERSOLD" if z_score <= -2 else
            "OVERBOUGHT" if z_score >= 2 else
            "NEUTRAL"
        )

        high_1y = prices.rolling(252).max().iloc[-1]
        drawdown = float((stock_price - high_1y) / high_1y * 100)

        # fundamentals (safe)
        try:
            info = yf.Ticker(ticker).info or {}
        except:
            info = {}

        pe = info.get("trailingPE")
        fpe = info.get("forwardPE")
        sector = info.get("sector")
        industry = info.get("industry")
        avg_volume = info.get("averageVolume")

        # simple opportunity score
        quality = 0
        if pe and pe < 25: quality += 20
        if fpe and pe and fpe < pe: quality += 15
        if avg_volume and avg_volume > 1_000_000: quality += 10

        dislocation = 0
        if z_score <= -2: dislocation += 30
        if drawdown <= -20: dislocation += 20

        opportunity_score = round(
            0.4 * quality +
            0.4 * dislocation +
            0.2 * max(0, 100 - volatility*100),
            2
        )

        return {
            "ticker": ticker,
            "current_price": stock_price,
            "drop_from_high_pct": drawdown,
            "volatility": volatility * 100,
            "vol_skew_ratio": vol_skew_ratio,
            "p5": p5,
            "p10": p10,
            "p50": p50,
            "var_95": var_95,
            "cvar_95": cvar_95,
            "pe_ratio": pe,
            "forward_pe": fpe,
            "sector": sector,
            "industry": industry,
            "avg_volume": avg_volume,
            "z_score": z_score,
            "signal": signal,
            "opportunity_score": opportunity_score,
            "success": True
        }

    except Exception as e:
        return {"ticker": ticker, "success": False, "error": str(e)}
