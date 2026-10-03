from src.data.reuse import scoped
import time
import math

from src.data.market_data import (
    get_current_price
)

from src.models.valuation_model import (
    calculate_historical_fair_value,
    calculate_peer_fair_value
)

from src.models.dcf_model import (
    get_dcf_scenarios
)

from src.models.dcf_analysis import (
    get_market_expectation_summary
)


# =========================================================
# Valuation Family Weights
# =========================================================

VALUATION_FAMILY_WEIGHTS = {
    "Relative": 0.50,
    "Intrinsic": 0.50
}


# =========================================================
# Helpers
# =========================================================

def is_valid_number(value):

    return (
        value is not None
        and isinstance(
            value,
            (int, float)
        )
        and math.isfinite(
            value
        )
    )


def clean_values(values):

    return [
        value
        for value in values
        if (
            is_valid_number(value)
            and value > 0
        )
    ]


def safe_average(values):

    values = clean_values(
        values
    )

    if not values:
        return None

    return (
        sum(values)
        / len(values)
    )


def safe_min(values):

    values = clean_values(
        values
    )

    if not values:
        return None

    return min(
        values
    )


def safe_max(values):

    values = clean_values(
        values
    )

    if not values:
        return None

    return max(
        values
    )


def calculate_expected_return(
    fair_value,
    current_price
):

    if (
        fair_value is None
        or current_price is None
        or current_price == 0
    ):
        return None

    return (
        fair_value
        - current_price
    ) / current_price


# =========================================================
# Relative Valuation Family
# =========================================================

def get_relative_family(
    ticker,
    peer_tickers
):

    historical_fair_value = None
    peer_fair_value = None

    # -----------------------------------------------------
    # Historical
    # -----------------------------------------------------

    historical_start = (
        time.perf_counter()
    )

    try:

        historical_fair_value = (
            calculate_historical_fair_value(
                ticker
            )
        )

    except Exception as error:

        print(
            "Historical valuation failed: "
            f"{error}"
        )

    historical_elapsed = (
        time.perf_counter()
        - historical_start
    )

    print(
        "[VALUATION PROFILE] Historical Fair Value : "
        f"{historical_elapsed:.3f}s"
    )

    # -----------------------------------------------------
    # Peer
    # -----------------------------------------------------

    peer_start = (
        time.perf_counter()
    )

    try:

        peer_fair_value = (
            calculate_peer_fair_value(
                ticker,
                peer_tickers
            )
        )

    except Exception as error:

        print(
            "Peer valuation failed: "
            f"{error}"
        )

    peer_elapsed = (
        time.perf_counter()
        - peer_start
    )

    print(
        "[VALUATION PROFILE] Peer Fair Value       : "
        f"{peer_elapsed:.3f}s"
    )

    # -----------------------------------------------------
    # Relative Family Value
    # -----------------------------------------------------

    relative_fair_value = (
        safe_average(
            [
                historical_fair_value,
                peer_fair_value
            ]
        )
    )

    return {

        "historical_fair_value":
            historical_fair_value,

        "peer_fair_value":
            peer_fair_value,

        "family_fair_value":
            relative_fair_value
    }


# =========================================================
# Intrinsic / DCF Family
# =========================================================

def get_intrinsic_family(
    ticker
):

    dcf_start = (
        time.perf_counter()
    )

    try:

        scenarios = (
            get_dcf_scenarios(
                ticker
            )
        )

    except Exception as error:

        print(
            "DCF analysis failed: "
            f"{error}"
        )

        scenarios = None

    dcf_elapsed = (
        time.perf_counter()
        - dcf_start
    )

    print(
        "[VALUATION PROFILE] DCF Scenarios          : "
        f"{dcf_elapsed:.3f}s"
    )

    if not scenarios:

        return {

            "bear":
                None,

            "base":
                None,

            "bull":
                None,

            "family_fair_value":
                None,

            "raw_scenarios":
                None
        }

    def get_scenario_value(name):

        scenario = (
            scenarios.get(
                name
            )
        )

        if not scenario:
            return None

        return (
            scenario.get(
                "Fair Value"
            )
        )

    bear = (
        get_scenario_value(
            "Bear"
        )
    )

    base = (
        get_scenario_value(
            "Base"
        )
    )

    bull = (
        get_scenario_value(
            "Bull"
        )
    )

    return {

        "bear":
            bear,

        "base":
            base,

        "bull":
            bull,

        "family_fair_value":
            base,

        "raw_scenarios":
            scenarios
    }


# =========================================================
# Weighted Family Fair Value
# =========================================================

def calculate_weighted_family_value(
    relative_value,
    intrinsic_value
):

    families = {

        "Relative": {
            "value":
                relative_value,

            "weight":
                VALUATION_FAMILY_WEIGHTS[
                    "Relative"
                ]
        },

        "Intrinsic": {
            "value":
                intrinsic_value,

            "weight":
                VALUATION_FAMILY_WEIGHTS[
                    "Intrinsic"
                ]
        }
    }

    weighted_total = 0
    available_weight = 0

    for family in (
        families.values()
    ):

        value = (
            family[
                "value"
            ]
        )

        weight = (
            family[
                "weight"
            ]
        )

        if not is_valid_number(
            value
        ):
            continue

        weighted_total += (
            value
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
# Relative Internal Spread
# =========================================================

def calculate_relative_internal_spread(
    historical_value,
    peer_value
):

    values = (
        clean_values(
            [
                historical_value,
                peer_value
            ]
        )
    )

    if len(values) < 2:
        return None

    average_value = (
        sum(values)
        / len(values)
    )

    if average_value == 0:
        return None

    return (
        abs(
            values[0]
            - values[1]
        )
        / average_value
    )


# =========================================================
# Family Spread
# =========================================================

def calculate_family_spread(
    relative_value,
    intrinsic_value
):

    values = (
        clean_values(
            [
                relative_value,
                intrinsic_value
            ]
        )
    )

    if len(values) < 2:
        return None

    average_value = (
        sum(values)
        / len(values)
    )

    if average_value == 0:
        return None

    return (
        abs(
            values[0]
            - values[1]
        )
        / average_value
    )


# =========================================================
# DCF Scenario Spread
# =========================================================

def calculate_dcf_scenario_spread(
    bear,
    base,
    bull
):

    if (
        not is_valid_number(
            bear
        )
        or not is_valid_number(
            base
        )
        or not is_valid_number(
            bull
        )
        or base == 0
    ):
        return None

    return (
        bull
        - bear
    ) / base


# =========================================================
# Valuation Confidence
# =========================================================

def classify_valuation_confidence(
    family_spread,
    relative_spread,
    dcf_spread
):

    if family_spread is None:
        return "Low"

    if (
        family_spread <= 0.20
        and (
            relative_spread is None
            or relative_spread <= 0.20
        )
        and (
            dcf_spread is None
            or dcf_spread <= 0.40
        )
    ):
        return "High"

    if (
        family_spread <= 0.40
        and (
            relative_spread is None
            or relative_spread <= 0.35
        )
        and (
            dcf_spread is None
            or dcf_spread <= 0.75
        )
    ):
        return "Medium"

    return "Low"


# =========================================================
# Market Expectation Risk
# =========================================================

def classify_expectation_risk(
    expectation_level
):

    mapping = {

        "Low":
            "Low",

        "Moderate":
            "Low",

        "Elevated":
            "Moderate",

        "Aggressive":
            "High",

        "Very Aggressive":
            "Very High",

        "Unknown":
            "Unknown"
    }

    return (
        mapping.get(
            expectation_level,
            "Unknown"
        )
    )


# =========================================================
# Valuation Interpretation
# =========================================================

def generate_valuation_interpretation(
    expected_return,
    valuation_confidence,
    expectation_level
):

    observations = []

    if expected_return is None:

        observations.append(
            "Central fair value is unavailable."
        )

    elif expected_return >= 0.25:

        observations.append(
            "Central valuation indicates substantial upside."
        )

    elif expected_return >= 0.10:

        observations.append(
            "Central valuation indicates moderate upside."
        )

    elif expected_return > -0.10:

        observations.append(
            "Central valuation is broadly near market price."
        )

    elif expected_return > -0.25:

        observations.append(
            "Central valuation indicates moderate downside."
        )

    else:

        observations.append(
            "Central valuation indicates substantial downside."
        )

    if valuation_confidence == "Low":

        observations.append(
            "Valuation methods show significant disagreement "
            "or sensitivity."
        )

    elif valuation_confidence == "Medium":

        observations.append(
            "Valuation methods show moderate agreement."
        )

    elif valuation_confidence == "High":

        observations.append(
            "Valuation methods show relatively strong agreement."
        )

    if expectation_level == "Very Aggressive":

        observations.append(
            "Current market price implies very demanding "
            "future cash-flow growth assumptions."
        )

    elif expectation_level == "Aggressive":

        observations.append(
            "Current market price implies demanding "
            "future growth assumptions."
        )

    elif expectation_level == "Elevated":

        observations.append(
            "Market expectations appear elevated "
            "relative to the base DCF framework."
        )

    return " ".join(
        observations
    )


# =========================================================
# Main Valuation Engine
# =========================================================

@scoped
def analyze_valuation(
    ticker,
    peer_tickers
):

    total_start = (
        time.perf_counter()
    )

    ticker = (
        ticker
        .upper()
        .strip()
    )

    print("\n")
    print("=" * 60)

    print(
        f"[VALUATION PROFILE] ANALYZE VALUATION: "
        f"{ticker}"
    )

    print("=" * 60)

    # =====================================================
    # Current Price
    # =====================================================

    price_start = (
        time.perf_counter()
    )

    current_price = (
        get_current_price(
            ticker
        )
    )

    price_elapsed = (
        time.perf_counter()
        - price_start
    )

    print(
        "[VALUATION PROFILE] Current Price         : "
        f"{price_elapsed:.3f}s"
    )

    # =====================================================
    # Relative Family
    # =====================================================

    relative_start = (
        time.perf_counter()
    )

    relative = (
        get_relative_family(
            ticker,
            peer_tickers
        )
    )

    relative_elapsed = (
        time.perf_counter()
        - relative_start
    )

    print(
        "[VALUATION PROFILE] Relative Family       : "
        f"{relative_elapsed:.3f}s"
    )

    historical_fair_value = (
        relative[
            "historical_fair_value"
        ]
    )

    peer_fair_value = (
        relative[
            "peer_fair_value"
        ]
    )

    relative_fair_value = (
        relative[
            "family_fair_value"
        ]
    )

    # =====================================================
    # Intrinsic Family
    # =====================================================

    intrinsic_start = (
        time.perf_counter()
    )

    intrinsic = (
        get_intrinsic_family(
            ticker
        )
    )

    intrinsic_elapsed = (
        time.perf_counter()
        - intrinsic_start
    )

    print(
        "[VALUATION PROFILE] Intrinsic Family      : "
        f"{intrinsic_elapsed:.3f}s"
    )

    dcf_bear = (
        intrinsic[
            "bear"
        ]
    )

    dcf_base = (
        intrinsic[
            "base"
        ]
    )

    dcf_bull = (
        intrinsic[
            "bull"
        ]
    )

    intrinsic_fair_value = (
        intrinsic[
            "family_fair_value"
        ]
    )

    # =====================================================
    # Local Math
    # =====================================================

    local_math_start = (
        time.perf_counter()
    )

    fair_value_base = (
        calculate_weighted_family_value(
            relative_value=(
                relative_fair_value
            ),
            intrinsic_value=(
                intrinsic_fair_value
            )
        )
    )

    range_values = [
        historical_fair_value,
        peer_fair_value,
        dcf_bear,
        dcf_base,
        dcf_bull
    ]

    fair_value_low = (
        safe_min(
            range_values
        )
    )

    fair_value_high = (
        safe_max(
            range_values
        )
    )

    expected_return_low = (
        calculate_expected_return(
            fair_value_low,
            current_price
        )
    )

    expected_return_base = (
        calculate_expected_return(
            fair_value_base,
            current_price
        )
    )

    expected_return_high = (
        calculate_expected_return(
            fair_value_high,
            current_price
        )
    )

    family_spread = (
        calculate_family_spread(
            relative_value=(
                relative_fair_value
            ),
            intrinsic_value=(
                intrinsic_fair_value
            )
        )
    )

    relative_spread = (
        calculate_relative_internal_spread(
            historical_value=(
                historical_fair_value
            ),
            peer_value=(
                peer_fair_value
            )
        )
    )

    dcf_spread = (
        calculate_dcf_scenario_spread(
            bear=(
                dcf_bear
            ),
            base=(
                dcf_base
            ),
            bull=(
                dcf_bull
            )
        )
    )

    valuation_confidence = (
        classify_valuation_confidence(
            family_spread=(
                family_spread
            ),
            relative_spread=(
                relative_spread
            ),
            dcf_spread=(
                dcf_spread
            )
        )
    )

    local_math_elapsed = (
        time.perf_counter()
        - local_math_start
    )

    print(
        "[VALUATION PROFILE] Local Math            : "
        f"{local_math_elapsed:.6f}s"
    )

    # =====================================================
    # Market Expectations
    # =====================================================

    expectation_start = (
        time.perf_counter()
    )

    market_expectation = {}

    try:

        market_expectation = (
            get_market_expectation_summary(
                ticker
            )
        )

    except Exception as error:

        print(
            "Market expectation analysis failed: "
            f"{error}"
        )

        market_expectation = {}

    expectation_elapsed = (
        time.perf_counter()
        - expectation_start
    )

    print(
        "[VALUATION PROFILE] Market Expectation    : "
        f"{expectation_elapsed:.3f}s"
    )

    implied_growth = (
        market_expectation.get(
            "Implied Growth"
        )
    )

    expectation_level = (
        market_expectation.get(
            "Expectation Level",
            "Unknown"
        )
    )

    market_premium_vs_dcf = (
        market_expectation.get(
            "Market Premium vs Base DCF"
        )
    )

    expectation_risk = (
        classify_expectation_risk(
            expectation_level
        )
    )

    # =====================================================
    # Final Processing
    # =====================================================

    final_start = (
        time.perf_counter()
    )

    family_count = sum(
        is_valid_number(
            value
        )
        for value in [
            relative_fair_value,
            intrinsic_fair_value
        ]
    )

    interpretation = (
        generate_valuation_interpretation(
            expected_return=(
                expected_return_base
            ),
            valuation_confidence=(
                valuation_confidence
            ),
            expectation_level=(
                expectation_level
            )
        )
    )

    final_elapsed = (
        time.perf_counter()
        - final_start
    )

    print(
        "[VALUATION PROFILE] Final Processing      : "
        f"{final_elapsed:.6f}s"
    )

    # =====================================================
    # Output
    # =====================================================

    report = {

        "ticker":
            ticker,

        "current_price":
            current_price,

        # -------------------------------------------------
        # Relative Family
        # -------------------------------------------------

        "historical_fair_value":
            historical_fair_value,

        "peer_fair_value":
            peer_fair_value,

        "relative_fair_value":
            relative_fair_value,

        "relative_family_weight":
            VALUATION_FAMILY_WEIGHTS[
                "Relative"
            ],

        # -------------------------------------------------
        # Intrinsic Family
        # -------------------------------------------------

        "dcf_bear":
            dcf_bear,

        "dcf_base":
            dcf_base,

        "dcf_bull":
            dcf_bull,

        "intrinsic_fair_value":
            intrinsic_fair_value,

        "intrinsic_family_weight":
            VALUATION_FAMILY_WEIGHTS[
                "Intrinsic"
            ],

        # -------------------------------------------------
        # Fair Value
        # -------------------------------------------------

        "fair_value_low":
            fair_value_low,

        "fair_value_base":
            fair_value_base,

        "fair_value_high":
            fair_value_high,

        # -------------------------------------------------
        # Expected Return
        # -------------------------------------------------

        "expected_return_low":
            expected_return_low,

        "expected_return_base":
            expected_return_base,

        "expected_return_high":
            expected_return_high,

        # -------------------------------------------------
        # Agreement / Confidence
        # -------------------------------------------------

        "family_count":
            family_count,

        "family_spread":
            family_spread,

        "relative_internal_spread":
            relative_spread,

        "dcf_scenario_spread":
            dcf_spread,

        "valuation_confidence":
            valuation_confidence,

        # -------------------------------------------------
        # Market Expectations
        # -------------------------------------------------

        "implied_fcff_growth":
            implied_growth,

        "expectation_level":
            expectation_level,

        "expectation_risk":
            expectation_risk,

        "market_premium_vs_base_dcf":
            market_premium_vs_dcf,

        # -------------------------------------------------
        # Interpretation
        # -------------------------------------------------

        "interpretation":
            interpretation,

        # -------------------------------------------------
        # Raw Details
        # -------------------------------------------------

        "dcf_scenarios":
            intrinsic[
                "raw_scenarios"
            ],

        "market_expectation_detail":
            market_expectation
    }

    # =====================================================
    # TOTAL
    # =====================================================

    total_elapsed = (
        time.perf_counter()
        - total_start
    )

    print("-" * 60)

    print(
        "[VALUATION PROFILE] TOTAL                 : "
        f"{total_elapsed:.3f}s"
    )

    print("=" * 60)
    print("\n")

    return report


# =========================================================
# Formatting
# =========================================================

def format_money(value):

    if value is None:
        return "N/A"

    return (
        f"${value:,.2f}"
    )


def format_percentage(value):

    if value is None:
        return "N/A"

    return (
        f"{value:.2%}"
    )


# =========================================================
# Pretty Print
# =========================================================

def print_valuation_report(
    report
):

    print("\n==============================")
    print("VALUATION ENGINE V2.2")
    print("==============================")

    print(
        f"\nTicker: "
        f"{report['ticker']}"
    )

    print(
        "Current Price: "
        f"{format_money(report['current_price'])}"
    )

    print("\n==============================")
    print("RELATIVE VALUATION")
    print("==============================")

    print(
        "Historical Fair Value: "
        f"{format_money(report['historical_fair_value'])}"
    )

    print(
        "Peer Fair Value: "
        f"{format_money(report['peer_fair_value'])}"
    )

    print(
        "Relative Family Fair Value: "
        f"{format_money(report['relative_fair_value'])}"
    )

    print(
        "Relative Weight: "
        f"{format_percentage(report['relative_family_weight'])}"
    )

    print("\n==============================")
    print("INTRINSIC / DCF VALUATION")
    print("==============================")

    print(
        "DCF Bear: "
        f"{format_money(report['dcf_bear'])}"
    )

    print(
        "DCF Base: "
        f"{format_money(report['dcf_base'])}"
    )

    print(
        "DCF Bull: "
        f"{format_money(report['dcf_bull'])}"
    )

    print(
        "Intrinsic Family Fair Value: "
        f"{format_money(report['intrinsic_fair_value'])}"
    )

    print(
        "Intrinsic Weight: "
        f"{format_percentage(report['intrinsic_family_weight'])}"
    )

    print("\n==============================")
    print("COMBINED FAIR VALUE")
    print("==============================")

    print(
        "Low: "
        f"{format_money(report['fair_value_low'])}"
    )

    print(
        "Base: "
        f"{format_money(report['fair_value_base'])}"
    )

    print(
        "High: "
        f"{format_money(report['fair_value_high'])}"
    )

    print(
        "\nExpected Return Low: "
        f"{format_percentage(report['expected_return_low'])}"
    )

    print(
        "Expected Return Base: "
        f"{format_percentage(report['expected_return_base'])}"
    )

    print(
        "Expected Return High: "
        f"{format_percentage(report['expected_return_high'])}"
    )

    print("\n==============================")
    print("MARKET EXPECTATIONS")
    print("==============================")

    print(
        "Implied 5Y FCFF Growth: "
        f"{format_percentage(report['implied_fcff_growth'])}"
    )

    print(
        "Expectation Level: "
        f"{report['expectation_level']}"
    )

    print(
        "Expectation Risk: "
        f"{report['expectation_risk']}"
    )

    print(
        "Market Premium vs Base DCF: "
        f"{format_percentage(report['market_premium_vs_base_dcf'])}"
    )

    print("\n==============================")
    print("VALUATION AGREEMENT")
    print("==============================")

    print(
        "Independent Families Available: "
        f"{report['family_count']}"
    )

    print(
        "Relative vs Intrinsic Spread: "
        f"{format_percentage(report['family_spread'])}"
    )

    print(
        "Relative Internal Spread: "
        f"{format_percentage(report['relative_internal_spread'])}"
    )

    print(
        "DCF Scenario Spread: "
        f"{format_percentage(report['dcf_scenario_spread'])}"
    )

    print(
        "Valuation Confidence: "
        f"{report['valuation_confidence']}"
    )

    print("\n==============================")
    print("VALUATION INTERPRETATION")
    print("==============================")

    print(
        report[
            "interpretation"
        ]
    )

    print(
        "\nImportant:"
    )

    print(
        "Market-implied expectations do not "
        "prove that a stock is rationally priced "
        "or in a bubble."
    )

    print(
        "They show what assumptions are required "
        "to reconcile market price with the "
        "intrinsic valuation framework."
    )


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
        f"VALUATION ENGINE TEST: "
        f"{ticker}"
    )
    print("==============================")

    report = (
        analyze_valuation(
            ticker=ticker,
            peer_tickers=peers
        )
    )

    print_valuation_report(
        report
    )