from src.services.company_service import get_company_data
from src.data.reuse import scoped


@scoped
def get_screener_data(ticker):
    # Preserve existing lightweight rows; no rating computation.
    return get_company_data(ticker)
