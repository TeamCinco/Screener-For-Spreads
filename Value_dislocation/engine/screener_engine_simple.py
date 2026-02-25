"""
Deep Value Stock Screener — Engine
Purpose: Pull fundamentals, compute value metrics, score and rank.

This is a SCREENING tool. It flags candidates for deeper analysis.
It does NOT compute intrinsic value — that requires a real DCF model
built on a per-company basis with company-specific assumptions.

Metrics used:
    - FCF Yield (%)        → higher = cheaper relative to cash generation
    - EV / EBITDA          → lower = cheaper relative to operating earnings
    - Earnings Yield (%)   → inverse of P/E, higher = cheaper
    - Net Debt / EBITDA    → lower = less leveraged
    - FCF-to-Debt Ratio    → higher = can pay down debt faster

Scoring: Each metric gets 0-2 points based on thresholds.
         Total score (0-10) determines signal classification.

Signals:
    DEEP_VALUE      → score >= 8, cheap on almost every metric
    VALUE           → score >= 5, cheap on several metrics
    NEUTRAL         → score < 5, not obviously cheap

High Conviction:
    DEEP_VALUE + liquid (avg volume > 500k) + no earnings within 14 days
    These are the names you could actually deploy capital into right now
    without walking into a binary event or illiquid spread.
"""

import yfinance as yf
import warnings
import pandas as pd
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")


# ============================================================
# EARNINGS DATE LOOKUP (3 FALLBACK METHODS)
# ============================================================

def get_earnings_date(stock, info):
    """
    Tries 3 methods to find the next earnings date.
    Yahoo Finance is inconsistent — this handles that.
    """

    # Method 1: earnings_dates property (most reliable)
    try:
        dates = stock.earnings_dates
        if dates is not None and len(dates) > 0:
            future = dates[dates.index >= datetime.now()]
            if len(future) > 0:
                return future.index[0]
            return dates.index[-1]
    except Exception:
        pass

    # Method 2: calendar dictionary
    try:
        cal = stock.calendar
        if isinstance(cal, dict):
            for key in cal:
                if "earn" in key.lower():
                    val = cal[key]
                    if isinstance(val, list) and len(val) > 0:
                        return pd.Timestamp(val[0])
    except Exception:
        pass

    # Method 3: raw timestamp from info
    try:
        ts = info.get("earningsTimestamp")
        if ts:
            return datetime.fromtimestamp(ts)
    except Exception:
        pass

    return None


# ============================================================
# PULL FUNDAMENTALS FOR ONE STOCK
# ============================================================

def analyze_stock(ticker, **kwargs):
    """
    Pull key fundamentals and compute screening metrics.
    Returns a flat dictionary — one row per stock.
    """

    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # --------------------------------------------------
        # RAW DATA FROM YAHOO
        # --------------------------------------------------

        price = info.get("currentPrice")
        market_cap = info.get("marketCap")
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        pe = info.get("trailingPE")
        forward_pe = info.get("forwardPE")
        ev = info.get("enterpriseValue")
        ebitda = info.get("ebitda")
        total_debt = info.get("totalDebt", 0) or 0
        total_cash = info.get("totalCash", 0) or 0
        shares = info.get("sharesOutstanding")
        avg_volume = info.get("averageVolume")

        # --------------------------------------------------
        # EARNINGS + DIVIDEND DATES
        # --------------------------------------------------

        earnings_date = get_earnings_date(stock, info)

        ex_div_date = None
        try:
            div_ts = info.get("exDividendDate")
            if div_ts:
                ex_div_date = datetime.fromtimestamp(div_ts)
        except Exception:
            pass

        # --------------------------------------------------
        # EARNINGS PROXIMITY CHECK
        # If earnings are within 14 days, flag it.
        # You don't want to enter a position right before
        # a binary event that could gap the stock 10%.
        # --------------------------------------------------

        earnings_within_14_days = False

        if earnings_date is not None:
            try:
                # Handle both Timestamp and datetime
                if isinstance(earnings_date, pd.Timestamp):
                    ed = earnings_date.to_pydatetime().replace(tzinfo=None)
                else:
                    ed = earnings_date.replace(tzinfo=None)

                days_until = (ed - datetime.now()).days

                # Flag if earnings are 0-14 days away
                if 0 <= days_until <= 14:
                    earnings_within_14_days = True
            except Exception:
                pass

        # --------------------------------------------------
        # FREE CASH FLOW
        # Financials excluded — banks don't have traditional FCF
        # because their "operating cash flow" includes deposits
        # and lending activity, not actual business operations.
        # --------------------------------------------------

        fcf = None

        if sector != "Financial Services":
            try:
                cf = stock.cashflow
                if cf is not None and not cf.empty:
                    if "Free Cash Flow" in cf.index:
                        fcf = cf.loc["Free Cash Flow"].iloc[0]
                    elif "Operating Cash Flow" in cf.index and "Capital Expenditure" in cf.index:
                        fcf = cf.loc["Operating Cash Flow"].iloc[0] + cf.loc["Capital Expenditure"].iloc[0]
            except Exception:
                pass

        # --------------------------------------------------
        # COMPUTED METRICS
        # --------------------------------------------------

        # FCF Yield = FCF / Market Cap
        # Higher = stock is cheaper relative to its cash generation
        fcf_yield = None
        if fcf and market_cap and market_cap > 0:
            fcf_yield = (fcf / market_cap) * 100

        # EV/EBITDA = Enterprise Value / EBITDA
        # Lower = cheaper relative to operating earnings
        ev_ebitda = None
        if ev and ebitda and ebitda > 0:
            ev_ebitda = ev / ebitda

        # Net Debt / EBITDA = how many years of earnings to pay off debt
        # Lower = less leveraged, more financial flexibility
        net_debt_ebitda = None
        net_debt = total_debt - total_cash
        if ebitda and ebitda > 0:
            net_debt_ebitda = net_debt / ebitda

        # Earnings Yield = 1 / PE ratio (expressed as %)
        # Higher = cheaper on an earnings basis
        earnings_yield = None
        if pe and pe > 0:
            earnings_yield = (1 / pe) * 100

        # FCF to Debt = can the company pay off debt with free cash flow?
        # Higher = stronger balance sheet relative to cash generation
        fcf_to_debt = None
        if fcf and total_debt and total_debt > 0:
            fcf_to_debt = fcf / total_debt

        # PE Recovery = Forward PE / Trailing PE
        # Below 1.0 = market expects earnings to GROW (forward cheaper than trailing)
        pe_recovery = None
        if pe and forward_pe and pe > 0:
            pe_recovery = forward_pe / pe

        # --------------------------------------------------
        # SCORING (0-10 SCALE)
        #
        # Each metric scored 0, 1, or 2 based on value thresholds.
        # These thresholds are general — not sector-adjusted.
        # The score is for RANKING, not for making buy decisions.
        # --------------------------------------------------

        score = 0

        # FCF Yield: > 5% = decent, > 10% = strong
        if fcf_yield is not None:
            if fcf_yield > 10:
                score += 2
            elif fcf_yield > 5:
                score += 1

        # EV/EBITDA: < 6 = cheap, < 10 = reasonable
        if ev_ebitda is not None:
            if ev_ebitda < 6:
                score += 2
            elif ev_ebitda < 10:
                score += 1

        # Earnings Yield: > 10% = cheap, > 6% = reasonable
        if earnings_yield is not None:
            if earnings_yield > 10:
                score += 2
            elif earnings_yield > 6:
                score += 1

        # Net Debt/EBITDA: < 1 = very clean, < 3 = manageable
        if net_debt_ebitda is not None:
            if net_debt_ebitda < 1:
                score += 2
            elif net_debt_ebitda < 3:
                score += 1

        # FCF to Debt: > 0.3 = solid, > 0.15 = acceptable
        if fcf_to_debt is not None:
            if fcf_to_debt > 0.3:
                score += 2
            elif fcf_to_debt > 0.15:
                score += 1

        # --------------------------------------------------
        # SIGNAL CLASSIFICATION
        #
        # DEEP_VALUE = cheap on almost every fundamental metric
        # VALUE      = cheap on several metrics, worth a look
        # NEUTRAL    = not obviously cheap, skip for now
        # --------------------------------------------------

        if score >= 8:
            signal = "DEEP_VALUE"
        elif score >= 5:
            signal = "VALUE"
        else:
            signal = "NEUTRAL"

        # --------------------------------------------------
        # HIGH CONVICTION
        #
        # Deep value alone isn't enough to deploy capital.
        # High conviction = deep value AND:
        #   - Liquid enough to enter/exit without moving the price
        #   - No earnings report in the next 14 days
        #
        # This separates "interesting on paper" from
        # "I could actually put money here today."
        # --------------------------------------------------

        high_conviction = (
            score >= 8
            and avg_volume is not None
            and avg_volume > 500_000
            and not earnings_within_14_days
        )

        # --------------------------------------------------
        # RETURN ONE ROW
        # --------------------------------------------------

        return {
            "ticker": ticker,
            "success": True,
            "sector": sector,
            "industry": industry,
            "signal": signal,
            "current_price": price,
            "market_cap": market_cap,
            "earnings_date": earnings_date,
            "earnings_within_14_days": earnings_within_14_days,
            "ex_dividend_date": ex_div_date,
            "pe_ratio": pe,
            "forward_pe": forward_pe,
            "pe_recovery_ratio": pe_recovery,
            "earnings_yield_%": earnings_yield,
            "fcf": fcf,
            "fcf_yield_%": fcf_yield,
            "ev_ebitda": ev_ebitda,
            "net_debt_ebitda": net_debt_ebitda,
            "fcf_to_debt": fcf_to_debt,
            "deep_value_score": score,
            "high_conviction": high_conviction,
            "avg_volume": avg_volume,
        }

    except Exception as e:
        return {
            "ticker": ticker,
            "success": False,
            "error": str(e),
        }