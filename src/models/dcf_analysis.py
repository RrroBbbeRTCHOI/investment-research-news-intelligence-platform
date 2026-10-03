from src.models.dcf_model import (
    calculate_dcf_fair_value,
    calculate_wacc,
    prepare_dcf_inputs
)


# =========================================================
# Configuration
# =========================================================

DEFAULT_TERMINAL_GROWTH = 0.025

DEFAULT_YEARS = 5


# =========================================================
# Helpers
# =========================================================

def format_money(value):

    if value is None:
        return "N/A"

    return f"${value:,.2f}"


def format_percentage(value):

    if value is None:
        return "N/A"

    return f"{value:.2%}"


# =========================================================
# DCF Sensitivity Analysis
# =========================================================

def run_dcf_sensitivity(
    ticker,
    growth_rates=None,
    discount_rates=None,
    terminal_growth_rate=DEFAULT_TERMINAL_GROWTH,
    years=DEFAULT_YEARS,
    inputs=None
):

    if inputs is None:

        inputs = (
            prepare_dcf_inputs(
                ticker
            )
        )

    if growth_rates is None:

        growth_rates = [
            0.03,
            0.05,
            0.07,
            0.09,
            0.11,
            0.13
        ]

    if discount_rates is None:

        base_wacc = (
            calculate_wacc(
                ticker,
                inputs=inputs
            )
        )

        if base_wacc is None:
            return None

        discount_rates = [
            base_wacc - 0.02,
            base_wacc - 0.01,
            base_wacc,
            base_wacc + 0.01,
            base_wacc + 0.02
        ]

    results = []

    for growth_rate in growth_rates:

        row = {
            "Growth Rate":
                growth_rate
        }

        for discount_rate in discount_rates:

            if (
                discount_rate
                <= terminal_growth_rate
            ):

                fair_value = None

            else:

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

            row[
                discount_rate
            ] = fair_value

        results.append(
            row
        )

    return {

        "Ticker":
            ticker.upper(),

        "Terminal Growth":
            terminal_growth_rate,

        "Years":
            years,

        "Growth Rates":
            growth_rates,

        "Discount Rates":
            discount_rates,

        "Results":
            results
    }


# =========================================================
# Reverse DCF
# =========================================================

def calculate_implied_growth_rate(
    ticker,
    target_price=None,
    discount_rate=None,
    terminal_growth_rate=DEFAULT_TERMINAL_GROWTH,
    years=DEFAULT_YEARS,
    lower_growth=-0.20,
    upper_growth=1.00,
    tolerance=0.0001,
    max_iterations=200,
    inputs=None
):

    # =====================================================
    # Prepare expensive inputs ONCE
    # =====================================================

    if inputs is None:

        inputs = (
            prepare_dcf_inputs(
                ticker
            )
        )

    # =====================================================
    # Target Price
    # =====================================================

    if target_price is None:

        target_price = (
            inputs.get(
                "Current Price"
            )
        )

    # =====================================================
    # WACC
    # =====================================================

    if discount_rate is None:

        discount_rate = (
            inputs.get(
                "WACC"
            )
        )

    if (
        target_price is None
        or discount_rate is None
    ):
        return None

    if (
        discount_rate
        <= terminal_growth_rate
    ):
        return None

    # =====================================================
    # Pure DCF Price Difference
    # =====================================================

    def price_difference(
        growth_rate
    ):

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

        if fair_value is None:
            return None

        return (
            fair_value
            - target_price
        )

    # =====================================================
    # Search Bounds
    # =====================================================

    lower_difference = (
        price_difference(
            lower_growth
        )
    )

    upper_difference = (
        price_difference(
            upper_growth
        )
    )

    if (
        lower_difference is None
        or upper_difference is None
    ):
        return None

    if (
        lower_difference
        * upper_difference
        > 0
    ):

        return {

            "Status":
                "Outside Search Range",

            "Target Price":
                target_price,

            "Discount Rate":
                discount_rate,

            "Terminal Growth":
                terminal_growth_rate,

            "Implied Growth":
                None,

            "Lower Search Bound":
                lower_growth,

            "Upper Search Bound":
                upper_growth
        }

    # =====================================================
    # Bisection Search
    # =====================================================

    low = lower_growth
    high = upper_growth

    implied_growth = None
    implied_fair_value = None

    for _ in range(
        max_iterations
    ):

        midpoint = (
            low
            + high
        ) / 2

        fair_value = (
            calculate_dcf_fair_value(
                ticker=ticker,
                growth_rate=midpoint,
                discount_rate=discount_rate,
                terminal_growth_rate=(
                    terminal_growth_rate
                ),
                years=years,
                inputs=inputs
            )
        )

        if fair_value is None:
            return None

        difference = (
            fair_value
            - target_price
        )

        if abs(
            difference
        ) <= 0.01:

            implied_growth = midpoint
            implied_fair_value = fair_value

            break

        if difference > 0:

            high = midpoint

        else:

            low = midpoint

        if (
            high
            - low
        ) < tolerance:

            implied_growth = midpoint
            implied_fair_value = fair_value

            break

    if implied_growth is None:

        implied_growth = (
            low
            + high
        ) / 2

        implied_fair_value = (
            calculate_dcf_fair_value(
                ticker=ticker,
                growth_rate=implied_growth,
                discount_rate=discount_rate,
                terminal_growth_rate=(
                    terminal_growth_rate
                ),
                years=years,
                inputs=inputs
            )
        )

    return {

        "Status":
            "Solved",

        "Target Price":
            target_price,

        "Discount Rate":
            discount_rate,

        "Terminal Growth":
            terminal_growth_rate,

        "Implied Growth":
            implied_growth,

        "Implied Fair Value":
            implied_fair_value,

        "Years":
            years
    }


# =========================================================
# Market Expectation Classification
# =========================================================

def classify_implied_growth(
    implied_growth
):

    if implied_growth is None:

        return "Unknown"

    if implied_growth < 0.05:

        return "Low"

    if implied_growth < 0.10:

        return "Moderate"

    if implied_growth < 0.15:

        return "Elevated"

    if implied_growth < 0.25:

        return "Aggressive"

    return "Very Aggressive"


# =========================================================
# Market Expectation Summary
# =========================================================

def get_market_expectation_summary(
    ticker,
    inputs=None
):

    # =====================================================
    # Prepare DCF inputs ONCE
    # =====================================================

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

    wacc = (
        inputs.get(
            "WACC"
        )
    )

    if wacc is None:

        return {

            "Ticker":
                ticker.upper(),

            "Current Price":
                current_price,

            "Base DCF Fair Value":
                None,

            "Market Premium vs Base DCF":
                None,

            "WACC":
                None,

            "Terminal Growth":
                DEFAULT_TERMINAL_GROWTH,

            "Implied Growth":
                None,

            "Expectation Level":
                "Unknown",

            "Reverse DCF Status":
                "Unavailable"
        }

    # =====================================================
    # Base DCF
    # =====================================================

    base_fair_value = (
        calculate_dcf_fair_value(
            ticker=ticker,
            growth_rate=0.07,
            discount_rate=wacc,
            terminal_growth_rate=(
                DEFAULT_TERMINAL_GROWTH
            ),
            years=DEFAULT_YEARS,
            inputs=inputs
        )
    )

    # =====================================================
    # Reverse DCF
    # =====================================================

    reverse_dcf = (
        calculate_implied_growth_rate(
            ticker=ticker,
            target_price=current_price,
            discount_rate=wacc,
            terminal_growth_rate=(
                DEFAULT_TERMINAL_GROWTH
            ),
            years=DEFAULT_YEARS,
            inputs=inputs
        )
    )

    implied_growth = None

    if reverse_dcf:

        implied_growth = (
            reverse_dcf.get(
                "Implied Growth"
            )
        )

    expectation_level = (
        classify_implied_growth(
            implied_growth
        )
    )

    # =====================================================
    # Market Premium
    # =====================================================

    valuation_gap = None

    if (
        base_fair_value is not None
        and current_price is not None
        and base_fair_value != 0
    ):

        valuation_gap = (
            current_price
            / base_fair_value
            - 1
        )

    return {

        "Ticker":
            ticker.upper(),

        "Current Price":
            current_price,

        "Base DCF Fair Value":
            base_fair_value,

        "Market Premium vs Base DCF":
            valuation_gap,

        "WACC":
            wacc,

        "Terminal Growth":
            DEFAULT_TERMINAL_GROWTH,

        "Implied Growth":
            implied_growth,

        "Expectation Level":
            expectation_level,

        "Reverse DCF Status":
            (
                reverse_dcf.get(
                    "Status"
                )
                if reverse_dcf
                else "Unavailable"
            )
    }


# =========================================================
# Sensitivity Printer
# =========================================================

def print_sensitivity_table(
    sensitivity
):

    if not sensitivity:

        print(
            "Sensitivity analysis unavailable."
        )

        return

    discount_rates = (
        sensitivity[
            "Discount Rates"
        ]
    )

    print("\n==============================")
    print("DCF SENSITIVITY TABLE")
    print("==============================")

    header = (
        "Growth"
        .ljust(
            10
        )
    )

    for rate in discount_rates:

        header += (
            f"{rate:.2%}"
            .rjust(
                14
            )
        )

    print(
        header
    )

    print(
        "-" * len(
            header
        )
    )

    for row in (
        sensitivity[
            "Results"
        ]
    ):

        line = (
            f"{row['Growth Rate']:.2%}"
            .ljust(
                10
            )
        )

        for rate in discount_rates:

            value = (
                row[
                    rate
                ]
            )

            if value is None:

                cell = "N/A"

            else:

                cell = (
                    f"${value:,.2f}"
                )

            line += (
                cell.rjust(
                    14
                )
            )

        print(
            line
        )


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "AAPL"

    inputs = (
        prepare_dcf_inputs(
            ticker
        )
    )

    reverse_dcf = (
        calculate_implied_growth_rate(
            ticker,
            inputs=inputs
        )
    )

    print("\n==============================")
    print("REVERSE DCF")
    print("==============================")

    print(
        reverse_dcf
    )

    summary = (
        get_market_expectation_summary(
            ticker,
            inputs=inputs
        )
    )

    print("\n==============================")
    print("MARKET EXPECTATION SUMMARY")
    print("==============================")

    print(
        "Current Price: "
        f"{format_money(summary['Current Price'])}"
    )

    print(
        "Base DCF Fair Value: "
        f"{format_money(summary['Base DCF Fair Value'])}"
    )

    print(
        "Implied FCFF Growth: "
        f"{format_percentage(summary['Implied Growth'])}"
    )

    print(
        "Expectation Level: "
        f"{summary['Expectation Level']}"
    )