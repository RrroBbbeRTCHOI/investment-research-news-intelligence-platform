"""Compatibility adapter for the unchanged research.html field contract."""
import logging

from src.data.reuse import scoped
from src.services import company_service, financials_service, rating_service
from src.services import valuation_service, historical_trends_service
from src.services import earnings_quality_service, sec_filing_service, screener_service
from src.ui.adapters import (
    adapt_company,
    adapt_recommendation,
    get_empty_recommendation_context,
    get_empty_historical_financials,
    get_empty_market_relative_performance,
)

# Keep established helper imports available to existing callers.
from src.ui.formatters import (
    format_percent,
    format_price,
    format_multiple,
    format_score,
    format_market_cap,
)
from src.analysis.company_metrics import (
    safe_float,
    latest_value,
    latest_two_values,
    calculate_revenue_growth,
    calculate_roe,
    calculate_operating_margin,
    calculate_fcf_margin,
    calculate_debt_to_equity,
)
from src.analysis.historical_trends import build_company_historical_trends
from src.analysis.market_relative_performance import build_market_relative_performance

DEFAULT_PEERS = {
    "AAPL": ["MSFT", "GOOGL", "NVDA", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "NVDA"],
    "GOOGL": ["META", "MSFT", "AMZN"],
    "NVDA": ["AMD", "AVGO", "INTC"],
    "AMZN": ["GOOGL", "MSFT", "META"],
    "META": ["GOOGL", "AMZN", "MSFT"],
    "TSLA": ["GM", "F"],
}
RECOMMENDATION_TABS = {"overview", "valuation", "earnings-quality"}
HISTORICAL_TABS = {"historical-trends"}


def build_basic_research(ticker, peers):
    """Use existing company fields without triggering unrelated tab pipelines."""
    return {"basic": company_service.get_company_data(ticker)}

PIPELINES = {
    "overview": valuation_service.build_valuation,
    "financials": financials_service.build_financials,
    "valuation": valuation_service.build_valuation_with_expectations,
    "historical-trends": historical_trends_service.build_historical_trends,
    "earnings-quality": earnings_quality_service.build_earnings_quality,
    "financial-health": financials_service.build_financials,
    "sec-filing": sec_filing_service.build_sec_filing,
    "relevant-events": build_basic_research,
}


@scoped
def load_basic_company_data(ticker):
    return adapt_company(company_service.get_company_data(ticker))


@scoped
def get_recommendation_context(ticker, peer_tickers):
    try:
        report = rating_service.get_rating_report(ticker, peer_tickers)
        return adapt_recommendation(report)
    except Exception:
        logging.getLogger(__name__).exception("Recommendation failed for %s", ticker)
        return get_empty_recommendation_context()


@scoped
def attach_rating_summary(
    context, ticker, peer_tickers=None, report=None, load_report=True
):
    """Fill missing company-level fields without changing tab-specific content."""
    defaults = {
        "rating": "N/A",
        "confidence": "N/A",
        "research_score": "N/A",
        "research_score_raw": None,
    }

    def available(key, value):
        if key == "research_score_raw":
            return safe_float(value) is not None
        return value is not None and value != "" and value != "N/A"

    for key, value in defaults.items():
        context.setdefault(key, value)
    if all(available(key, context[key]) for key in defaults):
        return context

    ticker = ticker.upper().strip()
    peers = DEFAULT_PEERS.get(ticker, []) if peer_tickers is None else peer_tickers
    try:
        if report is None:
            if not load_report:
                return context
            report = rating_service.get_rating_report(ticker, peers)
        summary = adapt_recommendation(report)
        for key in defaults:
            value = summary.get(key)
            if not available(key, context[key]) and available(key, value):
                context[key] = value
    except Exception:
        logging.getLogger(__name__).exception(
            "Rating summary failed for %s", ticker
        )
    return context


@scoped
def build_screener_context(ticker):
    ticker = ticker.upper().strip()
    context = adapt_company(screener_service.get_screener_data(ticker))
    return attach_rating_summary(context, ticker)


def adapt_earnings_quality_diagnostics(diagnostics):
    """Format the service payload without calculating or changing any scores."""
    def display_score(value):
        return "Unavailable" if value is None else format_score(value)

    contribution = diagnostics["weighted_positive_non_core_raw"]
    return {
        **diagnostics,
        "score": display_score(diagnostics["score_raw"]),
        "components": [
            {**item, "score": display_score(item["score_raw"])}
            for item in diagnostics["components"]
        ],
        "weighted_positive_non_core": (
            "Unavailable" if contribution is None else format_percent(contribution)
        ),
    }


@scoped
def build_company_context(ticker, peer_tickers=None, active_tab="overview"):
    ticker = ticker.upper().strip()
    active_tab = active_tab.lower().strip()
    peers = DEFAULT_PEERS.get(ticker, []) if peer_tickers is None else peer_tickers
    pipeline = PIPELINES.get(active_tab, financials_service.build_financials)
    if active_tab == "earnings-quality":
        diagnostics = earnings_quality_service.build_earnings_quality(ticker)
        # Page compatibility: rating remains an independent UI dependency, not an EQ dependency.
        result = {"basic": company_service.get_company_data(ticker),
                  "earnings_quality_diagnostics": diagnostics}
        try:
            result["recommendation"] = rating_service.get_rating_report(ticker, peers)
        except Exception:
            logging.getLogger(__name__).exception("Rating unavailable for %s", ticker)
    else:
        result = pipeline(ticker, peers)
    context = adapt_company(result["basic"])
    context["peers"] = peers
    report = result.get("recommendation")
    context.update(
        adapt_recommendation(report)
        if report is not None
        else get_empty_recommendation_context()
    )
    context["historical_trends"] = {
        "financials": result.get(
            "financial_history", get_empty_historical_financials(ticker)
        ),
        "market_relative_performance": result.get(
            "market_history", get_empty_market_relative_performance(ticker)
        ),
    }
    if active_tab == "earnings-quality":
        context["earnings_quality_diagnostics"] = adapt_earnings_quality_diagnostics(
            result["earnings_quality_diagnostics"]
        )
    if active_tab in {"financials", "financial-health"}:
        context["financial_interpretation"] = result.get("financial_interpretation")
    if active_tab == "sec-filing":
        context["sec_filings"] = result.get("sec_filings", [])
        context["sec_error"] = result.get("sec_error")
    if active_tab == "valuation":
        context["valuation_interpretation"] = result.get("valuation_interpretation")
    return attach_rating_summary(
        context,
        ticker,
        peer_tickers=peers,
        report=report,
        load_report=active_tab not in RECOMMENDATION_TABS,
    )
