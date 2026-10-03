from src.data.reuse import scoped
import time
import numpy as np

from src.data.financial_data import (
    get_revenue,
    get_net_income,
    get_operating_income,
    get_operating_cash_flow,
    get_total_assets
)

from src.analysis.fundamentals import (
    calculate_cash_conversion,
    calculate_roic
)

from src.analysis.non_core_earnings import (
    analyze_non_core_earnings
)


# =========================================================
# Model Weights
# =========================================================
#
# IMPORTANT:
# These are custom research-model weights.
# They are NOT GAAP rules or accounting standards.
#
# V2 Target Model:
#
# Cash Conversion      25%
# Core Revenue         15%
# Margin Stability     15%
# ROIC                 15%
# Accrual Quality      15%
# Non-Core Earnings    15%
#
# Missing components are excluded and
# remaining weights are re-normalized.
#
# =========================================================

QUALITY_WEIGHTS = {
    "Cash Conversion": 0.25,
    "Core Revenue": 0.15,
    "Margin Stability": 0.15,
    "ROIC": 0.15,
    "Accrual Quality": 0.15,
    "Non-Core Earnings": 0.15
}


# =========================================================
# Helper
# =========================================================

def clamp_score(value):
    """
    Keep a score between 0 and 100.
    """

    return max(
        0,
        min(100, value)
    )


# =========================================================
# Cash Conversion Score
# =========================================================

def score_cash_conversion(ticker):
    """
    Score:

        Operating Cash Flow / Net Income

    Around or above 1.0 is generally healthier.
    """

    ratio = (
        calculate_cash_conversion(
            ticker
        )
    )

    if ratio is None:
        return None

    if ratio >= 1.20:
        return 100

    elif ratio >= 1.00:
        return 90

    elif ratio >= 0.80:
        return 75

    elif ratio >= 0.60:
        return 55

    elif ratio >= 0.40:
        return 35

    return 15


# =========================================================
# Margin Stability
# =========================================================

def calculate_margin_history(ticker):
    """
    Calculate historical operating margins.
    """

    revenue = (
        get_revenue(
            ticker
        )
    )

    operating_income = (
        get_operating_income(
            ticker
        )
    )

    if (
        revenue is None
        or operating_income is None
    ):
        return None

    common_dates = (
        revenue
        .dropna()
        .index
        .intersection(
            operating_income
            .dropna()
            .index
        )
    )

    if len(common_dates) < 2:
        return None

    margins = []

    for date in common_dates:

        rev = revenue.loc[
            date
        ]

        op_income = (
            operating_income.loc[
                date
            ]
        )

        if rev == 0:
            continue

        margins.append(
            op_income / rev
        )

    if len(margins) < 2:
        return None

    return margins


def score_margin_stability(ticker):
    """
    Lower historical operating-margin
    volatility receives a higher score.
    """

    margins = (
        calculate_margin_history(
            ticker
        )
    )

    if margins is None:
        return None

    volatility = (
        np.std(
            margins
        )
    )

    if volatility <= 0.02:
        return 100

    elif volatility <= 0.04:
        return 85

    elif volatility <= 0.07:
        return 70

    elif volatility <= 0.10:
        return 50

    elif volatility <= 0.15:
        return 30

    return 10


# =========================================================
# ROIC Quality
# =========================================================

def score_roic(ticker):
    """
    Score company ROIC.

    IMPORTANT:
    calculate_roic() is still the
    simplified V1 implementation.

    Upgrade later to:
        NOPAT / Invested Capital
    """

    roic = (
        calculate_roic(
            ticker
        )
    )

    if roic is None:
        return None

    if roic >= 0.30:
        return 100

    elif roic >= 0.20:
        return 90

    elif roic >= 0.15:
        return 80

    elif roic >= 0.10:
        return 65

    elif roic >= 0.05:
        return 45

    elif roic >= 0:
        return 25

    return 0


# =========================================================
# Accrual Quality
# =========================================================

def calculate_accrual_ratio(ticker):
    """
    Simplified accrual ratio:

        (Net Income - Operating Cash Flow)
        / Total Assets

    Lower or negative accruals are generally
    stronger from an earnings-quality perspective.
    """

    net_income = (
        get_net_income(
            ticker
        )
    )

    operating_cash_flow = (
        get_operating_cash_flow(
            ticker
        )
    )

    total_assets = (
        get_total_assets(
            ticker
        )
    )

    if (
        net_income is None
        or operating_cash_flow is None
        or total_assets is None
    ):
        return None

    net_income = (
        net_income.dropna()
    )

    operating_cash_flow = (
        operating_cash_flow.dropna()
    )

    total_assets = (
        total_assets.dropna()
    )

    if (
        len(net_income) == 0
        or len(operating_cash_flow) == 0
        or len(total_assets) == 0
    ):
        return None

    assets = (
        total_assets.iloc[0]
    )

    if assets == 0:
        return None

    return (
        net_income.iloc[0]
        - operating_cash_flow.iloc[0]
    ) / assets


def score_accrual_quality(ticker):
    """
    Convert accrual ratio into 0-100 score.
    """

    accrual_ratio = (
        calculate_accrual_ratio(
            ticker
        )
    )

    if accrual_ratio is None:
        return None

    if accrual_ratio <= -0.05:
        return 100

    elif accrual_ratio <= 0:
        return 90

    elif accrual_ratio <= 0.03:
        return 75

    elif accrual_ratio <= 0.06:
        return 55

    elif accrual_ratio <= 0.10:
        return 30

    return 10


# =========================================================
# Core Revenue Quality
# =========================================================

def score_core_revenue(ticker):
    """
    Reserved for future revenue-composition analysis.

    Current system does not yet have a
    sufficiently reliable cross-company method
    for separating core vs non-core REVENUE.

    No artificial score is inserted.
    """

    return None


# =========================================================
# Non-Core Earnings Quality
# =========================================================

def get_non_core_earnings_component(ticker):
    """
    Retrieve Weighted Non-Core Earnings V2.

    Returns both:
        score
        supporting research details

    The score is based on weighted positive
    non-core contribution to pretax income.
    """

    try:

        report = (
            analyze_non_core_earnings(
                ticker
            )
        )

    except Exception as error:

        print(
            f"Non-Core Earnings analysis "
            f"failed for {ticker}: {error}"
        )

        return {
            "score": None,
            "report": None
        }

    score = (
        report.get(
            "score"
        )
    )

    return {
        "score":
            score,

        "report":
            report
    }


# =========================================================
# Calculate Components Once
# =========================================================

def get_quality_components(ticker):
    """
    Calculate all Earnings Quality components once.

    Profiling version.
    """

    total_start = time.perf_counter()

    print("\n")
    print("=" * 60)
    print(
        f"[QUALITY PROFILE] EARNINGS QUALITY: "
        f"{ticker.upper()}"
    )
    print("=" * 60)

    # =====================================================
    # Non-Core Earnings
    # =====================================================

    start = time.perf_counter()

    non_core = (
        get_non_core_earnings_component(
            ticker
        )
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        "[QUALITY PROFILE] Non-Core Earnings  : "
        f"{elapsed:.3f}s"
    )

    # =====================================================
    # Cash Conversion
    # =====================================================

    start = time.perf_counter()

    cash_conversion_score = (
        score_cash_conversion(
            ticker
        )
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        "[QUALITY PROFILE] Cash Conversion    : "
        f"{elapsed:.3f}s"
    )

    # =====================================================
    # Core Revenue
    # =====================================================

    start = time.perf_counter()

    core_revenue_score = (
        score_core_revenue(
            ticker
        )
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        "[QUALITY PROFILE] Core Revenue       : "
        f"{elapsed:.3f}s"
    )

    # =====================================================
    # Margin Stability
    # =====================================================

    start = time.perf_counter()

    margin_stability_score = (
        score_margin_stability(
            ticker
        )
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        "[QUALITY PROFILE] Margin Stability   : "
        f"{elapsed:.3f}s"
    )

    # =====================================================
    # ROIC
    # =====================================================

    start = time.perf_counter()

    roic_score = (
        score_roic(
            ticker
        )
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        "[QUALITY PROFILE] ROIC               : "
        f"{elapsed:.3f}s"
    )

    # =====================================================
    # Accrual Quality
    # =====================================================

    start = time.perf_counter()

    accrual_quality_score = (
        score_accrual_quality(
            ticker
        )
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        "[QUALITY PROFILE] Accrual Quality    : "
        f"{elapsed:.3f}s"
    )

    # =====================================================
    # Components
    # =====================================================

    components = {

        "Cash Conversion": {
            "score":
                cash_conversion_score,

            "weight":
                QUALITY_WEIGHTS[
                    "Cash Conversion"
                ]
        },

        "Core Revenue": {
            "score":
                core_revenue_score,

            "weight":
                QUALITY_WEIGHTS[
                    "Core Revenue"
                ]
        },

        "Margin Stability": {
            "score":
                margin_stability_score,

            "weight":
                QUALITY_WEIGHTS[
                    "Margin Stability"
                ]
        },

        "ROIC": {
            "score":
                roic_score,

            "weight":
                QUALITY_WEIGHTS[
                    "ROIC"
                ]
        },

        "Accrual Quality": {
            "score":
                accrual_quality_score,

            "weight":
                QUALITY_WEIGHTS[
                    "Accrual Quality"
                ]
        },

        "Non-Core Earnings": {
            "score":
                non_core[
                    "score"
                ],

            "weight":
                QUALITY_WEIGHTS[
                    "Non-Core Earnings"
                ],

            "details":
                non_core[
                    "report"
                ]
        }
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
        "[QUALITY PROFILE] TOTAL              : "
        f"{total_elapsed:.3f}s"
    )

    print("=" * 60)
    print("\n")

    return components


# =========================================================
# Earnings Quality Model
# =========================================================

def calculate_earnings_quality_score(
    ticker=None,
    components=None
):
    """
    Earnings Quality V2.

    Target formula:

        EQ =
        0.25 Cash Conversion
        + 0.15 Core Revenue
        + 0.15 Margin Stability
        + 0.15 ROIC
        + 0.15 Accrual Quality
        + 0.15 Non-Core Earnings

    Missing components are excluded and
    available weights are re-normalized.

    Pass components directly when already
    calculated to avoid repeating SEC calls.
    """

    if components is None:

        if ticker is None:
            return None

        components = (
            get_quality_components(
                ticker
            )
        )

    weighted_score = 0
    available_weight = 0

    for component in (
        components.values()
    ):

        score = (
            component.get(
                "score"
            )
        )

        weight = (
            component.get(
                "weight"
            )
        )

        if (
            score is None
            or weight is None
        ):
            continue

        weighted_score += (
            score
            * weight
        )

        available_weight += (
            weight
        )

    if available_weight == 0:
        return None

    final_score = (
        weighted_score
        / available_weight
    )

    return clamp_score(
        final_score
    )


# =========================================================
# Earnings Quality Label
# =========================================================

def classify_earnings_quality(
    score
):
    """
    Human-readable overall quality label.

    Custom research interpretation.
    """

    if score is None:
        return "Unknown"

    if score >= 85:
        return "Very Strong"

    if score >= 70:
        return "Strong"

    if score >= 55:
        return "Moderate"

    if score >= 40:
        return "Weak"

    return "Very Weak"


# =========================================================
# Quality Summary
# =========================================================

@scoped
def get_quality_summary(ticker, components=None):
    """
    Generate one complete Earnings Quality
    summary without recalculating the SEC
    pipeline multiple times.
    """

    if components is None:
        components = get_quality_components(ticker)

    final_score = (
        calculate_earnings_quality_score(
            components=components
        )
    )

    non_core_details = (
        components[
            "Non-Core Earnings"
        ].get(
            "details"
        )
    )

    weighted_non_core_ratio = None

    if non_core_details:

        weighted_non_core_ratio = (
            non_core_details.get(
                "weighted_non_core_ratio"
            )
        )

    return {
        "Ticker":
            ticker.upper(),

        "Cash Conversion Score":
            components[
                "Cash Conversion"
            ][
                "score"
            ],

        "Core Revenue Score":
            components[
                "Core Revenue"
            ][
                "score"
            ],

        "Margin Stability Score":
            components[
                "Margin Stability"
            ][
                "score"
            ],

        "ROIC Score":
            components[
                "ROIC"
            ][
                "score"
            ],

        "Accrual Quality Score":
            components[
                "Accrual Quality"
            ][
                "score"
            ],

        "Non-Core Earnings Score":
            components[
                "Non-Core Earnings"
            ][
                "score"
            ],

        "Weighted Non-Core Contribution":
            weighted_non_core_ratio,

        "Earnings Quality Score":
            final_score,

        "Earnings Quality":
            classify_earnings_quality(
                final_score
            )
    }


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "GOOGL"

    print("\n==============================")
    print(
        f"EARNINGS QUALITY V2: "
        f"{ticker}"
    )
    print("==============================")

    summary = (
        get_quality_summary(
            ticker
        )
    )

    for metric, value in (
        summary.items()
    ):

        if value is None:

            print(
                f"{metric}: N/A"
            )

        elif metric == "Ticker":

            print(
                f"{metric}: {value}"
            )

        elif metric == "Earnings Quality":

            print(
                f"{metric}: {value}"
            )

        elif metric == (
            "Weighted Non-Core Contribution"
        ):

            print(
                f"{metric}: "
                f"{value * 100:.2f}%"
            )

        else:

            print(
                f"{metric}: "
                f"{value:.2f}"
            )
