import logging
from src.data.financial_data import (
    get_revenue,
    get_net_income,
    get_operating_income,
    get_total_debt,
    get_equity,
    get_free_cash_flow,
)
from src.data.market_data import get_company_info, get_current_price, get_market_cap
from src.analysis.fundamentals import calculate_roic
from src.analysis.company_metrics import (
    safe_float,
    calculate_revenue_growth,
    calculate_roe,
    calculate_operating_margin,
    calculate_fcf_margin,
    calculate_debt_to_equity,
)
from src.data.reuse import scoped
from src.services.cache import cached


def load_company_data(ticker):
    info = get_company_info(ticker) or {}
    company_name = info.get("longName") or info.get("shortName") or ticker
    exchange = info.get("exchange") or "N/A"
    price_raw = safe_float(get_current_price(ticker))
    market_cap_raw = safe_float(get_market_cap(ticker))
    pe_raw = safe_float(info.get("trailingPE"))
    forward_pe_raw = safe_float(info.get("forwardPE"))
    enterprise_value_raw = safe_float(info.get("enterpriseValue"))
    daily_change_raw = safe_float(info.get("regularMarketChange"))
    daily_change_percent_raw = safe_float(info.get("regularMarketChangePercent"))
    revenue = get_revenue(ticker)
    net_income = get_net_income(ticker)
    operating_income = get_operating_income(ticker)
    total_debt = get_total_debt(ticker)
    equity = get_equity(ticker)
    free_cash_flow = get_free_cash_flow(ticker)
    revenue_growth_raw = calculate_revenue_growth(revenue)
    roe_raw = calculate_roe(net_income, equity)
    operating_margin_raw = calculate_operating_margin(operating_income, revenue)
    fcf_margin_raw = calculate_fcf_margin(free_cash_flow, revenue)
    debt_to_equity_raw = calculate_debt_to_equity(total_debt, equity)
    try:
        roic_raw = calculate_roic(ticker)
    except Exception as error:
        logging.getLogger(__name__).exception("ROIC calculation failed for %s", ticker)
        roic_raw = None
    return {
        "ticker": ticker,
        "company_name": company_name,
        "exchange": exchange,
        "price_raw": price_raw,
        "market_cap_raw": market_cap_raw,
        "revenue_growth_raw": revenue_growth_raw,
        "roe_raw": roe_raw,
        "roic_raw": roic_raw,
        "operating_margin_raw": operating_margin_raw,
        "fcf_margin_raw": fcf_margin_raw,
        "debt_to_equity_raw": debt_to_equity_raw,
        "pe_raw": pe_raw,
        "forward_pe_raw": forward_pe_raw,
        "enterprise_value_raw": enterprise_value_raw,
        "daily_change_raw": daily_change_raw,
        "daily_change_percent_raw": daily_change_percent_raw,
        "sector": info.get("sector") or "Unavailable",
        "industry": info.get("industry") or "Unavailable",
        "description": info.get("longBusinessSummary") or "Company description unavailable from the current provider.",
    }


@scoped
def get_company_data(ticker):
    ticker = ticker.upper().strip()
    return cached(("company", ticker), lambda: load_company_data(ticker))
