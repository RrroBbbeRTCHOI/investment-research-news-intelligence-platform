from src.services.financial_interpretation_service import build_financial_interpretation
from src.services.company_service import get_company_data


def build_financials(ticker, peers):
    return {"basic": get_company_data(ticker),
            "financial_interpretation": build_financial_interpretation(ticker)}
