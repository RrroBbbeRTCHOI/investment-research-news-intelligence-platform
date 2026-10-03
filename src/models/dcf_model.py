from src.data.reuse import scoped, memoized
from src.data.financial_data import (
    get_free_cash_flow,
    get_net_debt,
    get_total_debt
)

from src.data.market_data import (
    get_market_cap
)

from src.analysis.valuation import (
    get_current_price,
    get_company_info
)

from src.models.fcff_model import (
    calculate_normalized_fcff,
    get_fcff_history
)


# =========================================================
# WACC Assumptions - V2.4
# =========================================================

WACC_ASSUMPTIONS = {

    "risk_free_rate":
        0.04,

    "equity_risk_premium":
        0.05,

    "pre_tax_cost_of_debt":
        0.045,

    "tax_rate":
        0.21
}


# =========================================================
# Scenario Settings
# =========================================================

WACC_SCENARIO_SPREAD = 0.01


# =========================================================
# Helpers
# =========================================================

def get_latest_value(series):

    if series is None:
        return None

    series = series.dropna()

    if len(series) == 0:
        return None

    return float(
        series.iloc[0]
    )


# =========================================================
# Shares Outstanding
# =========================================================

def get_shares_outstanding(
    ticker
):

    info = (
        get_company_info(
            ticker
        )
    )

    if not info:
        return None

    shares = (
        info.get(
            "sharesOutstanding"
        )
    )

    if shares is None:
        return None

    try:

        shares = float(
            shares
        )

    except (
        TypeError,
        ValueError
    ):

        return None

    if shares <= 0:
        return None

    return shares


# =========================================================
# Beta
# =========================================================

def get_beta(
    ticker
):

    info = (
        get_company_info(
            ticker
        )
    )

    if not info:
        return None

    beta = (
        info.get(
            "beta"
        )
    )

    if beta is None:
        return None

    try:

        beta = float(
            beta
        )

    except (
        TypeError,
        ValueError
    ):

        return None

    if beta <= 0:
        return None

    return beta


# =========================================================
# Reported FCF
# =========================================================

def get_current_reported_fcf(
    ticker
):

    series = (
        get_free_cash_flow(
            ticker
        )
    )

    return (
        get_latest_value(
            series
        )
    )


# =========================================================
# Net Debt
# =========================================================

def get_current_net_debt(
    ticker
):

    net_debt = (
        get_net_debt(
            ticker
        )
    )

    return (
        get_latest_value(
            net_debt
        )
    )


# =========================================================
# Total Debt
# =========================================================

def get_current_total_debt(
    ticker
):

    total_debt = (
        get_total_debt(
            ticker
        )
    )

    return (
        get_latest_value(
            total_debt
        )
    )


# =========================================================
# Cost of Equity
# =========================================================

def calculate_cost_of_equity_from_beta(
    beta,
    risk_free_rate=None,
    equity_risk_premium=None
):

    if beta is None:
        return None

    if risk_free_rate is None:

        risk_free_rate = (
            WACC_ASSUMPTIONS[
                "risk_free_rate"
            ]
        )

    if equity_risk_premium is None:

        equity_risk_premium = (
            WACC_ASSUMPTIONS[
                "equity_risk_premium"
            ]
        )

    return (
        risk_free_rate
        +
        beta
        * equity_risk_premium
    )


def calculate_cost_of_equity(
    ticker,
    risk_free_rate=None,
    equity_risk_premium=None
):

    beta = (
        get_beta(
            ticker
        )
    )

    return (
        calculate_cost_of_equity_from_beta(
            beta=beta,
            risk_free_rate=risk_free_rate,
            equity_risk_premium=(
                equity_risk_premium
            )
        )
    )


# =========================================================
# After-Tax Cost of Debt
# =========================================================

def calculate_after_tax_cost_of_debt(
    pre_tax_cost_of_debt=None,
    tax_rate=None
):

    if pre_tax_cost_of_debt is None:

        pre_tax_cost_of_debt = (
            WACC_ASSUMPTIONS[
                "pre_tax_cost_of_debt"
            ]
        )

    if tax_rate is None:

        tax_rate = (
            WACC_ASSUMPTIONS[
                "tax_rate"
            ]
        )

    return (
        pre_tax_cost_of_debt
        * (
            1
            - tax_rate
        )
    )


# =========================================================
# Pure WACC Calculation
# =========================================================

def calculate_wacc_from_values(
    market_cap,
    total_debt,
    beta
):

    cost_of_equity = (
        calculate_cost_of_equity_from_beta(
            beta
        )
    )

    after_tax_cost_of_debt = (
        calculate_after_tax_cost_of_debt()
    )

    if (
        market_cap is None
        or total_debt is None
        or cost_of_equity is None
        or after_tax_cost_of_debt is None
    ):
        return None

    capital = (
        market_cap
        + total_debt
    )

    if capital <= 0:
        return None

    equity_weight = (
        market_cap
        / capital
    )

    debt_weight = (
        total_debt
        / capital
    )

    return (
        equity_weight
        * cost_of_equity
        +
        debt_weight
        * after_tax_cost_of_debt
    )


# =========================================================
# DCF Input Snapshot
# =========================================================

@memoized
def prepare_dcf_inputs(
    ticker
):
    """
    Prepare expensive DCF inputs ONCE.

    These values can then be reused by:

        Bear DCF
        Base DCF
        Bull DCF
        Reverse DCF

    This is the main V2.4 performance
    architecture change.
    """

    ticker = (
        ticker
        .upper()
        .strip()
    )

    # -----------------------------------------------------
    # Company Info - ONE request
    # -----------------------------------------------------

    company_info = (
        get_company_info(
            ticker
        )
        or {}
    )

    # -----------------------------------------------------
    # Shares
    # -----------------------------------------------------

    shares = (
        company_info.get(
            "sharesOutstanding"
        )
    )

    try:

        if shares is not None:
            shares = float(
                shares
            )

    except (
        TypeError,
        ValueError
    ):

        shares = None

    if (
        shares is not None
        and shares <= 0
    ):
        shares = None

    # -----------------------------------------------------
    # Beta
    # -----------------------------------------------------

    beta = (
        company_info.get(
            "beta"
        )
    )

    try:

        if beta is not None:
            beta = float(
                beta
            )

    except (
        TypeError,
        ValueError
    ):

        beta = None

    if (
        beta is not None
        and beta <= 0
    ):
        beta = None

    # -----------------------------------------------------
    # Core Financial Inputs
    # -----------------------------------------------------

    normalized_fcff = (
        calculate_normalized_fcff(
            ticker
        )
    )

    net_debt = (
        get_current_net_debt(
            ticker
        )
    )

    total_debt = (
        get_current_total_debt(
            ticker
        )
    )

    market_cap = (
        get_market_cap(
            ticker
        )
    )

    current_price = (
        get_current_price(
            ticker
        )
    )

    # -----------------------------------------------------
    # WACC
    # -----------------------------------------------------

    wacc = (
        calculate_wacc_from_values(
            market_cap=market_cap,
            total_debt=total_debt,
            beta=beta
        )
    )

    return {

        "Ticker":
            ticker,

        "Normalized FCFF":
            normalized_fcff,

        "Net Debt":
            net_debt,

        "Total Debt":
            total_debt,

        "Shares Outstanding":
            shares,

        "Market Cap":
            market_cap,

        "Current Price":
            current_price,

        "Beta":
            beta,

        "WACC":
            wacc,

        "Company Info":
            company_info
    }


# =========================================================
# WACC
# =========================================================

def calculate_wacc(
    ticker,
    inputs=None
):

    if inputs is not None:

        wacc = (
            inputs.get(
                "WACC"
            )
        )

        if wacc is not None:
            return wacc

    market_cap = (
        get_market_cap(
            ticker
        )
    )

    total_debt = (
        get_current_total_debt(
            ticker
        )
    )

    beta = (
        get_beta(
            ticker
        )
    )

    return (
        calculate_wacc_from_values(
            market_cap=market_cap,
            total_debt=total_debt,
            beta=beta
        )
    )


# =========================================================
# WACC Summary
# =========================================================

def get_wacc_summary(
    ticker,
    inputs=None
):

    if inputs is None:

        inputs = (
            prepare_dcf_inputs(
                ticker
            )
        )

    beta = (
        inputs.get(
            "Beta"
        )
    )

    market_cap = (
        inputs.get(
            "Market Cap"
        )
    )

    total_debt = (
        inputs.get(
            "Total Debt"
        )
    )

    wacc = (
        inputs.get(
            "WACC"
        )
    )

    risk_free_rate = (
        WACC_ASSUMPTIONS[
            "risk_free_rate"
        ]
    )

    equity_risk_premium = (
        WACC_ASSUMPTIONS[
            "equity_risk_premium"
        ]
    )

    pre_tax_cost_of_debt = (
        WACC_ASSUMPTIONS[
            "pre_tax_cost_of_debt"
        ]
    )

    tax_rate = (
        WACC_ASSUMPTIONS[
            "tax_rate"
        ]
    )

    cost_of_equity = (
        calculate_cost_of_equity_from_beta(
            beta=beta,
            risk_free_rate=risk_free_rate,
            equity_risk_premium=(
                equity_risk_premium
            )
        )
    )

    after_tax_cost_of_debt = (
        calculate_after_tax_cost_of_debt(
            pre_tax_cost_of_debt,
            tax_rate
        )
    )

    equity_weight = None
    debt_weight = None

    if (
        market_cap is not None
        and total_debt is not None
        and (
            market_cap
            + total_debt
        ) > 0
    ):

        capital = (
            market_cap
            + total_debt
        )

        equity_weight = (
            market_cap
            / capital
        )

        debt_weight = (
            total_debt
            / capital
        )

    missing = []

    if beta is None:
        missing.append(
            "Beta"
        )

    if market_cap is None:
        missing.append(
            "Market Cap"
        )

    if total_debt is None:
        missing.append(
            "Total Debt"
        )

    status = (
        "Complete"
        if not missing
        else "Incomplete"
    )

    return {

        "Status":
            status,

        "Missing Inputs":
            missing,

        "Beta":
            beta,

        "Beta Source":
            "yfinance",

        "Risk-Free Rate":
            risk_free_rate,

        "Risk-Free Rate Source":
            "Model Assumption",

        "Equity Risk Premium":
            equity_risk_premium,

        "ERP Source":
            "Model Assumption",

        "Cost of Equity":
            cost_of_equity,

        "Pre-Tax Cost of Debt":
            pre_tax_cost_of_debt,

        "Cost of Debt Source":
            "Model Assumption",

        "Tax Rate":
            tax_rate,

        "Tax Rate Source":
            "Model Assumption",

        "After-Tax Cost of Debt":
            after_tax_cost_of_debt,

        "Market Cap":
            market_cap,

        "Total Debt":
            total_debt,

        "Equity Weight":
            equity_weight,

        "Debt Weight":
            debt_weight,

        "WACC":
            wacc
    }


# =========================================================
# DCF Input Status
# =========================================================

def get_dcf_input_status(
    ticker,
    inputs=None
):

    if inputs is None:

        inputs = (
            prepare_dcf_inputs(
                ticker
            )
        )

    normalized_fcff = (
        inputs.get(
            "Normalized FCFF"
        )
    )

    net_debt = (
        inputs.get(
            "Net Debt"
        )
    )

    shares = (
        inputs.get(
            "Shares Outstanding"
        )
    )

    wacc = (
        inputs.get(
            "WACC"
        )
    )

    missing = []

    if normalized_fcff is None:
        missing.append(
            "Normalized FCFF"
        )

    if net_debt is None:
        missing.append(
            "Net Debt"
        )

    if shares is None:
        missing.append(
            "Shares Outstanding"
        )

    if wacc is None:
        missing.append(
            "WACC"
        )

    status = (
        "Complete"
        if not missing
        else "Incomplete"
    )

    return {

        "Status":
            status,

        "Missing Inputs":
            missing,

        "Normalized FCFF":
            normalized_fcff,

        "Net Debt":
            net_debt,

        "Shares Outstanding":
            shares,

        "WACC":
            wacc
    }


# =========================================================
# Forecast FCFF
# =========================================================

def forecast_free_cash_flow(
    ticker,
    growth_rate=0.07,
    years=5,
    inputs=None
):

    if inputs is None:

        normalized_fcff = (
            calculate_normalized_fcff(
                ticker
            )
        )

    else:

        normalized_fcff = (
            inputs.get(
                "Normalized FCFF"
            )
        )

    if normalized_fcff is None:
        return None

    forecasts = []

    for year in range(
        1,
        years + 1
    ):

        future_fcff = (
            normalized_fcff
            * (
                1
                + growth_rate
            ) ** year
        )

        forecasts.append(
            {
                "Year":
                    year,

                "FCFF":
                    future_fcff
            }
        )

    return forecasts


# =========================================================
# Discount Forecast FCFF
# =========================================================

def discount_forecast_cash_flows(
    forecasts,
    discount_rate
):

    if forecasts is None:
        return None

    discounted = []

    for item in forecasts:

        year = (
            item[
                "Year"
            ]
        )

        future_fcff = (
            item[
                "FCFF"
            ]
        )

        present_value = (
            future_fcff
            /
            (
                1
                + discount_rate
            ) ** year
        )

        discounted.append(
            {
                "Year":
                    year,

                "FCFF":
                    future_fcff,

                "PV":
                    present_value
            }
        )

    return discounted


# =========================================================
# Terminal Value
# =========================================================

def calculate_terminal_value(
    final_year_fcf,
    discount_rate,
    terminal_growth_rate
):

    if (
        final_year_fcf is None
        or discount_rate
        <= terminal_growth_rate
    ):
        return None

    terminal_fcff = (
        final_year_fcf
        * (
            1
            + terminal_growth_rate
        )
    )

    return (
        terminal_fcff
        /
        (
            discount_rate
            - terminal_growth_rate
        )
    )


# =========================================================
# PV Terminal Value
# =========================================================

def calculate_terminal_value_pv(
    terminal_value,
    years,
    discount_rate
):

    if terminal_value is None:
        return None

    return (
        terminal_value
        /
        (
            1
            + discount_rate
        ) ** years
    )


# =========================================================
# DCF Enterprise Value
# =========================================================

def calculate_dcf_enterprise_value(
    ticker,
    growth_rate=0.07,
    discount_rate=None,
    terminal_growth_rate=0.025,
    years=5,
    inputs=None
):

    if inputs is None:

        inputs = (
            prepare_dcf_inputs(
                ticker
            )
        )

    if discount_rate is None:

        discount_rate = (
            inputs.get(
                "WACC"
            )
        )

    if discount_rate is None:
        return None

    forecasts = (
        forecast_free_cash_flow(
            ticker=ticker,
            growth_rate=growth_rate,
            years=years,
            inputs=inputs
        )
    )

    if forecasts is None:
        return None

    discounted = (
        discount_forecast_cash_flows(
            forecasts=forecasts,
            discount_rate=discount_rate
        )
    )

    if discounted is None:
        return None

    pv_forecast_fcff = sum(
        item[
            "PV"
        ]
        for item in discounted
    )

    final_year_fcff = (
        forecasts[
            -1
        ][
            "FCFF"
        ]
    )

    terminal_value = (
        calculate_terminal_value(
            final_year_fcf=(
                final_year_fcff
            ),
            discount_rate=(
                discount_rate
            ),
            terminal_growth_rate=(
                terminal_growth_rate
            )
        )
    )

    if terminal_value is None:
        return None

    terminal_value_pv = (
        calculate_terminal_value_pv(
            terminal_value=(
                terminal_value
            ),
            years=years,
            discount_rate=(
                discount_rate
            )
        )
    )

    if terminal_value_pv is None:
        return None

    return (
        pv_forecast_fcff
        + terminal_value_pv
    )


# =========================================================
# DCF Equity Value
# =========================================================

def calculate_dcf_equity_value(
    ticker,
    growth_rate=0.07,
    discount_rate=None,
    terminal_growth_rate=0.025,
    years=5,
    inputs=None
):

    if inputs is None:

        inputs = (
            prepare_dcf_inputs(
                ticker
            )
        )

    enterprise_value = (
        calculate_dcf_enterprise_value(
            ticker=ticker,
            growth_rate=growth_rate,
            discount_rate=discount_rate,
            terminal_growth_rate=(
                terminal_growth_rate
            ),
            years=years,
            inputs=inputs
        )
    )

    if enterprise_value is None:
        return None

    net_debt = (
        inputs.get(
            "Net Debt"
        )
    )

    if net_debt is None:
        return None

    return (
        enterprise_value
        - net_debt
    )


# =========================================================
# DCF Fair Value Per Share
# =========================================================

def calculate_dcf_fair_value(
    ticker,
    growth_rate=0.07,
    discount_rate=None,
    terminal_growth_rate=0.025,
    years=5,
    inputs=None
):

    if inputs is None:

        inputs = (
            prepare_dcf_inputs(
                ticker
            )
        )

    equity_value = (
        calculate_dcf_equity_value(
            ticker=ticker,
            growth_rate=growth_rate,
            discount_rate=discount_rate,
            terminal_growth_rate=(
                terminal_growth_rate
            ),
            years=years,
            inputs=inputs
        )
    )

    shares = (
        inputs.get(
            "Shares Outstanding"
        )
    )

    if (
        equity_value is None
        or shares is None
        or shares == 0
    ):
        return None

    return (
        equity_value
        / shares
    )


# =========================================================
# DCF Upside / Downside
# =========================================================

def calculate_dcf_upside(
    ticker,
    growth_rate=0.07,
    discount_rate=None,
    terminal_growth_rate=0.025,
    years=5,
    inputs=None,
    fair_value=None
):

    if inputs is None:

        inputs = (
            prepare_dcf_inputs(
                ticker
            )
        )

    current_price = (
        inputs.get(
            "Current Price"
        )
    )

    if fair_value is None:

        fair_value = (
            calculate_dcf_fair_value(
                ticker=ticker,
                growth_rate=growth_rate,
                discount_rate=discount_rate,
                terminal_growth_rate=(
                    terminal_growth_rate
                ),
                years=years,
                inputs=inputs
            )
        )

    if (
        current_price is None
        or fair_value is None
        or current_price == 0
    ):
        return None

    return (
        fair_value
        - current_price
    ) / current_price


# =========================================================
# DCF Scenarios V2.4
# =========================================================

def get_dcf_scenarios(
    ticker,
    inputs=None
):

    if inputs is None:

        inputs = (
            prepare_dcf_inputs(
                ticker
            )
        )

    base_wacc = (
        inputs.get(
            "WACC"
        )
    )

    if base_wacc is None:
        return {}

    scenarios = {

        "Bear": {

            "growth_rate":
                0.04,

            "discount_rate":
                base_wacc
                + WACC_SCENARIO_SPREAD,

            "terminal_growth_rate":
                0.02
        },

        "Base": {

            "growth_rate":
                0.07,

            "discount_rate":
                base_wacc,

            "terminal_growth_rate":
                0.025
        },

        "Bull": {

            "growth_rate":
                0.10,

            "discount_rate":
                max(
                    base_wacc
                    - WACC_SCENARIO_SPREAD,
                    0.001
                ),

            "terminal_growth_rate":
                0.03
        }
    }

    results = {}

    for name, assumptions in (
        scenarios.items()
    ):

        fair_value = (
            calculate_dcf_fair_value(
                ticker=ticker,
                growth_rate=(
                    assumptions[
                        "growth_rate"
                    ]
                ),
                discount_rate=(
                    assumptions[
                        "discount_rate"
                    ]
                ),
                terminal_growth_rate=(
                    assumptions[
                        "terminal_growth_rate"
                    ]
                ),
                years=5,
                inputs=inputs
            )
        )

        # IMPORTANT:
        # reuse fair_value instead of
        # calculating DCF again.

        upside = (
            calculate_dcf_upside(
                ticker=ticker,
                growth_rate=(
                    assumptions[
                        "growth_rate"
                    ]
                ),
                discount_rate=(
                    assumptions[
                        "discount_rate"
                    ]
                ),
                terminal_growth_rate=(
                    assumptions[
                        "terminal_growth_rate"
                    ]
                ),
                years=5,
                inputs=inputs,
                fair_value=fair_value
            )
        )

        results[
            name
        ] = {

            "Growth Rate":
                assumptions[
                    "growth_rate"
                ],

            "Discount Rate":
                assumptions[
                    "discount_rate"
                ],

            "Terminal Growth":
                assumptions[
                    "terminal_growth_rate"
                ],

            "Fair Value":
                fair_value,

            "Upside / Downside":
                upside
        }

    return results


# =========================================================
# DCF Summary
# =========================================================

@scoped
def get_dcf_summary(
    ticker
):

    inputs = (
        prepare_dcf_inputs(
            ticker
        )
    )

    input_status = (
        get_dcf_input_status(
            ticker,
            inputs=inputs
        )
    )

    fair_value = (
        calculate_dcf_fair_value(
            ticker,
            inputs=inputs
        )
    )

    upside = (
        calculate_dcf_upside(
            ticker,
            inputs=inputs,
            fair_value=fair_value
        )
    )

    return {

        "Ticker":
            ticker.upper(),

        "Current Price":
            inputs.get(
                "Current Price"
            ),

        "FCFF History":
            get_fcff_history(
                ticker,
                years=3
            ),

        "Normalized FCFF":
            inputs.get(
                "Normalized FCFF"
            ),

        "Reported FCF Reference":
            get_current_reported_fcf(
                ticker
            ),

        "Net Debt":
            inputs.get(
                "Net Debt"
            ),

        "Shares Outstanding":
            inputs.get(
                "Shares Outstanding"
            ),

        "WACC Summary":
            get_wacc_summary(
                ticker,
                inputs=inputs
            ),

        "Input Status":
            input_status[
                "Status"
            ],

        "Missing Inputs":
            input_status[
                "Missing Inputs"
            ],

        "DCF Fair Value":
            fair_value,

        "DCF Upside / Downside":
            upside
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

    print("\n==============================")
    print(
        f"DCF MODEL V2.4: "
        f"{ticker}"
    )
    print("==============================")

    summary = (
        get_dcf_summary(
            ticker
        )
    )

    print(
        "\nCurrent Price: "
        f"{format_money(summary['Current Price'])}"
    )

    print(
        "Normalized FCFF: "
        f"{format_money(summary['Normalized FCFF'])}"
    )

    print(
        "Net Debt: "
        f"{format_money(summary['Net Debt'])}"
    )

    print(
        "Shares Outstanding: "
        f"{summary['Shares Outstanding']}"
    )

    print(
        "DCF Fair Value: "
        f"{format_money(summary['DCF Fair Value'])}"
    )

    print(
        "DCF Upside / Downside: "
        f"{format_percentage(summary['DCF Upside / Downside'])}"
    )

    print("\n==============================")
    print("DCF SCENARIOS")
    print("==============================")

    inputs = (
        prepare_dcf_inputs(
            ticker
        )
    )

    scenarios = (
        get_dcf_scenarios(
            ticker,
            inputs=inputs
        )
    )

    for name, data in (
        scenarios.items()
    ):

        print(
            f"\n{name} Case"
        )

        print(
            "Fair Value: "
            f"{format_money(data['Fair Value'])}"
        )

        print(
            "Upside / Downside: "
            f"{format_percentage(data['Upside / Downside'])}"
        )