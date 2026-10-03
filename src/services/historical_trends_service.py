import logging
from src.services.company_service import get_company_data
from src.analysis.historical_trends import build_company_historical_trends
from src.analysis.market_relative_performance import build_market_relative_performance
from src.data.reuse import scoped
from src.services.cache import cached


def _build_historical_trends(ticker, peers):
    result = {"basic": get_company_data(ticker)}
    try:
        result["financial_history"] = build_company_historical_trends(ticker)
    except Exception:
        logging.getLogger(__name__).exception(
            "Historical financials failed for %s", ticker
        )
    try:
        result["market_history"] = build_market_relative_performance(
            ticker, period="5y"
        )
    except Exception:
        logging.getLogger(__name__).exception("Historical prices failed for %s", ticker)
    return result


@scoped
def build_historical_trends(ticker, peers):
    """Reuse unchanged history outputs across dossier and compatibility contexts."""
    return cached(
        ("research-history-v1", ticker, tuple(peers)),
        lambda: _build_historical_trends(ticker, peers),
        acceptable=lambda result: bool(result.get("financial_history"))
        and bool(result.get("market_history", {}).get("normalized_history")),
    )
