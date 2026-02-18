"""
Capital Deployment Screener Engine
Quality + Dislocation + Revenue Growth + Liquidity + Earnings/Dividend
Production Safe Version
"""

import yfinance as yf
import numpy as np
import pandas as pd
from datetime import date, timedelta, datetime
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
# FUNDAMENTALS (Revenue + Liquidity + Earnings + Dividend)
# ============================================================

def get_fundamentals_extended(ticker):

    stock = yf.Ticker(ticker)

    pe = None
    fpe = None
    sector = None
    industry = None
    avg_volume = None
    earnings_date = None
    ex_dividend_date = None
    revenue_yoy = None
    revenue_cagr = None
    current_ratio = None
    cash_reserves = None

    # -------------------------
    # INFO BLOCK
    # -------------------------
    try:
        info = stock.info or {}

        pe = info.get("trailingPE")
        fpe = info.get("forwardPE")
        sector = info.get("sector")
        industry = info.get("industry")
        avg_volume = info.get("averageVolume")

        # Dividend
        div_ts = info.get("exDividendDate")
        if div_ts:
            try:
                ex_dividend_date = datetime.fromtimestamp(div_ts)
            except:
                pass

        # Earnings timestamp fallback
        earn_ts = info.get("earningsTimestamp")
        if earn_ts:
            try:
                earnings_date = datetime.fromtimestamp(earn_ts)
            except:
                pass

    except:
        pass

    # -------------------------
    # CALENDAR earnings fallback
    # -------------------------
    if earnings_date is None:
        try:
            cal = stock.calendar
            if isinstance(cal, dict):
                for key in cal:
                    if "earn" in key.lower():
                        val = cal[key]
                        if isinstance(val, list) and len(val) > 0:
                            earnings_date = pd.to_datetime(val[0])
                            break
        except:
            pass

    # -------------------------
    # REVENUE GROWTH
    # -------------------------
    try:
        income = stock.financials
        if income is not None and not income.empty:
            revenue_series = income.loc["Total Revenue"].dropna()

            if len(revenue_series) >= 2:

                # YoY
                revenue_yoy = (
                    (revenue_series.iloc[0] / revenue_series.iloc[1]) - 1
                ) * 100

                # CAGR
                years = len(revenue_series) - 1
                revenue_cagr = (
                    (revenue_series.iloc[0] / revenue_series.iloc[-1]) ** (1/years) - 1
                ) * 100 if years > 0 else None
    except:
        pass

    # -------------------------
    # LIQUIDITY (Balance Sheet)
    # -------------------------
    try:
        balance = stock.balance_sheet
        if balance is not None and not balance.empty:

            current_assets = balance.loc["Total Current Assets"].iloc[0]
            current_liabilities = balance.loc["Total Current Liabilities"].iloc[0]

            if current_liabilities and current_liabilities != 0:
                current_ratio = current_assets / current_liabilities

            if "Cash And Cash Equivalents" in balance.index:
                cash_reserves = balance.loc["Cash And Cash Equivalents"].iloc[0]
            elif "Cash" in balance.index:
                cash_reserves = balance.loc["Cash"].iloc[0]
    except:
        pass

    return {
        "pe_ratio": pe,
        "forward_pe": fpe,
        "sector": sector,
        "industry": industry,
        "avg_volume": avg_volume,
        "earnings_date": earnings_date,
        "ex_dividend_date": ex_dividend_date,
        "revenue_yoy_%": revenue_yoy,
        "revenue_cagr_%": revenue_cagr,
        "current_ratio": current_ratio,
        "cash_reserves": cash_reserves
    }


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

        prices = data["Close"].dropna()
        returns = prices.pct_change().dropna()

        stock_price = float(prices.iloc[-1])
        volatility = float(returns.std() * np.sqrt(252))
        mu = float(returns.mean() * 252)

        np.random.seed(42)
        final_returns = run_simulation(
            stock_price, mu, volatility,
            days_to_simulate, num_simulations
        )

        p5 = float(np.percentile(final_returns, 5))
        p10 = float(np.percentile(final_returns, 10))
        p50 = float(np.percentile(final_returns, 50))

        var_95 = np.percentile(final_returns, 5)
        cvar_95 = float(final_returns[final_returns <= var_95].mean())

        # Z-score
        rolling_mean = prices.rolling(60).mean()
        rolling_std = prices.rolling(60).std()

        if rolling_std.iloc[-1] > 0:
            z_score = float(
                (prices.iloc[-1] - rolling_mean.iloc[-1]) /
                rolling_std.iloc[-1]
            )
        else:
            z_score = 0

        signal = (
            "OVERSOLD" if z_score <= -2 else
            "OVERBOUGHT" if z_score >= 2 else
            "NEUTRAL"
        )

        high_1y = prices.rolling(252).max().iloc[-1]
        drawdown = float((stock_price - high_1y) / high_1y * 100)

        fundamentals = get_fundamentals_extended(ticker)

        # Earnings flags
        earnings_soon = False
        earnings_in_window = False

        ed = fundamentals["earnings_date"]
        if ed:
            try:
                days_to_earn = (pd.Timestamp(ed) - pd.Timestamp(datetime.now())).days
                if 0 <= days_to_earn <= 20:
                    earnings_soon = True
                if 0 <= days_to_earn <= days_to_simulate:
                    earnings_in_window = True
            except:
                pass

        return {
            "ticker": ticker,
            "current_price": stock_price,
            "drop_from_high_pct": drawdown,
            "volatility": volatility * 100,
            "p5": p5,
            "p10": p10,
            "p50": p50,
            "var_95": var_95,
            "cvar_95": cvar_95,
            "z_score": z_score,
            "signal": signal,

            # Earnings / Dividend
            "earnings_date": fundamentals["earnings_date"],
            "earnings_soon": earnings_soon,
            "earnings_in_window": earnings_in_window,
            "ex_dividend_date": fundamentals["ex_dividend_date"],

            # Revenue + Liquidity
            "revenue_yoy_%": fundamentals["revenue_yoy_%"],
            "revenue_cagr_%": fundamentals["revenue_cagr_%"],
            "current_ratio": fundamentals["current_ratio"],
            "cash_reserves": fundamentals["cash_reserves"],

            # Valuation
            "pe_ratio": fundamentals["pe_ratio"],
            "forward_pe": fundamentals["forward_pe"],
            "sector": fundamentals["sector"],
            "industry": fundamentals["industry"],
            "avg_volume": fundamentals["avg_volume"],

            "success": True
        }

    except Exception as e:
        return {"ticker": ticker, "success": False, "error": str(e)}
