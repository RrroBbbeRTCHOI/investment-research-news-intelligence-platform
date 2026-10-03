from src.config import (
    HISTORICAL_TREND_YEARS,
    RESEARCH_UNIVERSE,
)

from src.data.historical_financial_data import (
    get_income_history,
    get_cash_flow_history,
)


# =========================================================
# HELPERS
# =========================================================

def _safe_divide(
    numerator,
    denominator
):
    """
    Safely divide two numbers.
    """

    if numerator is None:
        return None

    if denominator in (
        None,
        0
    ):
        return None

    return (
        numerator
        / denominator
    )


def _calculate_growth(
    current,
    previous
):
    """
    Calculate year-over-year growth with
    research validity rules.

    Returns:

        {
            "value": float or None,
            "status": str
        }

    Status:
        normal
        turned_profitable
        turned_loss_making
        not_meaningful
        missing
    """

    # -----------------------------------------------------
    # Missing Values
    # -----------------------------------------------------

    if (
        current is None
        or previous is None
    ):

        return {
            "value":
                None,

            "status":
                "missing",
        }

    # -----------------------------------------------------
    # Near-Zero Denominator
    # -----------------------------------------------------

    if abs(previous) < 1e-9:

        return {
            "value":
                None,

            "status":
                "not_meaningful",
        }

    # -----------------------------------------------------
    # Loss -> Profit
    # -----------------------------------------------------

    if (
        previous < 0
        and current > 0
    ):

        return {
            "value":
                None,

            "status":
                "turned_profitable",
        }

    # -----------------------------------------------------
    # Profit -> Loss
    # -----------------------------------------------------

    if (
        previous > 0
        and current < 0
    ):

        return {
            "value":
                None,

            "status":
                "turned_loss_making",
        }

    # -----------------------------------------------------
    # Loss -> Loss
    # -----------------------------------------------------

    if (
        previous < 0
        and current < 0
    ):

        return {
            "value":
                None,

            "status":
                "not_meaningful",
        }

    # -----------------------------------------------------
    # Normal Growth
    # -----------------------------------------------------

    growth = (
        current
        / previous
    ) - 1

    return {
        "value":
            growth,

        "status":
            "normal",
    }


def _sort_by_year(
    history
):
    """
    Sort financial history from oldest
    fiscal year to newest.
    """

    valid_rows = []

    for row in history:

        year = row.get(
            "year"
        )

        if year is None:
            continue

        valid_rows.append(
            row
        )

    return sorted(
        valid_rows,
        key=lambda row: int(
            row["year"]
        )
    )


def _latest_years(
    history,
    years
):
    """
    Keep only the latest requested
    number of fiscal years.
    """

    history = _sort_by_year(
        history
    )

    return history[
        -years:
    ]


# =========================================================
# REVENUE GROWTH
# =========================================================

def calculate_revenue_growth_from_data(
    income_history
):
    """
    Calculate annual revenue growth.

    Current FMP setup:
        5 raw annual observations
        ->
        4 YoY growth observations
    """

    income_history = (
        _sort_by_year(
            income_history
        )
    )

    result = []

    for index in range(
        1,
        len(income_history)
    ):

        current = (
            income_history[
                index
            ]
        )

        previous = (
            income_history[
                index - 1
            ]
        )

        growth_result = (
            _calculate_growth(
                current.get(
                    "revenue"
                ),
                previous.get(
                    "revenue"
                )
            )
        )

        result.append(
            {
                "year":
                    current.get(
                        "year"
                    ),

                "revenue":
                    current.get(
                        "revenue"
                    ),

                "revenue_growth":
                    growth_result[
                        "value"
                    ],

                "growth_status":
                    growth_result[
                        "status"
                    ],
            }
        )

    return result


# =========================================================
# EPS GROWTH
# =========================================================

def calculate_eps_growth_from_data(
    income_history
):
    """
    Calculate annual EPS growth.

    Handles:
        profit -> loss
        loss -> profit
        loss -> loss
        near-zero denominator
    """

    income_history = (
        _sort_by_year(
            income_history
        )
    )

    result = []

    for index in range(
        1,
        len(income_history)
    ):

        current = (
            income_history[
                index
            ]
        )

        previous = (
            income_history[
                index - 1
            ]
        )

        growth_result = (
            _calculate_growth(
                current.get(
                    "eps"
                ),
                previous.get(
                    "eps"
                )
            )
        )

        result.append(
            {
                "year":
                    current.get(
                        "year"
                    ),

                "eps":
                    current.get(
                        "eps"
                    ),

                "eps_growth":
                    growth_result[
                        "value"
                    ],

                "growth_status":
                    growth_result[
                        "status"
                    ],
            }
        )

    return result


# =========================================================
# OPERATING MARGIN
# =========================================================

def calculate_operating_margin_from_data(
    income_history,
    display_years
):
    """
    Operating Margin:

        Operating Income
        ----------------
            Revenue
    """

    income_history = (
        _latest_years(
            income_history,
            display_years
        )
    )

    result = []

    for row in income_history:

        revenue = row.get(
            "revenue"
        )

        operating_income = row.get(
            "operating_income"
        )

        margin = (
            _safe_divide(
                operating_income,
                revenue
            )
        )

        result.append(
            {
                "year":
                    row.get(
                        "year"
                    ),

                "revenue":
                    revenue,

                "operating_income":
                    operating_income,

                "operating_margin":
                    margin,
            }
        )

    return result


# =========================================================
# FCF MARGIN
# =========================================================

def calculate_fcf_margin_from_data(
    income_history,
    cash_flow_history,
    display_years
):
    """
    FCF Margin:

        Free Cash Flow
        --------------
            Revenue
    """

    revenue_by_year = {

        str(
            row.get(
                "year"
            )
        ):
            row.get(
                "revenue"
            )

        for row in income_history

        if row.get(
            "year"
        ) is not None
    }

    fcf_by_year = {

        str(
            row.get(
                "year"
            )
        ):
            row.get(
                "free_cash_flow"
            )

        for row in cash_flow_history

        if row.get(
            "year"
        ) is not None
    }

    common_years = sorted(

        set(
            revenue_by_year.keys()
        )
        &
        set(
            fcf_by_year.keys()
        ),

        key=int
    )

    common_years = (
        common_years[
            -display_years:
        ]
    )

    result = []

    for year in common_years:

        revenue = (
            revenue_by_year[
                year
            ]
        )

        free_cash_flow = (
            fcf_by_year[
                year
            ]
        )

        margin = (
            _safe_divide(
                free_cash_flow,
                revenue
            )
        )

        result.append(
            {
                "year":
                    year,

                "revenue":
                    revenue,

                "free_cash_flow":
                    free_cash_flow,

                "fcf_margin":
                    margin,
            }
        )

    return result


# =========================================================
# COMPANY HISTORICAL TRENDS BUILDER
# =========================================================

def build_company_historical_trends(
    ticker,
    years=HISTORICAL_TREND_YEARS
):
    """
    Main historical financial trend builder
    for one company.

    Current structure:

        5 annual raw observations
        4 YoY growth observations
        5 annual margin observations

    Returns:

        {
            "ticker": ...,
            "revenue_growth": [...],
            "eps_growth": [...],
            "operating_margin": [...],
            "fcf_margin": [...]
        }
    """

    ticker = (
        ticker
        .upper()
        .strip()
    )

    # -----------------------------------------------------
    # Load Historical Financial Data
    # -----------------------------------------------------

    income_history = (
        get_income_history(
            ticker,
            years=years
        )
    )

    cash_flow_history = (
        get_cash_flow_history(
            ticker,
            years=years
        )
    )

    # -----------------------------------------------------
    # Validation
    # -----------------------------------------------------

    if len(
        income_history
    ) < years:

        print(
            f"[WARNING] {ticker}: "
            f"Expected {years} years "
            f"of income data, "
            f"received "
            f"{len(income_history)}."
        )

    if len(
        cash_flow_history
    ) < years:

        print(
            f"[WARNING] {ticker}: "
            f"Expected {years} years "
            f"of cash flow data, "
            f"received "
            f"{len(cash_flow_history)}."
        )

    # -----------------------------------------------------
    # Revenue Growth
    # -----------------------------------------------------

    revenue_growth = (
        calculate_revenue_growth_from_data(
            income_history
        )
    )

    # -----------------------------------------------------
    # EPS Growth
    # -----------------------------------------------------

    eps_growth = (
        calculate_eps_growth_from_data(
            income_history
        )
    )

    # -----------------------------------------------------
    # Operating Margin
    # -----------------------------------------------------

    operating_margin = (
        calculate_operating_margin_from_data(
            income_history,
            years
        )
    )

    # -----------------------------------------------------
    # FCF Margin
    # -----------------------------------------------------

    fcf_margin = (
        calculate_fcf_margin_from_data(
            income_history,
            cash_flow_history,
            years
        )
    )

    # -----------------------------------------------------
    # Final Output
    # -----------------------------------------------------

    return {
        "ticker":
            ticker,

        "revenue_growth":
            revenue_growth,

        "eps_growth":
            eps_growth,

        "operating_margin":
            operating_margin,

        "fcf_margin":
            fcf_margin,
    }


# =========================================================
# BACKWARD-COMPATIBILITY BUILDER
# =========================================================

def build_historical_trends(
    ticker,
    years=HISTORICAL_TREND_YEARS
):
    """
    Backward-compatible wrapper.

    Older code may still call:

        build_historical_trends()

    New UI code should use:

        build_company_historical_trends()
    """

    return (
        build_company_historical_trends(
            ticker,
            years=years
        )
    )


# =========================================================
# FORMATTING HELPERS
# =========================================================

def _format_percent(
    value
):
    """
    Decimal -> percentage.
    """

    if value is None:
        return "N/A"

    return (
        f"{value * 100:.2f}%"
    )


def _format_growth(
    value,
    status
):
    """
    Format research-grade
    growth result.
    """

    if status == "turned_profitable":

        return (
            "Turned Profitable"
        )

    if status == "turned_loss_making":

        return (
            "Turned Loss-Making"
        )

    if status == "not_meaningful":

        return "N/M"

    if status == "missing":

        return "N/A"

    if value is None:

        return "N/A"

    return (
        f"{value * 100:.2f}%"
    )


def _format_billions(
    value
):
    """
    Raw financial value
    -> billions.
    """

    if value is None:
        return "N/A"

    return (
        f"${value / 1_000_000_000:.2f}B"
    )


# =========================================================
# SINGLE COMPANY TEST
# =========================================================

def test_single_company(
    ticker
):

    print("\n")
    print("=" * 75)

    print(
        f"{ticker} HISTORICAL TRENDS"
    )

    print("=" * 75)

    trends = (
        build_company_historical_trends(
            ticker
        )
    )

    # -----------------------------------------------------
    # Revenue Growth
    # -----------------------------------------------------

    print(
        "\nREVENUE GROWTH"
    )

    print(
        "-" * 75
    )

    for row in trends[
        "revenue_growth"
    ]:

        print(
            row["year"],
            "| Revenue:",
            _format_billions(
                row[
                    "revenue"
                ]
            ),
            "| Growth:",
            _format_growth(
                row[
                    "revenue_growth"
                ],
                row[
                    "growth_status"
                ]
            )
        )

    # -----------------------------------------------------
    # EPS Growth
    # -----------------------------------------------------

    print(
        "\nEPS GROWTH"
    )

    print(
        "-" * 75
    )

    for row in trends[
        "eps_growth"
    ]:

        print(
            row["year"],
            "| EPS:",
            row[
                "eps"
            ],
            "| Growth:",
            _format_growth(
                row[
                    "eps_growth"
                ],
                row[
                    "growth_status"
                ]
            )
        )

    # -----------------------------------------------------
    # Operating Margin
    # -----------------------------------------------------

    print(
        "\nOPERATING MARGIN"
    )

    print(
        "-" * 75
    )

    for row in trends[
        "operating_margin"
    ]:

        print(
            row["year"],
            "| Margin:",
            _format_percent(
                row[
                    "operating_margin"
                ]
            )
        )

    # -----------------------------------------------------
    # FCF Margin
    # -----------------------------------------------------

    print(
        "\nFCF MARGIN"
    )

    print(
        "-" * 75
    )

    for row in trends[
        "fcf_margin"
    ]:

        print(
            row["year"],
            "| FCF:",
            _format_billions(
                row[
                    "free_cash_flow"
                ]
            ),
            "| Margin:",
            _format_percent(
                row[
                    "fcf_margin"
                ]
            )
        )


# =========================================================
# MAG7 VALIDATION
# =========================================================

def test_mag7():

    print("\n")
    print("=" * 75)

    print(
        "MAG7 HISTORICAL "
        "TRENDS VALIDATION"
    )

    print("=" * 75)

    successful = []

    failed = []

    for ticker in (
        RESEARCH_UNIVERSE
    ):

        print("\n")
        print("#" * 75)

        print(
            f"TESTING {ticker}"
        )

        print("#" * 75)

        try:

            test_single_company(
                ticker
            )

            successful.append(
                ticker
            )

        except Exception as error:

            failed.append(
                {
                    "ticker":
                        ticker,

                    "error":
                        str(error),
                }
            )

            print(
                f"\n[FAILED] "
                f"{ticker}"
            )

            print(
                "Error:",
                error
            )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    print("\n")
    print("=" * 75)

    print(
        "MAG7 VALIDATION SUMMARY"
    )

    print("=" * 75)

    print(
        "\nSuccessful:"
    )

    print(
        successful
    )

    print(
        "\nFailed:"
    )

    if not failed:

        print(
            "None"
        )

    else:

        for failure in failed:

            print(
                failure[
                    "ticker"
                ],
                "->",
                failure[
                    "error"
                ]
            )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    test_mag7()