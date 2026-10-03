from src.data.reuse import memoized
import requests

from src.config import SEC_USER_AGENT


# =========================================================
# SEC Configuration
# =========================================================

SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate"
}

COMPANY_TICKERS_URL = (
    "https://www.sec.gov/files/company_tickers.json"
)

COMPANY_FACTS_BASE_URL = (
    "https://data.sec.gov/api/xbrl/companyfacts"
)


# =========================================================
# Ticker -> CIK
# =========================================================

@memoized
def get_company_cik(ticker):
    """
    Convert stock ticker into SEC CIK number.

    Example:
        AAPL -> 0000320193
    """

    ticker = ticker.upper().strip()

    response = requests.get(
        COMPANY_TICKERS_URL,
        headers=SEC_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    companies = response.json()

    for company in companies.values():

        if company["ticker"].upper() == ticker:

            return str(
                company["cik_str"]
            ).zfill(10)

    return None


# =========================================================
# Company Facts
# =========================================================

@memoized
def get_company_facts(ticker):
    """
    Return SEC Company Facts JSON.
    """

    cik = get_company_cik(ticker)

    if cik is None:
        return None

    url = (
        f"{COMPANY_FACTS_BASE_URL}/"
        f"CIK{cik}.json"
    )

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# US-GAAP Facts
# =========================================================

def get_available_us_gaap_facts(ticker):
    """
    Return all available US-GAAP facts
    reported by a company.
    """

    facts = get_company_facts(
        ticker
    )

    if facts is None:
        return None

    return (
        facts
        .get("facts", {})
        .get("us-gaap", {})
    )


def get_sec_fact(
    ticker,
    fact_name
):
    """
    Return one SEC US-GAAP fact.
    """

    us_gaap = (
        get_available_us_gaap_facts(
            ticker
        )
    )

    if us_gaap is None:
        return None

    return us_gaap.get(
        fact_name
    )


# =========================================================
# Period Configuration
# =========================================================

def get_period_settings(period):
    """
    Define filing type.

    annual:
        Latest 10-K / FY

    quarterly:
        Latest 10-Q
    """

    if period == "annual":

        return {
            "forms": ("10-K",),
            "fiscal_periods": ("FY",)
        }

    elif period == "quarterly":

        return {
            "forms": ("10-Q",),
            "fiscal_periods": (
                "Q1",
                "Q2",
                "Q3"
            )
        }

    else:

        raise ValueError(
            "period must be "
            "'annual' or 'quarterly'"
        )


# =========================================================
# Latest SEC Value
# =========================================================

def get_latest_sec_value(
    ticker,
    fact_names,
    unit="USD",
    period="annual",
    require_fiscal_period=True
):
    """
    Return latest SEC value.

    Supports multiple fallback XBRL tags.
    """

    if isinstance(
        fact_names,
        str
    ):
        fact_names = [
            fact_names
        ]

    settings = get_period_settings(
        period
    )

    allowed_forms = (
        settings["forms"]
    )

    allowed_fp = (
        settings["fiscal_periods"]
    )

    for fact_name in fact_names:

        fact = get_sec_fact(
            ticker,
            fact_name
        )

        if fact is None:
            continue

        units = fact.get(
            "units",
            {}
        )

        observations = units.get(
            unit,
            []
        )

        valid = []

        for item in observations:

            if (
                item.get("form")
                not in allowed_forms
            ):
                continue

            if require_fiscal_period:

                fp = item.get("fp")

                if (
                    fp is not None
                    and fp not in allowed_fp
                ):
                    continue

            valid.append(
                item
            )

        if len(valid) == 0:
            continue

        valid = sorted(
            valid,
            key=lambda item: (
                item.get("end", ""),
                item.get("filed", "")
            ),
            reverse=True
        )

        latest = valid[0]

        return {
            "fact_name":
                fact_name,

            "value":
                latest.get("val"),

            "start":
                latest.get("start"),

            "end":
                latest.get("end"),

            "filed":
                latest.get("filed"),

            "form":
                latest.get("form"),

            "accession":
                latest.get("accn"),

            "fiscal_year":
                latest.get("fy"),

            "fiscal_period":
                latest.get("fp")
        }

    return None


# =========================================================
# SEC Value for Specific Fiscal Year
# =========================================================

def get_sec_value_for_fiscal_year(
    ticker,
    fact_names,
    fiscal_year,
    unit="USD",
    form="10-K"
):
    """
    Return SEC value for a specific fiscal year.

    IMPORTANT:
    This function does NOT fall back
    to older fiscal years.

    If the requested fiscal year
    does not exist, return None.
    """

    if isinstance(
        fact_names,
        str
    ):
        fact_names = [
            fact_names
        ]

    for fact_name in fact_names:

        fact = get_sec_fact(
            ticker,
            fact_name
        )

        if fact is None:
            continue

        units = fact.get(
            "units",
            {}
        )

        observations = units.get(
            unit,
            []
        )

        valid = []

        for item in observations:

            if (
                item.get("form")
                != form
            ):
                continue

            if (
                item.get("fy")
                != fiscal_year
            ):
                continue

            fp = item.get("fp")

            if (
                form == "10-K"
                and fp is not None
                and fp != "FY"
            ):
                continue

            valid.append(
                item
            )

        if len(valid) == 0:
            continue

        valid = sorted(
            valid,
            key=lambda item: (
                item.get("end", ""),
                item.get("filed", "")
            ),
            reverse=True
        )

        latest = valid[0]

        return {
            "fact_name":
                fact_name,

            "value":
                latest.get("val"),

            "start":
                latest.get("start"),

            "end":
                latest.get("end"),

            "filed":
                latest.get("filed"),

            "form":
                latest.get("form"),

            "accession":
                latest.get("accn"),

            "fiscal_year":
                latest.get("fy"),

            "fiscal_period":
                latest.get("fp")
        }

    return None


# =========================================================
# Revenue
# =========================================================

def get_sec_revenue(
    ticker,
    period="annual"
):
    """
    Return Revenue.
    """

    return get_latest_sec_value(
        ticker,
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet"
        ],
        period=period
    )


# =========================================================
# Latest Fiscal Year
# =========================================================

def get_latest_fiscal_year(ticker):
    """
    Return latest annual fiscal year
    using Revenue as reference.
    """

    revenue = get_sec_revenue(
        ticker,
        period="annual"
    )

    if revenue is None:
        return None

    return revenue.get(
        "fiscal_year"
    )


# =========================================================
# Net Income
# =========================================================

def get_sec_net_income(
    ticker,
    period="annual"
):
    """
    Return Net Income.
    """

    return get_latest_sec_value(
        ticker,
        [
            "NetIncomeLoss",
            "ProfitLoss"
        ],
        period=period
    )


# =========================================================
# Operating Income
# =========================================================

def get_sec_operating_income(
    ticker,
    period="annual"
):
    """
    Return Operating Income.
    """

    return get_latest_sec_value(
        ticker,
        [
            "OperatingIncomeLoss"
        ],
        period=period
    )


# =========================================================
# Pretax Income
# =========================================================

def get_sec_pretax_income(
    ticker,
    period="annual"
):
    """
    Return income before tax.
    """

    return get_latest_sec_value(
        ticker,
        [
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxes"
        ],
        period=period
    )


# =========================================================
# Operating Cash Flow
# =========================================================

def get_sec_operating_cash_flow(
    ticker,
    period="annual"
):
    """
    Return Operating Cash Flow.
    """

    return get_latest_sec_value(
        ticker,
        [
            "NetCashProvidedByUsedInOperatingActivities"
        ],
        period=period
    )


# =========================================================
# CapEx
# =========================================================

def get_sec_capex(
    ticker,
    period="annual"
):
    """
    Return capital expenditure.

    SEC generally reports this as
    positive cash paid for PP&E.
    """

    return get_latest_sec_value(
        ticker,
        [
            "PaymentsToAcquirePropertyPlantAndEquipment"
        ],
        period=period
    )


# =========================================================
# Free Cash Flow
# =========================================================

def calculate_sec_free_cash_flow(
    ticker,
    period="annual"
):
    """
    Free Cash Flow =

    Operating Cash Flow - CapEx
    """

    ocf = (
        get_sec_operating_cash_flow(
            ticker,
            period
        )
    )

    capex = (
        get_sec_capex(
            ticker,
            period
        )
    )

    if (
        ocf is None
        or capex is None
    ):
        return None

    ocf_value = ocf.get(
        "value"
    )

    capex_value = capex.get(
        "value"
    )

    if (
        ocf_value is None
        or capex_value is None
    ):
        return None

    return {
        "value":
            ocf_value - capex_value,

        "operating_cash_flow":
            ocf_value,

        "capex":
            capex_value,

        "period_end":
            ocf.get("end"),

        "form":
            ocf.get("form")
    }


# =========================================================
# Instant Balance Sheet Helper
# =========================================================

def get_latest_balance_sheet_value(
    ticker,
    fact_names,
    period="annual"
):
    """
    Retrieve point-in-time balance sheet values.
    """

    return get_latest_sec_value(
        ticker,
        fact_names,
        period=period,
        require_fiscal_period=False
    )


# =========================================================
# Cash
# =========================================================

def get_sec_cash(
    ticker,
    period="annual"
):
    """
    Return cash and cash equivalents.
    """

    return get_latest_balance_sheet_value(
        ticker,
        [
            "CashAndCashEquivalentsAtCarryingValue"
        ],
        period
    )


# =========================================================
# Short-Term Investments
# =========================================================

def get_sec_short_term_investments(
    ticker,
    period="annual"
):
    """
    Return short-term investments /
    marketable securities when available.
    """

    return get_latest_balance_sheet_value(
        ticker,
        [
            "ShortTermInvestments",
            "MarketableSecuritiesCurrent"
        ],
        period
    )


# =========================================================
# Assets
# =========================================================

def get_sec_total_assets(
    ticker,
    period="annual"
):
    """
    Return Total Assets.
    """

    return get_latest_balance_sheet_value(
        ticker,
        [
            "Assets"
        ],
        period
    )


# =========================================================
# Equity
# =========================================================

def get_sec_equity(
    ticker,
    period="annual"
):
    """
    Return shareholders' equity.
    """

    return get_latest_balance_sheet_value(
        ticker,
        [
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
        ],
        period
    )


# =========================================================
# Debt Components
# =========================================================

def get_sec_current_debt(
    ticker,
    period="annual"
):
    """
    Current portion of debt.
    """

    return get_latest_balance_sheet_value(
        ticker,
        [
            "LongTermDebtCurrent",
            "LongTermDebtAndFinanceLeaseObligationsCurrent"
        ],
        period
    )


def get_sec_long_term_debt(
    ticker,
    period="annual"
):
    """
    Non-current long-term debt.
    """

    return get_latest_balance_sheet_value(
        ticker,
        [
            "LongTermDebtNoncurrent",
            "LongTermDebtAndFinanceLeaseObligationsNoncurrent"
        ],
        period
    )


def get_sec_commercial_paper(
    ticker,
    period="annual"
):
    """
    Commercial paper / short-term borrowing.
    """

    return get_latest_balance_sheet_value(
        ticker,
        [
            "CommercialPaper",
            "ShortTermBorrowings"
        ],
        period
    )


# =========================================================
# Total Debt
# =========================================================

def calculate_sec_total_debt(
    ticker,
    period="annual"
):
    """
    Approximate Total Debt:

    Current Debt
    + Long-Term Debt
    + Commercial Paper
    """

    components = {
        "Current Debt":
            get_sec_current_debt(
                ticker,
                period
            ),

        "Long-Term Debt":
            get_sec_long_term_debt(
                ticker,
                period
            ),

        "Commercial Paper":
            get_sec_commercial_paper(
                ticker,
                period
            )
    }

    total = 0
    found = False

    component_values = {}

    for name, item in (
        components.items()
    ):

        if (
            item is None
            or item.get("value") is None
        ):

            component_values[
                name
            ] = None

            continue

        value = item["value"]

        component_values[
            name
        ] = value

        total += value
        found = True

    if not found:
        return None

    return {
        "value":
            total,

        "components":
            component_values
    }


# =========================================================
# Net Debt
# =========================================================

def calculate_sec_net_debt(
    ticker,
    period="annual"
):
    """
    V1 Net Debt:

    Total Debt - Cash
    """

    debt = (
        calculate_sec_total_debt(
            ticker,
            period
        )
    )

    cash = (
        get_sec_cash(
            ticker,
            period
        )
    )

    if debt is None:
        return None

    total_debt = debt["value"]

    cash_value = 0

    if (
        cash is not None
        and cash.get("value") is not None
    ):

        cash_value = (
            cash["value"]
        )

    return {
        "value":
            total_debt - cash_value,

        "total_debt":
            total_debt,

        "cash":
            cash_value
    }


# =========================================================
# Interest Income
# =========================================================

def get_sec_interest_income(
    ticker,
    period="annual"
):
    """
    Return interest-related income.

    For annual data, the value MUST match
    the latest fiscal year.

    Older fiscal years are not used
    as fallback.
    """

    fact_names = [
        "InvestmentIncomeInterestAndDividend",
        "InterestIncomeExpenseNonoperatingNet",
        "InterestAndOtherNet"
    ]

    if period != "annual":

        return get_latest_sec_value(
            ticker,
            fact_names,
            period=period
        )

    fiscal_year = (
        get_latest_fiscal_year(
            ticker
        )
    )

    if fiscal_year is None:
        return None

    return get_sec_value_for_fiscal_year(
        ticker,
        fact_names,
        fiscal_year=fiscal_year,
        form="10-K"
    )


# =========================================================
# Investment Gain / Loss
# =========================================================

def get_sec_investment_gain_loss(
    ticker,
    period="annual"
):
    """
    Return investment gains / losses.

    IMPORTANT:
    Interest/dividend income is NOT included
    here to avoid double counting.
    """

    fact_names = [
        "GainLossOnSaleOfInvestments",
        "GainLossOnInvestments"
    ]

    if period != "annual":

        return get_latest_sec_value(
            ticker,
            fact_names,
            period=period
        )

    fiscal_year = (
        get_latest_fiscal_year(
            ticker
        )
    )

    if fiscal_year is None:
        return None

    return get_sec_value_for_fiscal_year(
        ticker,
        fact_names,
        fiscal_year=fiscal_year,
        form="10-K"
    )


# =========================================================
# Other Non-operating Income
# =========================================================

def get_sec_other_non_operating_income(
    ticker,
    period="annual"
):
    """
    Return other non-operating
    income / expense.

    Annual data must match
    the latest fiscal year.
    """

    fact_names = [
        "NonoperatingIncomeExpense",
        "OtherNonoperatingIncomeExpense"
    ]

    if period != "annual":

        return get_latest_sec_value(
            ticker,
            fact_names,
            period=period
        )

    fiscal_year = (
        get_latest_fiscal_year(
            ticker
        )
    )

    if fiscal_year is None:
        return None

    return get_sec_value_for_fiscal_year(
        ticker,
        fact_names,
        fiscal_year=fiscal_year,
        form="10-K"
    )


# =========================================================
# Earnings Composition
# =========================================================

def get_sec_earnings_composition(
    ticker,
    period="annual"
):
    """
    Return available earnings composition
    components from SEC Company Facts.

    Missing same-period components return N/A
    instead of using stale historical data.
    """

    return {
        "Operating Income":
            get_sec_operating_income(
                ticker,
                period
            ),

        "Pretax Income":
            get_sec_pretax_income(
                ticker,
                period
            ),

        "Interest Income":
            get_sec_interest_income(
                ticker,
                period
            ),

        "Investment Gain / Loss":
            get_sec_investment_gain_loss(
                ticker,
                period
            ),

        "Other Non-operating Income":
            get_sec_other_non_operating_income(
                ticker,
                period
            )
    }


# =========================================================
# Non-operating Contribution
# =========================================================

def calculate_non_operating_contribution(
    ticker,
    period="annual"
):
    """
    Simplified estimate:

    Pretax Income - Operating Income

    Positive:
        Non-operating items increased pretax income.

    Negative:
        Non-operating items reduced pretax income.
    """

    operating_income = (
        get_sec_operating_income(
            ticker,
            period
        )
    )

    pretax_income = (
        get_sec_pretax_income(
            ticker,
            period
        )
    )

    if (
        operating_income is None
        or pretax_income is None
    ):
        return None

    operating_value = (
        operating_income.get(
            "value"
        )
    )

    pretax_value = (
        pretax_income.get(
            "value"
        )
    )

    if (
        operating_value is None
        or pretax_value is None
    ):
        return None

    contribution = (
        pretax_value
        - operating_value
    )

    return {
        "value":
            contribution,

        "operating_income":
            operating_value,

        "pretax_income":
            pretax_value
    }


# =========================================================
# Non-operating Share
# =========================================================

def calculate_non_operating_share(
    ticker,
    period="annual"
):
    """
    Non-operating Contribution
    /
    Pretax Income
    """

    result = (
        calculate_non_operating_contribution(
            ticker,
            period
        )
    )

    if result is None:
        return None

    pretax_income = (
        result["pretax_income"]
    )

    if pretax_income == 0:
        return None

    share = (
        result["value"]
        / pretax_income
    )

    return {
        "value":
            share,

        "non_operating_contribution":
            result["value"],

        "pretax_income":
            pretax_income
    }


# =========================================================
# SEC Financial Summary
# =========================================================

def get_sec_financial_summary(
    ticker,
    period="annual"
):
    """
    Return SEC financial summary.
    """

    return {
        "Ticker":
            ticker.upper(),

        "Period":
            period,

        "Revenue":
            get_sec_revenue(
                ticker,
                period
            ),

        "Net Income":
            get_sec_net_income(
                ticker,
                period
            ),

        "Operating Income":
            get_sec_operating_income(
                ticker,
                period
            ),

        "Pretax Income":
            get_sec_pretax_income(
                ticker,
                period
            ),

        "Operating Cash Flow":
            get_sec_operating_cash_flow(
                ticker,
                period
            ),

        "CapEx":
            get_sec_capex(
                ticker,
                period
            ),

        "Free Cash Flow":
            calculate_sec_free_cash_flow(
                ticker,
                period
            ),

        "Cash":
            get_sec_cash(
                ticker,
                period
            ),

        "Short-Term Investments":
            get_sec_short_term_investments(
                ticker,
                period
            ),

        "Total Assets":
            get_sec_total_assets(
                ticker,
                period
            ),

        "Equity":
            get_sec_equity(
                ticker,
                period
            ),

        "Total Debt":
            calculate_sec_total_debt(
                ticker,
                period
            ),

        "Net Debt":
            calculate_sec_net_debt(
                ticker,
                period
            ),

        "Non-operating Contribution":
            calculate_non_operating_contribution(
                ticker,
                period
            ),

        "Non-operating Share":
            calculate_non_operating_share(
                ticker,
                period
            )
    }


# =========================================================
# Display Helper
# =========================================================

def print_sec_metric(
    name,
    data
):
    """
    Pretty-print SEC metric.
    """

    print(
        f"\n{name}:"
    )

    if data is None:

        print(
            "N/A"
        )

        return

    if (
        isinstance(data, dict)
        and "value" in data
    ):

        value = (
            data.get("value")
        )

        if value is not None:

            if (
                "Share" in name
                or (
                    isinstance(value, float)
                    and abs(value) < 1
                )
            ):

                print(
                    f"Value: "
                    f"{value:.2%}"
                )

            else:

                print(
                    f"Value: "
                    f"${value:,.0f}"
                )

        if data.get(
            "fact_name"
        ):

            print(
                f"Fact: "
                f"{data['fact_name']}"
            )

        if data.get(
            "fiscal_year"
        ) is not None:

            print(
                f"Fiscal Year: "
                f"{data['fiscal_year']}"
            )

        if data.get(
            "end"
        ):

            print(
                f"Period End: "
                f"{data['end']}"
            )

        if data.get(
            "filed"
        ):

            print(
                f"Filed: "
                f"{data['filed']}"
            )

        if data.get(
            "form"
        ):

            print(
                f"Form: "
                f"{data['form']}"
            )

    else:

        print(
            data
        )


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "AAPL"

    print("\n==============================")
    print(f"SEC TEST: {ticker}")
    print("==============================")

    print(
        f"\nCIK: "
        f"{get_company_cik(ticker)}"
    )

    facts = (
        get_company_facts(
            ticker
        )
    )

    if facts is not None:

        print(
            f"Company: "
            f"{facts.get('entityName')}"
        )

    print(
        f"Latest Fiscal Year: "
        f"{get_latest_fiscal_year(ticker)}"
    )

    # -----------------------------------------------------
    # Annual Data
    # -----------------------------------------------------

    print("\n==============================")
    print("ANNUAL 10-K DATA")
    print("==============================")

    annual = (
        get_sec_financial_summary(
            ticker,
            period="annual"
        )
    )

    annual_metrics = [
        "Revenue",
        "Net Income",
        "Operating Income",
        "Pretax Income",
        "Operating Cash Flow",
        "CapEx",
        "Free Cash Flow",
        "Cash",
        "Total Assets",
        "Equity",
        "Total Debt",
        "Net Debt",
        "Non-operating Contribution",
        "Non-operating Share"
    ]

    for metric in annual_metrics:

        print_sec_metric(
            metric,
            annual.get(metric)
        )

    # -----------------------------------------------------
    # Earnings Composition
    # -----------------------------------------------------

    print("\n==============================")
    print("EARNINGS COMPOSITION")
    print("==============================")

    composition = (
        get_sec_earnings_composition(
            ticker,
            period="annual"
        )
    )

    for name, data in (
        composition.items()
    ):

        print_sec_metric(
            name,
            data
        )

    # -----------------------------------------------------
    # Quarterly Data
    # -----------------------------------------------------

    print("\n==============================")
    print("LATEST 10-Q DATA")
    print("==============================")

    quarterly = (
        get_sec_financial_summary(
            ticker,
            period="quarterly"
        )
    )

    quarterly_metrics = [
        "Revenue",
        "Net Income",
        "Operating Income",
        "Pretax Income",
        "Operating Cash Flow",
        "CapEx",
        "Cash",
        "Total Debt"
    ]

    for metric in quarterly_metrics:

        print_sec_metric(
            metric,
            quarterly.get(metric)
        )