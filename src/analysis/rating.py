import time
import numpy as np

from src.analysis.fundamentals import (
    calculate_revenue_growth,
    calculate_net_income_growth,
    calculate_fcf_growth,
    calculate_debt_to_equity
)

from src.analysis.quality import (
    get_quality_summary
)

from src.models.valuation_engine import (
    analyze_valuation
)

from src.data.market_data import (
    get_price_history
)


# =========================================================
# FUNDAMENTAL SCORE WEIGHTS
# =========================================================
#
# Fundamental Score answers:
#
#     "How strong is the underlying business?"
#
# It deliberately excludes:
#
#     Valuation
#     Momentum
#
# because those are market / pricing factors,
# not operating fundamentals.
#
# CUSTOM research-model parameters.
#
# =========================================================

FUNDAMENTAL_WEIGHTS = {

    "Growth":
        0.35,

    "Quality":
        0.40,

    "Balance Sheet":
        0.25
}


# =========================================================
# FUNDAMENTAL RISK PENALTY
# =========================================================
#
# Historical share-price volatility is NOT
# pure business risk.
#
# Therefore volatility receives only a
# relatively small penalty in the
# Fundamental Score.
#
# =========================================================

FUNDAMENTAL_RISK_PENALTY_WEIGHT = 0.03


# =========================================================
# RESEARCH PROFILE WEIGHTS
# =========================================================
#
# Research Score answers:
#
#     "How attractive is the overall
#      research profile right now?"
#
# It combines:
#
#     Fundamental Score
#     Valuation
#     Momentum
#
# Valuation is included here for research
# ranking / screening purposes.
#
# IMPORTANT:
#
# Final Recommendation will NOT use a weak
# Research Score as proof of weak fundamentals.
#
# =========================================================

RESEARCH_PROFILE_WEIGHTS = {

    "Fundamental":
        0.55,

    "Valuation":
        0.30,

    "Momentum":
        0.15
}


# =========================================================
# Helper
# =========================================================

def clamp_score(value):
    """
    Keep score between 0 and 100.
    """

    return max(
        0,
        min(
            100,
            value
        )
    )


# =========================================================
# Growth Score
# =========================================================

def score_growth_rate(growth):
    """
    Convert growth rate into a
    0-100 research score.

    CUSTOM thresholds.
    """

    if growth is None:
        return None

    if growth >= 0.30:
        return 100

    elif growth >= 0.20:
        return 90

    elif growth >= 0.15:
        return 80

    elif growth >= 0.10:
        return 70

    elif growth >= 0.05:
        return 60

    elif growth >= 0:
        return 50

    elif growth >= -0.10:
        return 30

    return 10


def calculate_growth_score(ticker):
    """
    Growth Score based on:

        Revenue Growth
        Net Income Growth
        Reported FCF Growth

    Available metrics are equally weighted.

    NOTE:
    Reported FCF growth is used here as a
    business-growth indicator.

    Enterprise DCF itself uses normalized FCFF.
    """

    metrics = [

        calculate_revenue_growth(
            ticker
        ),

        calculate_net_income_growth(
            ticker
        ),

        calculate_fcf_growth(
            ticker
        )
    ]

    scores = []

    for metric in metrics:

        score = (
            score_growth_rate(
                metric
            )
        )

        if score is not None:

            scores.append(
                score
            )

    if not scores:
        return None

    return (
        sum(scores)
        / len(scores)
    )


# =========================================================
# Balance Sheet Score
# =========================================================

def calculate_financial_health_score(
    ticker
):
    """
    V1 Balance-Sheet Score.

    Currently based only on
    Debt-to-Equity.

    IMPORTANT:
    This remains simplified.

    Companies with large historical
    share repurchases may have unusually
    low book equity, which can distort D/E.
    """

    debt_to_equity = (
        calculate_debt_to_equity(
            ticker
        )
    )

    if debt_to_equity is None:
        return None

    if debt_to_equity <= 0.30:
        return 100

    elif debt_to_equity <= 0.60:
        return 85

    elif debt_to_equity <= 1.00:
        return 70

    elif debt_to_equity <= 1.50:
        return 55

    elif debt_to_equity <= 2.00:
        return 40

    elif debt_to_equity <= 3.00:
        return 25

    return 10


# =========================================================
# Momentum
# =========================================================

def calculate_six_month_momentum(
    ticker
):
    """
    Six-month price return.
    """

    history = (
        get_price_history(
            ticker,
            period="6mo"
        )
    )

    if (
        history is None
        or len(history) < 2
    ):
        return None

    start_price = (
        history[
            "Close"
        ].iloc[0]
    )

    end_price = (
        history[
            "Close"
        ].iloc[-1]
    )

    if start_price == 0:
        return None

    return (
        end_price
        - start_price
    ) / start_price


def score_momentum(
    momentum
):
    """
    Convert six-month momentum
    into a 0-100 score.
    """

    if momentum is None:
        return None

    if momentum >= 0.30:
        return 100

    elif momentum >= 0.20:
        return 90

    elif momentum >= 0.10:
        return 80

    elif momentum >= 0.05:
        return 70

    elif momentum >= 0:
        return 60

    elif momentum >= -0.10:
        return 45

    elif momentum >= -0.20:
        return 30

    return 10


def calculate_momentum_score(
    ticker
):
    """
    Standalone momentum-score wrapper.
    """

    momentum = (
        calculate_six_month_momentum(
            ticker
        )
    )

    return (
        score_momentum(
            momentum
        )
    )


# =========================================================
# Risk
# =========================================================

def calculate_annualised_volatility(
    ticker
):
    """
    Annualised historical volatility
    using approximately one year of
    daily market returns.
    """

    history = (
        get_price_history(
            ticker,
            period="1y"
        )
    )

    if (
        history is None
        or len(history) < 20
    ):
        return None

    daily_returns = (
        history[
            "Close"
        ]
        .pct_change()
        .dropna()
    )

    if len(daily_returns) == 0:
        return None

    return (
        daily_returns.std()
        * np.sqrt(
            252
        )
    )


def score_risk_from_volatility(
    volatility
):
    """
    Higher score = HIGHER market risk.

    This is historical price volatility,
    not a full fundamental-risk model.
    """

    if volatility is None:
        return None

    if volatility <= 0.15:
        return 10

    elif volatility <= 0.20:
        return 25

    elif volatility <= 0.30:
        return 40

    elif volatility <= 0.40:
        return 60

    elif volatility <= 0.60:
        return 80

    return 100


def calculate_risk_score(
    ticker
):
    """
    Standalone risk-score wrapper.
    """

    volatility = (
        calculate_annualised_volatility(
            ticker
        )
    )

    return (
        score_risk_from_volatility(
            volatility
        )
    )


# =========================================================
# Valuation Score
# =========================================================

def score_valuation_expected_return(
    expected_return
):
    """
    Convert Valuation Engine V2 expected
    return into a 0-100 research score.

    CUSTOM thresholds.

    This score is for research ranking.

    It does NOT directly determine the
    final investment recommendation.
    """

    if expected_return is None:
        return None

    if expected_return >= 0.30:
        return 100

    elif expected_return >= 0.20:
        return 90

    elif expected_return >= 0.10:
        return 80

    elif expected_return >= 0:
        return 65

    elif expected_return >= -0.10:
        return 50

    elif expected_return >= -0.20:
        return 35

    elif expected_return >= -0.30:
        return 20

    return 5


# =========================================================
# Calculate Fundamental Score
# =========================================================

def calculate_fundamental_score_from_components(
    components
):
    """
    Fundamental Score:

        Growth
        Quality
        Balance Sheet

    minus a small market-risk penalty.

    Valuation and Momentum are deliberately
    excluded.

    Missing positive components are excluded
    and remaining weights are re-normalized.
    """

    positive_score = 0
    available_weight = 0

    mapping = {

        "Growth":
            "Growth",

        "Quality":
            "Quality",

        "Balance Sheet":
            "Balance Sheet"
    }

    for weight_name, component_name in (
        mapping.items()
    ):

        score = (
            components.get(
                component_name
            )
        )

        if score is None:
            continue

        weight = (
            FUNDAMENTAL_WEIGHTS[
                weight_name
            ]
        )

        positive_score += (
            score
            * weight
        )

        available_weight += (
            weight
        )

    if available_weight == 0:
        return None

    normalized_score = (
        positive_score
        / available_weight
    )

    risk_score = (
        components.get(
            "Risk"
        )
    )

    if risk_score is None:

        risk_penalty = 0

    else:

        risk_penalty = (
            risk_score
            * FUNDAMENTAL_RISK_PENALTY_WEIGHT
        )

    final_score = (
        normalized_score
        - risk_penalty
    )

    return (
        clamp_score(
            final_score
        )
    )


# =========================================================
# Research Score
# =========================================================

def calculate_research_score_from_components(
    components
):
    """
    Research Profile Score:

        Fundamental Score
        Valuation Score
        Momentum Score

    This score is useful for:

        screening
        ranking
        research prioritisation

    It is NOT the final investment
    recommendation.
    """

    fundamental_score = (
        components.get(
            "Fundamental Score"
        )
    )

    valuation_score = (
        components.get(
            "Valuation"
        )
    )

    momentum_score = (
        components.get(
            "Momentum"
        )
    )

    values = {

        "Fundamental":
            fundamental_score,

        "Valuation":
            valuation_score,

        "Momentum":
            momentum_score
    }

    weighted_total = 0
    available_weight = 0

    for name, score in (
        values.items()
    ):

        if score is None:
            continue

        weight = (
            RESEARCH_PROFILE_WEIGHTS[
                name
            ]
        )

        weighted_total += (
            score
            * weight
        )

        available_weight += (
            weight
        )

    if available_weight == 0:
        return None

    return (
        clamp_score(
            weighted_total
            / available_weight
        )
    )


# =========================================================
# Calculate All Research Components Once
# =========================================================

def get_research_components(ticker, peer_tickers):
    from src.services.rating_service import build_research_components
    return build_research_components(ticker, peer_tickers)


# =========================================================
# Standalone Fundamental Score
# =========================================================

def calculate_fundamental_score(
    ticker,
    peer_tickers
):
    """
    Calculate current Fundamental Score.

    peer_tickers is accepted because the
    shared research-component pipeline
    also calculates valuation.
    """

    components = (
        get_research_components(
            ticker,
            peer_tickers
        )
    )

    return (
        components.get(
            "Fundamental Score"
        )
    )


# =========================================================
# Standalone Research Score
# =========================================================

def calculate_research_score(
    ticker,
    peer_tickers
):
    """
    Calculate overall Research Profile Score.
    """

    components = (
        get_research_components(
            ticker,
            peer_tickers
        )
    )

    return (
        calculate_research_score_from_components(
            components
        )
    )


# =========================================================
# Fundamental Grade
# =========================================================

def grade_fundamental_score(
    score
):
    """
    Fundamental business-quality grade.
    """

    if score is None:
        return None

    if score >= 85:
        return "A"

    elif score >= 75:
        return "A-"

    elif score >= 65:
        return "B+"

    elif score >= 55:
        return "B"

    elif score >= 45:
        return "C"

    return "D"


# =========================================================
# Research Grade
# =========================================================

def grade_research_score(
    score
):
    """
    Overall research-profile grade.

    This is NOT the investment
    recommendation.
    """

    if score is None:
        return None

    if score >= 85:
        return "A"

    elif score >= 75:
        return "A-"

    elif score >= 65:
        return "B+"

    elif score >= 55:
        return "B"

    elif score >= 45:
        return "C"

    return "D"


# =========================================================
# Rating Grade Compatibility Wrapper
# =========================================================

def get_rating_grade(
    ticker=None,
    peer_tickers=None,
    research_score=None
):
    """
    Compatibility wrapper for existing
    code that requests Research Grade.
    """

    if research_score is None:

        if (
            ticker is None
            or peer_tickers is None
        ):
            return None

        research_score = (
            calculate_research_score(
                ticker,
                peer_tickers
            )
        )

    return (
        grade_research_score(
            research_score
        )
    )


# =========================================================
# Research Summary
# =========================================================

def get_research_summary(
    ticker,
    peer_tickers
):
    """
    Generate full Research Model V3 summary.

    IMPORTANT:

    Recommendation is deliberately
    NOT produced here anymore.

    Investment Recommendation belongs
    exclusively to:

        src.analysis.recommendation
    """

    components = (
        get_research_components(
            ticker,
            peer_tickers
        )
    )

    fundamental_score = (
        components.get(
            "Fundamental Score"
        )
    )

    research_score = (
        calculate_research_score_from_components(
            components
        )
    )

    fundamental_grade = (
        grade_fundamental_score(
            fundamental_score
        )
    )

    research_grade = (
        grade_research_score(
            research_score
        )
    )

    quality_details = (
        components.get(
            "Quality Details",
            {}
        )
    )

    return {

        "Ticker":
            ticker.upper(),

        # -------------------------------------------------
        # Fundamental Profile
        # -------------------------------------------------

        "Growth Score":
            components.get(
                "Growth"
            ),

        "Quality Score":
            components.get(
                "Quality"
            ),

        "Financial Health Score":
            components.get(
                "Balance Sheet"
            ),

        "Fundamental Risk Score":
            components.get(
                "Risk"
            ),

        "Fundamental Score":
            fundamental_score,

        "Fundamental Grade":
            fundamental_grade,

        # -------------------------------------------------
        # Earnings Quality Detail
        # -------------------------------------------------

        "Non-Core Earnings Score":
            quality_details.get(
                "Non-Core Earnings Score"
            ),

        "Weighted Non-Core Contribution":
            quality_details.get(
                "Weighted Non-Core Contribution"
            ),

        # -------------------------------------------------
        # Market / Valuation Profile
        # -------------------------------------------------

        "Valuation Score":
            components.get(
                "Valuation"
            ),

        "Expected Return":
            components.get(
                "Expected Return"
            ),

        "Valuation Confidence":
            components.get(
                "Valuation Confidence"
            ),

        "Expectation Level":
            components.get(
                "Expectation Level"
            ),

        "Expectation Risk":
            components.get(
                "Expectation Risk"
            ),

        # -------------------------------------------------
        # Momentum
        # -------------------------------------------------

        "Momentum Score":
            components.get(
                "Momentum"
            ),

        "Six Month Momentum":
            components.get(
                "Six Month Momentum"
            ),

        "Annualised Volatility":
            components.get(
                "Annualised Volatility"
            ),

        # -------------------------------------------------
        # Overall Research Profile
        # -------------------------------------------------

        "Research Score":
            research_score,

        "Research Grade":
            research_grade
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
        f"RESEARCH MODEL V3: "
        f"{ticker}"
    )
    print("==============================")

    summary = (
        get_research_summary(
            ticker,
            peers
        )
    )

    percentage_metrics = {

        "Expected Return",
        "Weighted Non-Core Contribution",
        "Six Month Momentum",
        "Annualised Volatility"
    }

    for metric, value in (
        summary.items()
    ):

        if value is None:

            print(
                f"{metric}: N/A"
            )

        elif metric in (
            percentage_metrics
        ):

            print(
                f"{metric}: "
                f"{value:.2%}"
            )

        elif isinstance(
            value,
            (int, float)
        ):

            print(
                f"{metric}: "
                f"{value:.2f}"
            )

        else:

            print(
                f"{metric}: "
                f"{value}"
            )
