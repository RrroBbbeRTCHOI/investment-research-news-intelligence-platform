from src.data.reuse import scoped
from src.data.financial_data import (
    get_operating_income,
    get_pretax_income,
    get_income_tax_expense,
    get_depreciation_amortization,
    get_capex,
    get_change_in_working_capital,
    get_free_cash_flow
)


# =========================================================
# Configuration
# =========================================================

NORMALIZED_FCFF_WEIGHTS = [
    0.50,
    0.30,
    0.20
]


# =========================================================
# Helpers
# =========================================================

def clean_series(series):
    """
    Drop missing values from a financial Series.
    """

    if series is None:
        return None

    series = series.dropna()

    if len(series) == 0:
        return None

    return series


def get_common_dates(series_map):
    """
    Find dates available across all required
    financial statement series.
    """

    cleaned = {}

    for name, series in series_map.items():

        series = clean_series(series)

        if series is None:
            return []

        cleaned[name] = series

    common_dates = None

    for series in cleaned.values():

        dates = set(
            series.index
        )

        if common_dates is None:
            common_dates = dates

        else:

            common_dates = (
                common_dates
                & dates
            )

    if not common_dates:
        return []

    return sorted(
        common_dates,
        reverse=True
    )


# =========================================================
# Historical FCFF Bridge
# =========================================================

def calculate_fcff_for_date(
    operating_income,
    pretax_income,
    tax_expense,
    depreciation_amortization,
    capex,
    working_capital_adjustment
):
    """
    Calculate FCFF for one fiscal period.

    Effective Tax Rate
    =
    Tax Provision / Pretax Income

    NOPAT
    =
    Operating Income
    × (1 - Effective Tax Rate)

    FCFF
    =
    NOPAT
    + D&A
    + CapEx
    + Working Capital Adjustment

    IMPORTANT:
    CapEx and working capital values from
    yfinance already contain cash-flow signs.
    """

    if (
        pretax_income is None
        or pretax_income <= 0
    ):
        return None

    tax_rate = (
        tax_expense
        / pretax_income
    )

    if (
        tax_rate < 0
        or tax_rate > 0.60
    ):
        return None

    nopat = (
        operating_income
        * (
            1
            - tax_rate
        )
    )

    fcff = (
        nopat
        + depreciation_amortization
        + capex
        + working_capital_adjustment
    )

    return {
        "Operating Income":
            float(
                operating_income
            ),

        "Pretax Income":
            float(
                pretax_income
            ),

        "Tax Provision":
            float(
                tax_expense
            ),

        "Effective Tax Rate":
            float(
                tax_rate
            ),

        "NOPAT":
            float(
                nopat
            ),

        "D&A":
            float(
                depreciation_amortization
            ),

        "Capital Expenditure":
            float(
                capex
            ),

        "Working Capital Adjustment":
            float(
                working_capital_adjustment
            ),

        "FCFF":
            float(
                fcff
            )
    }


# =========================================================
# FCFF History
# =========================================================

def get_fcff_history(
    ticker,
    years=3
):
    """
    Calculate historical FCFF bridges
    for recent fiscal years.

    Only periods with all required
    inputs are included.
    """

    operating_income = (
        get_operating_income(
            ticker
        )
    )

    pretax_income = (
        get_pretax_income(
            ticker
        )
    )

    tax_expense = (
        get_income_tax_expense(
            ticker
        )
    )

    depreciation_amortization = (
        get_depreciation_amortization(
            ticker
        )
    )

    capex = (
        get_capex(
            ticker
        )
    )

    working_capital_adjustment = (
        get_change_in_working_capital(
            ticker
        )
    )

    series_map = {
        "Operating Income":
            operating_income,

        "Pretax Income":
            pretax_income,

        "Tax Provision":
            tax_expense,

        "D&A":
            depreciation_amortization,

        "Capital Expenditure":
            capex,

        "Working Capital Adjustment":
            working_capital_adjustment
    }

    common_dates = (
        get_common_dates(
            series_map
        )
    )

    results = []

    for date in (
        common_dates[:years]
    ):

        result = (
            calculate_fcff_for_date(
                operating_income=(
                    operating_income.loc[
                        date
                    ]
                ),
                pretax_income=(
                    pretax_income.loc[
                        date
                    ]
                ),
                tax_expense=(
                    tax_expense.loc[
                        date
                    ]
                ),
                depreciation_amortization=(
                    depreciation_amortization.loc[
                        date
                    ]
                ),
                capex=(
                    capex.loc[
                        date
                    ]
                ),
                working_capital_adjustment=(
                    working_capital_adjustment.loc[
                        date
                    ]
                )
            )
        )

        if result is None:
            continue

        result[
            "Date"
        ] = date

        results.append(
            result
        )

    return results


# =========================================================
# Latest FCFF
# =========================================================

def calculate_fcff(
    ticker
):
    """
    Return latest calculated FCFF.
    """

    history = (
        get_fcff_history(
            ticker,
            years=1
        )
    )

    if not history:
        return None

    return (
        history[
            0
        ][
            "FCFF"
        ]
    )


# =========================================================
# Normalized FCFF
# =========================================================

def calculate_normalized_fcff(
    ticker
):
    """
    Calculate normalized FCFF using
    the latest three valid fiscal years.

    Custom research weights:

        Latest Year      50%
        Previous Year    30%
        Third Year       20%

    Missing years are excluded and
    available weights are re-normalized.
    """

    history = (
        get_fcff_history(
            ticker,
            years=3
        )
    )

    if not history:
        return None

    weighted_total = 0
    available_weight = 0

    for index, item in enumerate(
        history
    ):

        if index >= len(
            NORMALIZED_FCFF_WEIGHTS
        ):
            break

        fcff = (
            item.get(
                "FCFF"
            )
        )

        if fcff is None:
            continue

        weight = (
            NORMALIZED_FCFF_WEIGHTS[
                index
            ]
        )

        weighted_total += (
            fcff
            * weight
        )

        available_weight += (
            weight
        )

    if available_weight == 0:
        return None

    return (
        weighted_total
        / available_weight
    )


# =========================================================
# Reported FCF History
# =========================================================

def get_reported_fcf_history(
    ticker,
    years=3
):
    """
    Return reported yfinance Free Cash Flow
    for comparison only.

    This is NOT treated as FCFF.
    """

    series = (
        clean_series(
            get_free_cash_flow(
                ticker
            )
        )
    )

    if series is None:
        return []

    results = []

    for date, value in (
        series.iloc[:years].items()
    ):

        results.append(
            {
                "Date":
                    date,

                "Reported FCF":
                    float(
                        value
                    )
            }
        )

    return results


# =========================================================
# FCFF Summary
# =========================================================

@scoped
def get_fcff_summary(
    ticker
):
    """
    Return transparent FCFF V2 summary.
    """

    history = (
        get_fcff_history(
            ticker,
            years=3
        )
    )

    normalized_fcff = (
        calculate_normalized_fcff(
            ticker
        )
    )

    reported_fcf = (
        get_reported_fcf_history(
            ticker,
            years=3
        )
    )

    if len(history) >= 3:

        status = "Complete"

    elif len(history) > 0:

        status = "Partial"

    else:

        status = "Incomplete"

    return {
        "Ticker":
            ticker.upper(),

        "Status":
            status,

        "FCFF History":
            history,

        "Normalized FCFF":
            normalized_fcff,

        "Reported FCF History":
            reported_fcf
    }


# =========================================================
# Formatting
# =========================================================

def format_money(
    value
):

    if value is None:
        return "N/A"

    return (
        f"${value:,.2f}"
    )


def format_percentage(
    value
):

    if value is None:
        return "N/A"

    return (
        f"{value:.2%}"
    )


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "AAPL"

    summary = (
        get_fcff_summary(
            ticker
        )
    )

    print("\n==============================")
    print(
        f"FCFF MODEL V2: "
        f"{ticker}"
    )
    print("==============================")

    print(
        "\nStatus: "
        f"{summary['Status']}"
    )

    print("\n==============================")
    print("HISTORICAL FCFF")
    print("==============================")

    for item in (
        summary[
            "FCFF History"
        ]
    ):

        date = (
            item[
                "Date"
            ]
        )

        print(
            f"\nFiscal Period: "
            f"{date.date()}"
        )

        print(
            "Operating Income: "
            f"{format_money(item['Operating Income'])}"
        )

        print(
            "Effective Tax Rate: "
            f"{format_percentage(item['Effective Tax Rate'])}"
        )

        print(
            "NOPAT: "
            f"{format_money(item['NOPAT'])}"
        )

        print(
            "D&A: "
            f"{format_money(item['D&A'])}"
        )

        print(
            "Capital Expenditure: "
            f"{format_money(item['Capital Expenditure'])}"
        )

        print(
            "Working Capital Adjustment: "
            f"{format_money(item['Working Capital Adjustment'])}"
        )

        print(
            "FCFF: "
            f"{format_money(item['FCFF'])}"
        )

    print("\n==============================")
    print("NORMALIZED FCFF")
    print("==============================")

    print(
        "Normalized FCFF: "
        f"{format_money(summary['Normalized FCFF'])}"
    )

    print(
        "Weights: "
        "50% / 30% / 20%"
    )

    print("\n==============================")
    print("REPORTED FCF REFERENCE")
    print("==============================")

    for item in (
        summary[
            "Reported FCF History"
        ]
    ):

        print(
            f"{item['Date'].date()}: "
            f"{format_money(item['Reported FCF'])}"
        )

    print(
        "\nNote:"
    )

    print(
        "Reported FCF is shown only as "
        "a cash-generation reference."
    )

    print(
        "Enterprise DCF will use "
        "Normalized FCFF."
    )