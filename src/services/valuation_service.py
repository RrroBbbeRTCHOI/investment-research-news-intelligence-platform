from src.services.valuation_interpretation_service import build_valuation_interpretation
from src.services.company_service import get_company_data
from src.services.rating_service import get_rating_report


def build_valuation(ticker, peers, include_expectations=False):
    basic = get_company_data(ticker)
    try:
        report = get_rating_report(ticker, peers)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Recommendation failed for %s", ticker)
        report = None
    result = {"basic": basic, "recommendation": report}
    if include_expectations:
        result["valuation_interpretation"] = build_valuation_interpretation(ticker,basic)
    return result


def build_valuation_with_expectations(ticker, peers):
    return build_valuation(ticker, peers, include_expectations=True)
