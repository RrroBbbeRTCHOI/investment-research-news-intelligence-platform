from src.data.reuse import memoized
import pandas as pd
from src.data import yahoo_provider

from src.data.financial_data import (
    get_free_cash_flow,
    get_diluted_eps
)


# =========================================================
# Company Info
# =========================================================

def get_company_info(ticker):
    from src.data.yahoo_provider import company_info
    return company_info(ticker)


# =========================================================
# Read Metric From Existing Info
# =========================================================

def get_metric_from_info(
    info,
    metric
):
    """
    Read a valuation metric from an already
    fetched company-info dictionary.

    This avoids repeated yfinance requests.
    """

    if not info:
        return None

    mapping = {

        "Current Price":
            "currentPrice",

        "Market Cap":
            "marketCap",

        "Enterprise Value":
            "enterpriseValue",

        "P/E":
            "trailingPE",

        "Forward P/E":
            "forwardPE",

        "P/B":
            "priceToBook",

        "P/S":
            "priceToSalesTrailing12Months",

        "EV/EBITDA":
            "enterpriseToEbitda"
    }

    key = (
        mapping.get(
            metric
        )
    )

    if key is None:
        return None

    return (
        info.get(
            key
        )
    )


# =========================================================
# Price / Market Data
# =========================================================

def get_current_price(
    ticker,
    info=None
):

    if info is None:

        info = (
            get_company_info(
                ticker
            )
        )

    return (
        get_metric_from_info(
            info,
            "Current Price"
        )
    )


def get_market_cap(
    ticker,
    info=None
):

    if info is None:

        info = (
            get_company_info(
                ticker
            )
        )

    return (
        get_metric_from_info(
            info,
            "Market Cap"
        )
    )


def get_enterprise_value(
    ticker,
    info=None
):

    if info is None:

        info = (
            get_company_info(
                ticker
            )
        )

    return (
        get_metric_from_info(
            info,
            "Enterprise Value"
        )
    )


# =========================================================
# Valuation Multiples
# =========================================================

def calculate_pe(
    ticker,
    info=None
):

    if info is None:

        info = (
            get_company_info(
                ticker
            )
        )

    return (
        get_metric_from_info(
            info,
            "P/E"
        )
    )


def calculate_forward_pe(
    ticker,
    info=None
):

    if info is None:

        info = (
            get_company_info(
                ticker
            )
        )

    return (
        get_metric_from_info(
            info,
            "Forward P/E"
        )
    )


def calculate_price_to_book(
    ticker,
    info=None
):

    if info is None:

        info = (
            get_company_info(
                ticker
            )
        )

    return (
        get_metric_from_info(
            info,
            "P/B"
        )
    )


def calculate_price_to_sales(
    ticker,
    info=None
):

    if info is None:

        info = (
            get_company_info(
                ticker
            )
        )

    return (
        get_metric_from_info(
            info,
            "P/S"
        )
    )


def calculate_ev_to_ebitda(
    ticker,
    info=None
):

    if info is None:

        info = (
            get_company_info(
                ticker
            )
        )

    return (
        get_metric_from_info(
            info,
            "EV/EBITDA"
        )
    )


# =========================================================
# Yield Metrics
# =========================================================

def calculate_earnings_yield(
    ticker,
    info=None
):

    pe = (
        calculate_pe(
            ticker,
            info=info
        )
    )

    if (
        pe is None
        or pe == 0
    ):
        return None

    return (
        1
        / pe
    )


def calculate_fcf_yield(
    ticker,
    info=None
):

    free_cash_flow = (
        get_free_cash_flow(
            ticker
        )
    )

    market_cap = (
        get_market_cap(
            ticker,
            info=info
        )
    )

    if (
        free_cash_flow is None
        or market_cap is None
    ):
        return None

    free_cash_flow = (
        free_cash_flow
        .dropna()
    )

    if len(
        free_cash_flow
    ) == 0:
        return None

    latest_fcf = (
        free_cash_flow
        .iloc[0]
    )

    if market_cap == 0:
        return None

    return (
        latest_fcf
        / market_cap
    )


# =========================================================
# Historical Valuation
# =========================================================

@memoized
def get_historical_pe(ticker):
    """
    Simplified annual historical P/E.
    """
    eps_series = get_diluted_eps(ticker)
    if eps_series is None:
        return None
    eps_series = eps_series.dropna()
    if len(eps_series) == 0:
        return None
    results = []
    for fiscal_date, eps in eps_series.items():
        if eps is None or eps <= 0:
            continue
        fiscal_date = pd.Timestamp(fiscal_date)
        start_date = fiscal_date - pd.Timedelta(days=10)
        end_date = fiscal_date + pd.Timedelta(days=10)
        price_history = yahoo_provider.history(ticker, start=start_date, end=end_date)
        if price_history.empty:
            continue
        price_history = price_history.copy()
        if price_history.index.tz is not None:
            price_history.index = price_history.index.tz_localize(None)
        price_history['distance'] = abs(price_history.index - fiscal_date)
        nearest_row = price_history.sort_values('distance').iloc[0]
        stock_price = nearest_row['Close']
        historical_pe = stock_price / eps
        results.append({'Date': fiscal_date, 'Price': stock_price, 'EPS': eps, 'P/E': historical_pe})
    if not results:
        return None
    df = pd.DataFrame(results)
    df = df.sort_values('Date', ascending=False)
    return df


def calculate_historical_pe_median(
    ticker,
    historical_pe=None
):

    if historical_pe is None:

        historical_pe = (
            get_historical_pe(
                ticker
            )
        )

    if (
        historical_pe is None
        or historical_pe.empty
    ):
        return None

    return (
        historical_pe[
            "P/E"
        ]
        .median()
    )


def calculate_pe_premium_to_history(
    ticker,
    current_pe=None,
    historical_pe=None
):

    if current_pe is None:

        current_pe = (
            calculate_pe(
                ticker
            )
        )

    historical_median = (
        calculate_historical_pe_median(
            ticker,
            historical_pe=(
                historical_pe
            )
        )
    )

    if (
        current_pe is None
        or historical_median is None
        or historical_median == 0
    ):
        return None

    return (
        current_pe
        - historical_median
    ) / historical_median


def calculate_pe_percentile(
    ticker,
    current_pe=None,
    historical_pe=None
):

    if current_pe is None:

        current_pe = (
            calculate_pe(
                ticker
            )
        )

    if historical_pe is None:

        historical_pe = (
            get_historical_pe(
                ticker
            )
        )

    if (
        current_pe is None
        or historical_pe is None
    ):
        return None

    pe_values = (
        historical_pe[
            "P/E"
        ]
        .dropna()
    )

    if len(
        pe_values
    ) == 0:
        return None

    return (
        pe_values
        < current_pe
    ).mean()


def get_historical_valuation_signal(
    ticker,
    current_pe=None,
    historical_pe=None
):

    percentile = (
        calculate_pe_percentile(
            ticker,
            current_pe=(
                current_pe
            ),
            historical_pe=(
                historical_pe
            )
        )
    )

    if percentile is None:
        return None

    if percentile >= 0.80:
        return "Expensive"

    elif percentile >= 0.60:
        return "Above Historical Average"

    elif percentile >= 0.40:
        return "Normal"

    elif percentile >= 0.20:
        return "Below Historical Average"

    return "Cheap"


# =========================================================
# Peer Valuation
# =========================================================

def get_peer_valuation_table(
    tickers
):
    """
    Fetch each peer's company.info ONCE.

    Previously each peer could trigger
    five separate info requests.
    """

    rows = []

    for ticker in tickers:

        ticker = (
            ticker
            .upper()
            .strip()
        )

        try:

            info = (
                get_company_info(
                    ticker
                )
            )

        except Exception as error:

            print(
                f"Peer info failed for "
                f"{ticker}: {error}"
            )

            info = {}

        rows.append(
            {
                "Ticker":
                    ticker,

                "P/E":
                    calculate_pe(
                        ticker,
                        info=info
                    ),

                "Forward P/E":
                    calculate_forward_pe(
                        ticker,
                        info=info
                    ),

                "P/B":
                    calculate_price_to_book(
                        ticker,
                        info=info
                    ),

                "P/S":
                    calculate_price_to_sales(
                        ticker,
                        info=info
                    ),

                "EV/EBITDA":
                    calculate_ev_to_ebitda(
                        ticker,
                        info=info
                    )
            }
        )

    return (
        pd.DataFrame(
            rows
        )
    )


def calculate_peer_median(
    peer_tickers,
    metric,
    peer_table=None
):
    """
    Calculate peer median.

    PERFORMANCE:
    If only one metric is needed,
    fetch that metric once per ticker,
    rather than building the full table.
    """

    valid_metrics = {
        "P/E",
        "Forward P/E",
        "P/B",
        "P/S",
        "EV/EBITDA"
    }

    if metric not in valid_metrics:
        return None

    # -----------------------------------------------------
    # Reuse table if supplied
    # -----------------------------------------------------

    if peer_table is not None:

        if metric not in (
            peer_table.columns
        ):
            return None

        values = (
            peer_table[
                metric
            ]
            .dropna()
        )

        if len(values) == 0:
            return None

        return (
            values.median()
        )

    # -----------------------------------------------------
    # Single-metric fast path
    # -----------------------------------------------------

    values = []

    for ticker in peer_tickers:

        ticker = (
            ticker
            .upper()
            .strip()
        )

        try:

            info = (
                get_company_info(
                    ticker
                )
            )

        except Exception as error:

            print(
                f"Peer info failed for "
                f"{ticker}: {error}"
            )

            continue

        value = (
            get_metric_from_info(
                info,
                metric
            )
        )

        if value is not None:

            values.append(
                value
            )

    if not values:
        return None

    return (
        pd.Series(
            values
        )
        .median()
    )


def get_company_valuation_metric(
    ticker,
    metric,
    info=None
):

    if info is None:

        info = (
            get_company_info(
                ticker
            )
        )

    return (
        get_metric_from_info(
            info,
            metric
        )
    )


def calculate_peer_premium(
    ticker,
    peer_tickers,
    metric,
    company_info=None,
    peer_table=None
):

    company_value = (
        get_company_valuation_metric(
            ticker,
            metric,
            info=(
                company_info
            )
        )
    )

    peer_median = (
        calculate_peer_median(
            peer_tickers,
            metric,
            peer_table=(
                peer_table
            )
        )
    )

    if (
        company_value is None
        or peer_median is None
        or peer_median == 0
    ):
        return None

    return (
        company_value
        - peer_median
    ) / peer_median


def get_peer_comparison_summary(
    ticker,
    peer_tickers
):
    """
    Build peer table ONCE,
    then calculate all five metrics from it.
    """

    metrics = [
        "P/E",
        "Forward P/E",
        "P/B",
        "P/S",
        "EV/EBITDA"
    ]

    company_info = (
        get_company_info(
            ticker
        )
    )

    peer_table = (
        get_peer_valuation_table(
            peer_tickers
        )
    )

    results = {}

    for metric in metrics:

        company_value = (
            get_company_valuation_metric(
                ticker,
                metric,
                info=(
                    company_info
                )
            )
        )

        peer_median = (
            calculate_peer_median(
                peer_tickers,
                metric,
                peer_table=(
                    peer_table
                )
            )
        )

        premium = None

        if (
            company_value is not None
            and peer_median is not None
            and peer_median != 0
        ):

            premium = (
                company_value
                - peer_median
            ) / peer_median

        results[
            metric
        ] = {

            "Company":
                company_value,

            "Peer Median":
                peer_median,

            "Premium / Discount":
                premium
        }

    return results


# =========================================================
# Valuation Summary
# =========================================================

def get_valuation_summary(
    ticker
):
    """
    Main valuation metrics.

    Company info and historical PE
    are each prepared only once.
    """

    info = (
        get_company_info(
            ticker
        )
    )

    current_price = (
        get_current_price(
            ticker,
            info=info
        )
    )

    market_cap = (
        get_market_cap(
            ticker,
            info=info
        )
    )

    enterprise_value = (
        get_enterprise_value(
            ticker,
            info=info
        )
    )

    pe = (
        calculate_pe(
            ticker,
            info=info
        )
    )

    forward_pe = (
        calculate_forward_pe(
            ticker,
            info=info
        )
    )

    price_to_book = (
        calculate_price_to_book(
            ticker,
            info=info
        )
    )

    price_to_sales = (
        calculate_price_to_sales(
            ticker,
            info=info
        )
    )

    ev_to_ebitda = (
        calculate_ev_to_ebitda(
            ticker,
            info=info
        )
    )

    earnings_yield = (
        calculate_earnings_yield(
            ticker,
            info=info
        )
    )

    fcf_yield = (
        calculate_fcf_yield(
            ticker,
            info=info
        )
    )

    historical_pe = (
        get_historical_pe(
            ticker
        )
    )

    historical_median = (
        calculate_historical_pe_median(
            ticker,
            historical_pe=(
                historical_pe
            )
        )
    )

    historical_premium = (
        calculate_pe_premium_to_history(
            ticker,
            current_pe=pe,
            historical_pe=(
                historical_pe
            )
        )
    )

    historical_percentile = (
        calculate_pe_percentile(
            ticker,
            current_pe=pe,
            historical_pe=(
                historical_pe
            )
        )
    )

    historical_signal = (
        get_historical_valuation_signal(
            ticker,
            current_pe=pe,
            historical_pe=(
                historical_pe
            )
        )
    )

    return {

        "Ticker":
            ticker.upper(),

        "Current Price":
            current_price,

        "Market Cap":
            market_cap,

        "Enterprise Value":
            enterprise_value,

        "P/E":
            pe,

        "Forward P/E":
            forward_pe,

        "P/B":
            price_to_book,

        "P/S":
            price_to_sales,

        "EV/EBITDA":
            ev_to_ebitda,

        "Earnings Yield":
            earnings_yield,

        "FCF Yield":
            fcf_yield,

        "Historical P/E Median":
            historical_median,

        "P/E Premium to History":
            historical_premium,

        "Historical P/E Percentile":
            historical_percentile,

        "Historical Valuation Signal":
            historical_signal
    }


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "AAPL"

    peers = [
        "MSFT",
        "GOOGL",
        "NVDA",
        "AMZN"
    ]

    print("\n==============================")
    print(
        f"VALUATION ANALYSIS: "
        f"{ticker}"
    )
    print("==============================")

    print(
        get_valuation_summary(
            ticker
        )
    )

    print("\n==============================")
    print("PEER VALUATION")
    print("==============================")

    peer_table = (
        get_peer_valuation_table(
            peers
        )
    )

    print(
        peer_table
    )

    print(
        "\nPeer Median P/E:"
    )

    print(
        calculate_peer_median(
            peers,
            "P/E",
            peer_table=peer_table
        )
    )

    print(
        "\nFull Peer Comparison:"
    )

    print(
        get_peer_comparison_summary(
            ticker,
            peers
        )
    )
