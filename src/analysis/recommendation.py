import time

from src.analysis.rating import (
    get_research_components,
    calculate_research_score_from_components
)


# =========================================================
# Recommendation Thresholds
# =========================================================

RECOMMENDATION_THRESHOLDS = {

    "strong_downside":
        -0.25,

    "sell":
        -0.10,

    "buy":
        0.10,

    "strong_upside":
        0.25
}


# =========================================================
# Conviction Rules
# =========================================================

CONVICTION_RULES = {

    "buy_min_fundamental_score":
        75,

    "buy_min_quality_score":
        70,

    "sell_max_fundamental_score":
        50,

    "sell_max_quality_score":
        55
}


# =========================================================
# Formatting Helpers
# =========================================================

def format_percentage(value):

    if value is None:
        return "N/A"

    return (
        f"{value:.2%}"
    )


def format_score(value):

    if value is None:
        return "N/A"

    return (
        f"{value:.2f}"
    )


def format_money(value):

    if value is None:
        return "N/A"

    return (
        f"${value:,.2f}"
    )


# =========================================================
# Base Direction
# =========================================================

def classify_base_direction(
    expected_return
):

    if expected_return is None:

        return {
            "direction":
                "Neutral",

            "conviction_candidate":
                False,

            "reason":
                "Expected return unavailable."
        }

    if (
        expected_return
        <= RECOMMENDATION_THRESHOLDS[
            "strong_downside"
        ]
    ):

        return {
            "direction":
                "Sell",

            "conviction_candidate":
                True,

            "reason":
                "Central valuation indicates substantial downside."
        }

    if (
        expected_return
        < RECOMMENDATION_THRESHOLDS[
            "sell"
        ]
    ):

        return {
            "direction":
                "Sell",

            "conviction_candidate":
                False,

            "reason":
                "Central valuation indicates downside."
        }

    if (
        expected_return
        < RECOMMENDATION_THRESHOLDS[
            "buy"
        ]
    ):

        return {
            "direction":
                "Neutral",

            "conviction_candidate":
                False,

            "reason":
                "Central valuation is broadly near market price."
        }

    if (
        expected_return
        < RECOMMENDATION_THRESHOLDS[
            "strong_upside"
        ]
    ):

        return {
            "direction":
                "Buy",

            "conviction_candidate":
                False,

            "reason":
                "Central valuation indicates upside."
        }

    return {
        "direction":
            "Buy",

        "conviction_candidate":
            True,

        "reason":
            "Central valuation indicates substantial upside."
    }


# =========================================================
# Conviction Buy Gate
# =========================================================

def check_conviction_buy(
    fundamental_score,
    quality_score,
    valuation_confidence,
    expectation_risk
):

    conditions = {

        "Fundamental Strength":
            (
                fundamental_score is not None
                and fundamental_score
                >= CONVICTION_RULES[
                    "buy_min_fundamental_score"
                ]
            ),

        "Earnings Quality":
            (
                quality_score is not None
                and quality_score
                >= CONVICTION_RULES[
                    "buy_min_quality_score"
                ]
            ),

        "Valuation Confidence":
            (
                valuation_confidence
                == "High"
            ),

        "Expectation Risk":
            (
                expectation_risk
                not in [
                    "Very High",
                    "Unknown"
                ]
            )
    }

    return {
        "passed":
            all(
                conditions.values()
            ),

        "conditions":
            conditions
    }


# =========================================================
# Conviction Sell Gate
# =========================================================

def check_conviction_sell(
    fundamental_score,
    quality_score,
    valuation_confidence
):

    weak_fundamentals = (
        fundamental_score is not None
        and fundamental_score
        <= CONVICTION_RULES[
            "sell_max_fundamental_score"
        ]
    )

    weak_quality = (
        quality_score is not None
        and quality_score
        <= CONVICTION_RULES[
            "sell_max_quality_score"
        ]
    )

    conditions = {

        "Valuation Confidence":
            (
                valuation_confidence
                == "High"
            ),

        "Fundamental Weakness":
            (
                weak_fundamentals
                or weak_quality
            )
    }

    return {
        "passed":
            all(
                conditions.values()
            ),

        "conditions":
            conditions
    }


# =========================================================
# Final Recommendation Logic
# =========================================================

def determine_recommendation(
    expected_return,
    fundamental_score,
    quality_score,
    valuation_confidence,
    expectation_risk
):

    base = (
        classify_base_direction(
            expected_return
        )
    )

    direction = (
        base[
            "direction"
        ]
    )

    conviction_candidate = (
        base[
            "conviction_candidate"
        ]
    )

    # -----------------------------------------------------
    # Neutral
    # -----------------------------------------------------

    if direction == "Neutral":

        return {
            "recommendation":
                "Neutral",

            "base_direction":
                "Neutral",

            "conviction":
                False,

            "conviction_gate":
                None
        }

    # -----------------------------------------------------
    # Buy
    # -----------------------------------------------------

    if direction == "Buy":

        if not conviction_candidate:

            return {
                "recommendation":
                    "Buy",

                "base_direction":
                    "Buy",

                "conviction":
                    False,

                "conviction_gate":
                    None
            }

        gate = (
            check_conviction_buy(
                fundamental_score=(
                    fundamental_score
                ),
                quality_score=(
                    quality_score
                ),
                valuation_confidence=(
                    valuation_confidence
                ),
                expectation_risk=(
                    expectation_risk
                )
            )
        )

        if gate[
            "passed"
        ]:

            recommendation = (
                "Conviction Buy"
            )

            conviction = True

        else:

            recommendation = (
                "Buy"
            )

            conviction = False

        return {
            "recommendation":
                recommendation,

            "base_direction":
                "Buy",

            "conviction":
                conviction,

            "conviction_gate":
                gate
        }

    # -----------------------------------------------------
    # Sell
    # -----------------------------------------------------

    if direction == "Sell":

        if not conviction_candidate:

            return {
                "recommendation":
                    "Sell",

                "base_direction":
                    "Sell",

                "conviction":
                    False,

                "conviction_gate":
                    None
            }

        gate = (
            check_conviction_sell(
                fundamental_score=(
                    fundamental_score
                ),
                quality_score=(
                    quality_score
                ),
                valuation_confidence=(
                    valuation_confidence
                )
            )
        )

        if gate[
            "passed"
        ]:

            recommendation = (
                "Conviction Sell"
            )

            conviction = True

        else:

            recommendation = (
                "Sell"
            )

            conviction = False

        return {
            "recommendation":
                recommendation,

            "base_direction":
                "Sell",

            "conviction":
                conviction,

            "conviction_gate":
                gate
        }

    return {
        "recommendation":
            "Neutral",

        "base_direction":
            "Neutral",

        "conviction":
            False,

        "conviction_gate":
            None
    }


# =========================================================
# Recommendation Explanation
# =========================================================

def generate_recommendation_explanation(
    expected_return,
    fundamental_score,
    research_score,
    quality_score,
    valuation_confidence,
    expectation_level,
    expectation_risk
):

    reasons = []

    # -----------------------------------------------------
    # Valuation Direction
    # -----------------------------------------------------

    if expected_return is not None:

        if expected_return <= -0.25:

            reasons.append(
                "Central valuation indicates substantial downside."
            )

        elif expected_return < -0.10:

            reasons.append(
                "Central valuation indicates moderate downside."
            )

        elif expected_return < 0.10:

            reasons.append(
                "Central valuation is broadly near market price."
            )

        elif expected_return < 0.25:

            reasons.append(
                "Central valuation indicates moderate upside."
            )

        else:

            reasons.append(
                "Central valuation indicates substantial upside."
            )

    # -----------------------------------------------------
    # Fundamental Strength
    # -----------------------------------------------------

    if fundamental_score is not None:

        if fundamental_score >= 75:

            reasons.append(
                "Underlying fundamentals are strong."
            )

        elif fundamental_score >= 65:

            reasons.append(
                "Underlying fundamentals remain relatively solid."
            )

        elif fundamental_score < 50:

            reasons.append(
                "Underlying fundamental strength is weak."
            )

    # -----------------------------------------------------
    # Earnings Quality
    # -----------------------------------------------------

    if quality_score is not None:

        if quality_score >= 70:

            reasons.append(
                "Earnings quality remains relatively strong."
            )

        elif quality_score < 55:

            reasons.append(
                "Earnings quality is weak."
            )

    # -----------------------------------------------------
    # Research Profile
    # -----------------------------------------------------

    if research_score is not None:

        if research_score >= 75:

            reasons.append(
                "The overall research profile is strong."
            )

        elif research_score < 55:

            reasons.append(
                "The overall research profile is currently weak."
            )

    # -----------------------------------------------------
    # Valuation Confidence
    # -----------------------------------------------------

    if valuation_confidence == "Low":

        reasons.append(
            "Conviction is limited by low valuation confidence."
        )

    elif valuation_confidence == "Medium":

        reasons.append(
            "Valuation confidence is moderate."
        )

    elif valuation_confidence == "High":

        reasons.append(
            "Valuation methods show relatively strong agreement."
        )

    # -----------------------------------------------------
    # Market Expectations
    # -----------------------------------------------------

    if expectation_level == "Very Aggressive":

        reasons.append(
            "The current market price requires very aggressive "
            "cash-flow growth assumptions under the DCF framework."
        )

    elif expectation_level == "Aggressive":

        reasons.append(
            "The current market price requires aggressive "
            "future growth assumptions."
        )

    elif expectation_level == "Elevated":

        reasons.append(
            "Market expectations appear elevated."
        )

    if expectation_risk == "Very High":

        reasons.append(
            "Market expectation risk is very high."
        )

    elif expectation_risk == "High":

        reasons.append(
            "Market expectation risk is high."
        )

    return " ".join(
        reasons
    )


# =========================================================
# Main Recommendation Engine
# =========================================================

def analyze_recommendation(ticker, peer_tickers):
    from src.services.rating_service import build_recommendation
    return build_recommendation(ticker, peer_tickers, get_research_components,
                                calculate_research_score_from_components)


# =========================================================
# Pretty Print
# =========================================================

def print_recommendation_report(
    report
):

    print("\n==============================")
    print("INVESTMENT RECOMMENDATION")
    print("==============================")

    print(
        f"\nTicker: "
        f"{report['Ticker']}"
    )

    print(
        "Recommendation: "
        f"{report['Recommendation']}"
    )

    print(
        "Base Direction: "
        f"{report['Base Direction']}"
    )

    print(
        "Conviction: "
        f"{report['Conviction']}"
    )

    print("\n==============================")
    print("BUSINESS QUALITY")
    print("==============================")

    print(
        "Fundamental Score: "
        f"{format_score(report['Fundamental Score'])}"
    )

    print(
        "Earnings Quality: "
        f"{format_score(report['Earnings Quality'])}"
    )

    print("\n==============================")
    print("RESEARCH PROFILE")
    print("==============================")

    print(
        "Research Score: "
        f"{format_score(report['Research Score'])}"
    )

    print("\n==============================")
    print("VALUATION")
    print("==============================")

    print(
        "Current Price: "
        f"{format_money(report['Current Price'])}"
    )

    print(
        "Fair Value Low: "
        f"{format_money(report['Fair Value Low'])}"
    )

    print(
        "Fair Value Base: "
        f"{format_money(report['Fair Value Base'])}"
    )

    print(
        "Fair Value High: "
        f"{format_money(report['Fair Value High'])}"
    )

    print(
        "Expected Return: "
        f"{format_percentage(report['Expected Return'])}"
    )

    print(
        "Valuation Confidence: "
        f"{report['Valuation Confidence']}"
    )

    print("\n==============================")
    print("MARKET EXPECTATIONS")
    print("==============================")

    print(
        "Implied 5Y FCFF Growth: "
        f"{format_percentage(report['Implied FCFF Growth'])}"
    )

    print(
        "Expectation Level: "
        f"{report['Expectation Level']}"
    )

    print(
        "Expectation Risk: "
        f"{report['Expectation Risk']}"
    )

    print(
        "Market Premium vs Base DCF: "
        f"{format_percentage(report['Market Premium vs Base DCF'])}"
    )

    gate = (
        report[
            "Conviction Gate"
        ]
    )

    if gate is not None:

        print("\n==============================")
        print("CONVICTION GATE")
        print("==============================")

        for condition, passed in (
            gate[
                "conditions"
            ].items()
        ):

            status = (
                "PASS"
                if passed
                else "FAIL"
            )

            print(
                f"{condition}: "
                f"{status}"
            )

    print("\n==============================")
    print("INTERPRETATION")
    print("==============================")

    print(
        report[
            "Explanation"
        ]
    )

    print(
        "\nImportant:"
    )

    print(
        "Recommendation is a model output, "
        "not a statement of certainty."
    )

    print(
        "Market price and intrinsic value "
        "may diverge materially."
    )

    print(
        "Conviction requires stronger evidence "
        "than valuation direction alone."
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

    report = (
        analyze_recommendation(
            ticker=ticker,
            peer_tickers=peers
        )
    )

    print_recommendation_report(
        report
    )
