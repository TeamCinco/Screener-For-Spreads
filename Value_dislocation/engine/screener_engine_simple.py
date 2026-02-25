"""
Deep Value Screener Engine
Institutional-grade fundamental value screener

Compatible with:
- main_enhanced.py
- excel_writer_simple.py
- ticker_loader.py
"""

import yfinance as yf
import warnings

warnings.filterwarnings("ignore")


# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================

def analyze_stock(
    ticker,
    days_to_simulate=None,
    num_simulations=None,
    historical_window=None
):
    """
    Core deep value screener function.
    Returns standardized dict compatible with pipeline.
    """

    try:

        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # ====================================================
        # BASIC INFO
        # ====================================================

        current_price = info.get("currentPrice")
        market_cap = info.get("marketCap")

        sector = info.get("sector")
        industry = info.get("industry")

        pe_ratio = info.get("trailingPE")
        forward_pe = info.get("forwardPE")

        enterprise_value = info.get("enterpriseValue")
        ebitda = info.get("ebitda")

        total_debt = info.get("totalDebt")
        total_cash = info.get("totalCash")

        shares_outstanding = info.get("sharesOutstanding")

        avg_volume = info.get("averageVolume")

        signal = "NEUTRAL"

        # ====================================================
        # FREE CASH FLOW
        # ====================================================

        fcf = None

        try:

            cashflow = stock.cashflow

            if cashflow is not None and not cashflow.empty:

                if "Free Cash Flow" in cashflow.index:

                    fcf = cashflow.loc["Free Cash Flow"].iloc[0]

                elif (
                    "Operating Cash Flow" in cashflow.index and
                    "Capital Expenditure" in cashflow.index
                ):

                    ocf = cashflow.loc["Operating Cash Flow"].iloc[0]
                    capex = cashflow.loc["Capital Expenditure"].iloc[0]

                    fcf = ocf + capex

        except:
            pass


        # ====================================================
        # EXCLUDE FINANCIALS (FCF invalid)
        # ====================================================

        if sector == "Financial Services":

            fcf = None


        # ====================================================
        # FCF YIELD
        # ====================================================

        fcf_yield = None

        if fcf and market_cap and market_cap > 0:

            fcf_yield = (fcf / market_cap) * 100


        # ====================================================
        # EV / EBITDA
        # ====================================================

        ev_ebitda = None

        if enterprise_value and ebitda and ebitda > 0:

            ev_ebitda = enterprise_value / ebitda


        # ====================================================
        # NET DEBT / EBITDA
        # ====================================================

        net_debt = None
        net_debt_ebitda = None

        if total_debt and total_cash:

            net_debt = total_debt - total_cash

            if ebitda and ebitda > 0:

                net_debt_ebitda = net_debt / ebitda


        # ====================================================
        # EARNINGS YIELD
        # ====================================================

        earnings_yield = None

        if pe_ratio and pe_ratio > 0:

            earnings_yield = (1 / pe_ratio) * 100


        # ====================================================
        # INTRINSIC VALUE (FCF PER SHARE METHOD)
        # ====================================================

        intrinsic_value = None
        intrinsic_value_per_share = None
        margin_of_safety = None

        if fcf and shares_outstanding and current_price:

            fcf_per_share = fcf / shares_outstanding

            intrinsic_value_per_share = fcf_per_share * 15

            intrinsic_value = intrinsic_value_per_share * shares_outstanding

            margin_of_safety = (
                intrinsic_value_per_share - current_price
            ) / current_price * 100


        # ====================================================
        # SANITY FILTER (remove impossible values)
        # ====================================================

        if margin_of_safety and abs(margin_of_safety) > 500:

            margin_of_safety = None
            intrinsic_value = None
            intrinsic_value_per_share = None


        # ====================================================
        # RECOVERY SIGNAL
        # ====================================================

        pe_recovery_ratio = None

        if pe_ratio and forward_pe and pe_ratio > 0:

            pe_recovery_ratio = forward_pe / pe_ratio


        # ====================================================
        # DEEP VALUE SCORE
        # ====================================================

        deep_value_score = 0

        if fcf_yield and fcf_yield > 8:
            deep_value_score += 2

        if ev_ebitda and ev_ebitda < 8:
            deep_value_score += 2

        if net_debt_ebitda and net_debt_ebitda < 3:
            deep_value_score += 1

        if earnings_yield and earnings_yield > 8:
            deep_value_score += 1

        if margin_of_safety and margin_of_safety > 30:
            deep_value_score += 3

        elif margin_of_safety and margin_of_safety > 15:
            deep_value_score += 2

        elif margin_of_safety and margin_of_safety > 5:
            deep_value_score += 1


        # ====================================================
        # SIGNAL CLASSIFICATION
        # ====================================================

        if deep_value_score >= 7:

            signal = "DEEP_VALUE"

        elif deep_value_score >= 4:

            signal = "VALUE"

        else:

            signal = "NEUTRAL"


        high_conviction = deep_value_score >= 7


        # ====================================================
        # RETURN STRUCTURED RESULT
        # ====================================================

        return {

            "ticker": ticker,
            "success": True,

            "sector": sector,
            "industry": industry,

            "signal": signal,

            "current_price": current_price,
            "market_cap": market_cap,

            "pe_ratio": pe_ratio,
            "forward_pe": forward_pe,
            "earnings_yield_%": earnings_yield,

            "fcf": fcf,
            "fcf_yield_%": fcf_yield,

            "ev_ebitda": ev_ebitda,
            "net_debt_ebitda": net_debt_ebitda,

            "pe_recovery_ratio": pe_recovery_ratio,

            "intrinsic_value": intrinsic_value,
            "intrinsic_value_per_share": intrinsic_value_per_share,
            "margin_of_safety_%": margin_of_safety,

            "deep_value_score": deep_value_score,
            "high_conviction": high_conviction,

            "avg_volume": avg_volume
        }


    except Exception as e:

        return {

            "ticker": ticker,
            "success": False,
            "error": str(e)
        }