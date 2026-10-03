from src.data.financial_data import (
    get_revenue,
    get_net_income,
    get_operating_income,
    get_total_debt,
    get_equity,
    get_gross_profit,
    get_free_cash_flow,
    get_operating_cash_flow
)


# =========================================================
# Helper Functions
# =========================================================

def get_latest_value(series):
    """
    Return the latest valid value from a financial Series.
    """

    if series is None:
        return None

    series = series.dropna()

    if len(series) == 0:
        return None

    return series.iloc[0]


def get_latest_two_values(series):
    """
    Return the latest two valid values from a financial Series.
    """

    if series is None:
        return None, None

    series = series.dropna()

    if len(series) < 2:
        return None, None

    latest = series.iloc[0]
    previous = series.iloc[1]

    return latest, previous


# =========================================================
# Growth
# =========================================================

def calculate_revenue_growth(ticker):
    """
    Calculate year-over-year revenue growth.
    """

    revenue = get_revenue(ticker)

    latest, previous = get_latest_two_values(revenue)

    if latest is None or previous is None:
        return None

    if previous == 0:
        return None

    return (latest - previous) / previous


def calculate_net_income_growth(ticker):
    """
    Calculate year-over-year net income growth.
    """

    net_income = get_net_income(ticker)

    latest, previous = get_latest_two_values(
        net_income
    )

    if latest is None or previous is None:
        return None

    if previous == 0:
        return None

    return (latest - previous) / previous


def calculate_fcf_growth(ticker):
    """
    Calculate year-over-year free cash flow growth.
    """

    free_cash_flow = get_free_cash_flow(ticker)

    latest, previous = get_latest_two_values(
        free_cash_flow
    )

    if latest is None or previous is None:
        return None

    if previous == 0:
        return None

    return (latest - previous) / previous


# =========================================================
# Profitability
# =========================================================

def calculate_gross_margin(ticker):
    """
    Gross Profit / Revenue
    """

    revenue = get_latest_value(
        get_revenue(ticker)
    )

    gross_profit = get_latest_value(
        get_gross_profit(ticker)
    )

    if revenue is None or gross_profit is None:
        return None

    if revenue == 0:
        return None

    return gross_profit / revenue


def calculate_operating_margin(ticker):
    """
    Operating Income / Revenue
    """

    revenue = get_latest_value(
        get_revenue(ticker)
    )

    operating_income = get_latest_value(
        get_operating_income(ticker)
    )

    if revenue is None or operating_income is None:
        return None

    if revenue == 0:
        return None

    return operating_income / revenue


def calculate_net_margin(ticker):
    """
    Net Income / Revenue
    """

    revenue = get_latest_value(
        get_revenue(ticker)
    )

    net_income = get_latest_value(
        get_net_income(ticker)
    )

    if revenue is None or net_income is None:
        return None

    if revenue == 0:
        return None

    return net_income / revenue


def calculate_roe(ticker):
    """
    Return on Equity.

    Net Income / Shareholders' Equity

    Note:
    This is currently a simplified version using
    latest year-end equity.
    """

    net_income = get_latest_value(
        get_net_income(ticker)
    )

    equity = get_latest_value(
        get_equity(ticker)
    )

    if net_income is None or equity is None:
        return None

    if equity == 0:
        return None

    return net_income / equity


def calculate_roic(ticker):
    """
    Simplified Return on Invested Capital.

    Operating Income /
    (Total Debt + Shareholders' Equity)

    This will later be upgraded to a more professional
    NOPAT / Invested Capital calculation.
    """

    operating_income = get_latest_value(
        get_operating_income(ticker)
    )

    debt = get_latest_value(
        get_total_debt(ticker)
    )

    equity = get_latest_value(
        get_equity(ticker)
    )

    if (
        operating_income is None
        or debt is None
        or equity is None
    ):
        return None

    invested_capital = debt + equity

    if invested_capital == 0:
        return None

    return operating_income / invested_capital


# =========================================================
# Financial Health
# =========================================================

def calculate_debt_to_equity(ticker):
    """
    Total Debt / Shareholders' Equity
    """

    debt = get_latest_value(
        get_total_debt(ticker)
    )

    equity = get_latest_value(
        get_equity(ticker)
    )

    if debt is None or equity is None:
        return None

    if equity == 0:
        return None

    return debt / equity


# =========================================================
# Earnings Quality
# =========================================================

def calculate_cash_conversion(ticker):
    """
    Operating Cash Flow / Net Income

    A value above 1 generally means operating cash flow
    exceeds reported net income.
    """

    operating_cash_flow = get_latest_value(
        get_operating_cash_flow(ticker)
    )

    net_income = get_latest_value(
        get_net_income(ticker)
    )

    if (
        operating_cash_flow is None
        or net_income is None
    ):
        return None

    if net_income == 0:
        return None

    return operating_cash_flow / net_income


# =========================================================
# Fundamental Summary
# =========================================================

def get_fundamental_summary(ticker):
    """
    Return the main fundamental metrics
    in one dictionary.
    """

    return {
        "Ticker": ticker.upper(),
        "Revenue Growth": calculate_revenue_growth(
            ticker
        ),
        "Net Income Growth": calculate_net_income_growth(
            ticker
        ),
        "FCF Growth": calculate_fcf_growth(
            ticker
        ),
        "Gross Margin": calculate_gross_margin(
            ticker
        ),
        "Operating Margin": calculate_operating_margin(
            ticker
        ),
        "Net Margin": calculate_net_margin(
            ticker
        ),
        "ROE": calculate_roe(
            ticker
        ),
        "ROIC": calculate_roic(
            ticker
        ),
        "Debt-to-Equity": calculate_debt_to_equity(
            ticker
        ),
        "Cash Conversion": calculate_cash_conversion(
            ticker
        )
    }


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "AAPL"

    print("\n==============================")
    print(f"FUNDAMENTAL ANALYSIS: {ticker}")
    print("==============================")

    summary = get_fundamental_summary(ticker)

    for metric, value in summary.items():

        if metric == "Ticker":
            print(f"\n{metric}: {value}")
            continue

        if value is None:
            print(f"{metric}: N/A")
        else:
            print(f"{metric}: {value:.4f}")