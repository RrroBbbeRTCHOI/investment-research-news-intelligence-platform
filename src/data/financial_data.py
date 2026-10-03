import yfinance as yf


# =========================================================
# Company Object
# =========================================================

def get_company_object(ticker):
    """
    Create and return a yfinance Ticker object.
    """

    ticker = ticker.upper().strip()

    return yf.Ticker(ticker)


# =========================================================
# Raw Financial Statements
# =========================================================

def get_income_statement(ticker):
    from src.data.yahoo_provider import statement
    return statement(ticker, 'financials')


def get_balance_sheet(ticker):
    from src.data.yahoo_provider import statement
    return statement(ticker, 'balance_sheet')


def get_cash_flow(ticker):
    from src.data.yahoo_provider import statement
    return statement(ticker, 'cashflow')


# =========================================================
# Helper Functions
# =========================================================

def get_financial_row(
    statement,
    row_name
):
    """
    Return one financial statement row.
    """

    if statement is None:
        return None

    if statement.empty:
        return None

    if row_name not in statement.index:
        return None

    return statement.loc[
        row_name
    ]


def get_first_available_row(
    statement,
    possible_rows
):
    """
    Return the first available row
    from a list of possible row names.

    Useful because yfinance row naming
    can vary between companies.
    """

    for row_name in possible_rows:

        result = (
            get_financial_row(
                statement,
                row_name
            )
        )

        if result is not None:
            return result

    return None


# =========================================================
# Income Statement Data
# =========================================================

def get_revenue(ticker):

    statement = (
        get_income_statement(
            ticker
        )
    )

    return (
        get_financial_row(
            statement,
            "Total Revenue"
        )
    )


def get_net_income(ticker):

    statement = (
        get_income_statement(
            ticker
        )
    )

    return (
        get_financial_row(
            statement,
            "Net Income"
        )
    )


def get_operating_income(ticker):
    """
    Operating Income.

    Used as EBIT proxy in
    the initial FCFF model.
    """

    statement = (
        get_income_statement(
            ticker
        )
    )

    return (
        get_financial_row(
            statement,
            "Operating Income"
        )
    )


def get_pretax_income(ticker):
    """
    Return Pretax Income.

    Used for effective tax-rate
    calculation.
    """

    statement = (
        get_income_statement(
            ticker
        )
    )

    possible_rows = [
        "Pretax Income",
        "Income Before Tax",
        "Income Before Taxes"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


def get_income_tax_expense(ticker):
    """
    Return income tax expense /
    tax provision.
    """

    statement = (
        get_income_statement(
            ticker
        )
    )

    possible_rows = [
        "Tax Provision",
        "Income Tax Expense",
        "Income Tax Expense Benefit"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


def get_gross_profit(ticker):

    statement = (
        get_income_statement(
            ticker
        )
    )

    return (
        get_financial_row(
            statement,
            "Gross Profit"
        )
    )


def get_ebitda(ticker):

    statement = (
        get_income_statement(
            ticker
        )
    )

    possible_rows = [
        "EBITDA",
        "Normalized EBITDA"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


def get_diluted_eps(ticker):
    """
    Return historical diluted EPS.
    """

    statement = (
        get_income_statement(
            ticker
        )
    )

    return (
        get_financial_row(
            statement,
            "Diluted EPS"
        )
    )


# =========================================================
# Balance Sheet Data
# =========================================================

def get_total_debt(ticker):

    statement = (
        get_balance_sheet(
            ticker
        )
    )

    return (
        get_financial_row(
            statement,
            "Total Debt"
        )
    )


def get_net_debt(ticker):

    statement = (
        get_balance_sheet(
            ticker
        )
    )

    return (
        get_financial_row(
            statement,
            "Net Debt"
        )
    )


def get_cash(ticker):

    statement = (
        get_balance_sheet(
            ticker
        )
    )

    possible_rows = [
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


def get_equity(ticker):

    statement = (
        get_balance_sheet(
            ticker
        )
    )

    possible_rows = [
        "Stockholders Equity",
        "Total Stockholder Equity",
        "Common Stock Equity"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


def get_total_assets(ticker):

    statement = (
        get_balance_sheet(
            ticker
        )
    )

    return (
        get_financial_row(
            statement,
            "Total Assets"
        )
    )


def get_current_assets(ticker):
    """
    Return Total Current Assets.
    """

    statement = (
        get_balance_sheet(
            ticker
        )
    )

    possible_rows = [
        "Current Assets",
        "Total Current Assets"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


def get_current_liabilities(ticker):
    """
    Return Total Current Liabilities.
    """

    statement = (
        get_balance_sheet(
            ticker
        )
    )

    possible_rows = [
        "Current Liabilities",
        "Total Current Liabilities"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


# =========================================================
# Cash Flow Data
# =========================================================

def get_operating_cash_flow(ticker):

    statement = (
        get_cash_flow(
            ticker
        )
    )

    possible_rows = [
        "Operating Cash Flow",
        "Total Cash From Operating Activities"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


def get_capex(ticker):

    statement = (
        get_cash_flow(
            ticker
        )
    )

    possible_rows = [
        "Capital Expenditure",
        "Capital Expenditures"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


def get_free_cash_flow(ticker):

    statement = (
        get_cash_flow(
            ticker
        )
    )

    return (
        get_financial_row(
            statement,
            "Free Cash Flow"
        )
    )


def get_depreciation_amortization(ticker):
    """
    Return Depreciation & Amortization.

    Required for FCFF construction.
    """

    statement = (
        get_cash_flow(
            ticker
        )
    )

    possible_rows = [
        "Depreciation And Amortization",
        "Depreciation Amortization Depletion",
        "Depreciation",
        "Depreciation And Amortization In Income Statement"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


def get_change_in_working_capital(ticker):
    """
    Return cash-flow-statement
    Change in Working Capital.

    IMPORTANT:
    We only expose the raw reported
    series here.

    FCFF logic will handle the
    sign convention separately.
    """

    statement = (
        get_cash_flow(
            ticker
        )
    )

    possible_rows = [
        "Change In Working Capital",
        "Change In Working Capital Change",
        "Changes In Account Receivables"
    ]

    return (
        get_first_available_row(
            statement,
            possible_rows
        )
    )


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "AAPL"

    print("\n==============================")
    print(f"FINANCIAL DATA TEST: {ticker}")
    print("==============================")

    print("\nRevenue:")
    print(
        get_revenue(
            ticker
        )
    )

    print("\nNet Income:")
    print(
        get_net_income(
            ticker
        )
    )

    print("\nOperating Income / EBIT Proxy:")
    print(
        get_operating_income(
            ticker
        )
    )

    print("\nPretax Income:")
    print(
        get_pretax_income(
            ticker
        )
    )

    print("\nIncome Tax Expense:")
    print(
        get_income_tax_expense(
            ticker
        )
    )

    print("\nEBITDA:")
    print(
        get_ebitda(
            ticker
        )
    )

    print("\nTotal Debt:")
    print(
        get_total_debt(
            ticker
        )
    )

    print("\nNet Debt:")
    print(
        get_net_debt(
            ticker
        )
    )

    print("\nCash:")
    print(
        get_cash(
            ticker
        )
    )

    print("\nEquity:")
    print(
        get_equity(
            ticker
        )
    )

    print("\nCurrent Assets:")
    print(
        get_current_assets(
            ticker
        )
    )

    print("\nCurrent Liabilities:")
    print(
        get_current_liabilities(
            ticker
        )
    )

    print("\nOperating Cash Flow:")
    print(
        get_operating_cash_flow(
            ticker
        )
    )

    print("\nCapital Expenditure:")
    print(
        get_capex(
            ticker
        )
    )

    print("\nFree Cash Flow:")
    print(
        get_free_cash_flow(
            ticker
        )
    )

    print("\nDepreciation & Amortization:")
    print(
        get_depreciation_amortization(
            ticker
        )
    )

    print("\nChange in Working Capital:")
    print(
        get_change_in_working_capital(
            ticker
        )
    )
