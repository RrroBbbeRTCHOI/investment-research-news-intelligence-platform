import pandas as pd
import yfinance as yf

from src.config import STOCK_DATABASE_PATH


# =========================================================
# Market Price History
# =========================================================

def get_price_history(ticker, period='1y'):
    from src.data.yahoo_provider import history
    result = history(ticker, period=period)
    return None if result.empty else result


# =========================================================
# Current Price
# =========================================================

def get_current_price(
    ticker
):
    """
    Return the latest available closing price.

    Uses recent price history rather than
    relying on yfinance info fields.
    """

    history = (
        get_price_history(
            ticker,
            period="5d"
        )
    )

    if (
        history is None
        or history.empty
        or "Close" not in history.columns
    ):
        return None

    close_prices = (
        history[
            "Close"
        ]
        .dropna()
    )

    if close_prices.empty:
        return None

    return float(
        close_prices.iloc[-1]
    )


# =========================================================
# Company Market Information
# =========================================================

def get_company_info(ticker):
    from src.data.yahoo_provider import company_info
    return company_info(ticker, suppress_info_errors=True) or None


# =========================================================
# Market Capitalisation
# =========================================================

def get_market_cap(
    ticker
):
    """
    Return current market capitalisation.
    """

    info = (
        get_company_info(
            ticker
        )
    )

    if info is None:
        return None

    market_cap = (
        info.get(
            "marketCap"
        )
    )

    if market_cap is None:
        return None

    return float(
        market_cap
    )


# =========================================================
# Enterprise Value
# =========================================================

def get_enterprise_value(
    ticker
):
    """
    Return current enterprise value.
    """

    info = (
        get_company_info(
            ticker
        )
    )

    if info is None:
        return None

    enterprise_value = (
        info.get(
            "enterpriseValue"
        )
    )

    if enterprise_value is None:
        return None

    return float(
        enterprise_value
    )


# =========================================================
# Data Cleaning
# =========================================================

def clean_stock_data(
    df
):
    """
    Clean and standardise
    stock database data.
    """

    df = df.copy()

    df.columns = [
        column.strip()
        for column in df.columns
    ]

    if "Ticker" in df.columns:

        df[
            "Ticker"
        ] = (
            df[
                "Ticker"
            ]
            .astype(str)
            .str.upper()
            .str.strip()
        )

    return df


# =========================================================
# Load Stock Database
# =========================================================

def load_stock_database():
    """
    Load the local stock database
    from CSV.
    """

    if not STOCK_DATABASE_PATH.exists():

        raise FileNotFoundError(
            f"Stock database not found: "
            f"{STOCK_DATABASE_PATH}"
        )

    df = (
        pd.read_csv(
            STOCK_DATABASE_PATH
        )
    )

    return (
        clean_stock_data(
            df
        )
    )


# =========================================================
# Get Single Company
# =========================================================

def get_company(
    ticker
):
    """
    Return one company's row
    from the local stock database.
    """

    df = (
        load_stock_database()
    )

    ticker = (
        ticker
        .upper()
        .strip()
    )

    company = (
        df[
            df[
                "Ticker"
            ]
            == ticker
        ]
    )

    if company.empty:
        return None

    return (
        company.iloc[0]
    )


# =========================================================
# Get Available Tickers
# =========================================================

def get_tickers():
    """
    Return all available ticker symbols.
    """

    df = (
        load_stock_database()
    )

    return (
        df[
            "Ticker"
        ]
        .tolist()
    )


# =========================================================
# Search Companies
# =========================================================

def search_companies(
    keyword
):
    """
    Search companies by ticker
    or company name.
    """

    df = (
        load_stock_database()
    )

    keyword = (
        keyword
        .lower()
        .strip()
    )

    result = (
        df[
            df[
                "Ticker"
            ]
            .astype(str)
            .str.lower()
            .str.contains(
                keyword,
                na=False
            )
            |
            df[
                "Company"
            ]
            .astype(str)
            .str.lower()
            .str.contains(
                keyword,
                na=False
            )
        ]
    )

    return result


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "AAPL"

    print("\n==============================")
    print("MARKET DATA TEST")
    print("==============================")

    print(
        "\nStock Database:"
    )

    print(
        load_stock_database()
    )

    print(
        "\nAvailable Tickers:"
    )

    print(
        get_tickers()
    )

    print(
        f"\nLocal Company Record: "
        f"{ticker}"
    )

    print(
        get_company(
            ticker
        )
    )

    print(
        "\nSearch 'micro':"
    )

    print(
        search_companies(
            "micro"
        )
    )

    print(
        f"\n{ticker} Current Price:"
    )

    current_price = (
        get_current_price(
            ticker
        )
    )

    if current_price is None:

        print(
            "N/A"
        )

    else:

        print(
            f"${current_price:,.2f}"
        )

    print(
        f"\n{ticker} Market Cap:"
    )

    market_cap = (
        get_market_cap(
            ticker
        )
    )

    if market_cap is None:

        print(
            "N/A"
        )

    else:

        print(
            f"${market_cap:,.0f}"
        )

    print(
        f"\n{ticker} Enterprise Value:"
    )

    enterprise_value = (
        get_enterprise_value(
            ticker
        )
    )

    if enterprise_value is None:

        print(
            "N/A"
        )

    else:

        print(
            f"${enterprise_value:,.0f}"
        )

    print(
        f"\n{ticker} 6-Month Price History:"
    )

    history = (
        get_price_history(
            ticker,
            period="6mo"
        )
    )

    if history is None:

        print(
            "N/A"
        )

    else:

        print(
            history.tail()
        )
