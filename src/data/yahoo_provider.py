"""Shared raw Yahoo reads. Pricing definitions remain in their original callers."""
import yfinance as yf
from src.data.reuse import reuse


def company_info(ticker, suppress_info_errors=False):
    symbol = ticker.upper().strip()

    def load():
        company = yf.Ticker(symbol)
        try:
            return company.info
        except Exception:
            if suppress_info_errors:
                return None
            raise

    return reuse(("yahoo", "info", symbol), load)


def statement(ticker, name):
    symbol = ticker.upper().strip()
    return reuse(("yahoo", name, symbol), lambda: getattr(yf.Ticker(symbol), name))


def history(ticker, **parameters):
    symbol = ticker.upper().strip()
    key = ("yahoo", "history", symbol, tuple(sorted(parameters.items())))
    return reuse(key, lambda: yf.Ticker(symbol).history(**parameters))
