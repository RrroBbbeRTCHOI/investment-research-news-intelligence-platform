"""Historical ROE using the production definition: net income / year-end equity."""
from src.data.financial_data import get_net_income, get_equity
from src.data.reuse import scoped
from src.services.cache import cached


def _build(ticker, years=5):
    income_series = get_net_income(ticker).dropna()
    equity_series = get_equity(ticker).dropna()
    common_dates = income_series.index.intersection(equity_series.index)
    result = []
    for date in common_dates:
        equity = equity_series.loc[date]
        value = None if equity == 0 else income_series.loc[date] / equity
        result.append({"year": str(getattr(date, "year", date))[:4], "roe": value})
    return sorted(result, key=lambda row: int(row["year"]))[-years:]


@scoped
def get_historical_roe(ticker, years=5):
    ticker = ticker.upper().strip()
    return cached(("historical-roe-v1", ticker, years), lambda: _build(ticker, years),
                  acceptable=lambda rows: any(row["roe"] is not None for row in rows))
