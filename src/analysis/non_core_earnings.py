from src.analysis.materiality import (
    analyze_materiality,
    format_percentage
)

from src.analysis.financial_line_extractor import (
    format_usd
)


# =========================================================
# Custom Research Weights
# =========================================================
#
# IMPORTANT:
# These are custom analytical parameters.
# They are NOT GAAP rules or accounting standards.
#
# Weight means:
#
#     how strongly a detected positive
#     non-core item should count against
#     earnings quality.
#
# =========================================================

NON_CORE_WEIGHTS = {

    # -----------------------------------------------------
    # High earnings-quality concern
    # -----------------------------------------------------

    "equity_security_gains": 1.00,

    # -----------------------------------------------------
    # Medium-high concern
    # -----------------------------------------------------

    "investment_gains": 0.75,

    # -----------------------------------------------------
    # Medium concern
    # -----------------------------------------------------

    "debt_security_gains": 0.50,

    "derivatives": 0.50,

    # -----------------------------------------------------
    # Lower concern
    # -----------------------------------------------------

    "equity_method": 0.25,

    # -----------------------------------------------------
    # Do not penalize earnings quality directly
    # -----------------------------------------------------

    "foreign_exchange": 0.00
}


# =========================================================
# Score Thresholds
# =========================================================

def score_weighted_non_core_ratio(
    ratio
):
    """
    Convert weighted non-core earnings
    contribution into a 0-100 quality score.

    V2 thresholds:

        < 1%       -> 100
        1% - 5%    -> 80
        5% - 10%   -> 60
        10% - 20%  -> 40
        >= 20%     -> 20

    Custom research model.
    """

    if ratio is None:
        return None

    if ratio < 0.01:
        return 100

    if ratio < 0.05:
        return 80

    if ratio < 0.10:
        return 60

    if ratio < 0.20:
        return 40

    return 20


# =========================================================
# Quality Label
# =========================================================

def classify_non_core_quality(
    score
):
    """
    Human-readable interpretation.
    """

    if score is None:
        return "Unknown"

    if score >= 90:
        return "Very Strong"

    if score >= 75:
        return "Strong"

    if score >= 55:
        return "Moderate"

    if score >= 35:
        return "Weak"

    return "Very Weak"


# =========================================================
# Weight Lookup
# =========================================================

def get_topic_weight(
    topic
):
    """
    Return research penalty weight.

    Unknown topics are NOT automatically
    penalized.

    Conservative behavior:
        unknown topic -> None
    """

    return (
        NON_CORE_WEIGHTS.get(
            topic
        )
    )


# =========================================================
# Prepare Weighted Events
# =========================================================

def calculate_weighted_non_core_events(
    materiality_report
):
    """
    Build weighted analysis for detected events.

    Positive items may receive an
    earnings-quality penalty.

    Negative items are tracked separately.

    FX currently receives 0 penalty weight.
    """

    events = (
        materiality_report.get(
            "events",
            []
        )
    )

    weighted_positive_events = []
    negative_events = []
    ignored_events = []

    total_positive_amount = 0
    total_weighted_amount = 0
    total_negative_amount = 0

    for event in events:

        topic = (
            event.get(
                "topic"
            )
        )

        amount = (
            event.get(
                "event_amount"
            )
        )

        if amount is None:
            continue

        weight = (
            get_topic_weight(
                topic
            )
        )

        # -------------------------------------------------
        # Unknown research category
        # -------------------------------------------------

        if weight is None:

            ignored_events.append(
                {
                    **event,

                    "weight":
                        None,

                    "weighted_amount":
                        None,

                    "reason":
                        "no_weight_defined"
                }
            )

            continue

        # -------------------------------------------------
        # Negative item
        # -------------------------------------------------

        if amount < 0:

            total_negative_amount += (
                abs(amount)
            )

            negative_events.append(
                {
                    **event,

                    "weight":
                        weight,

                    "weighted_amount":
                        0,

                    "reason":
                        "negative_item_tracked_separately"
                }
            )

            continue

        # -------------------------------------------------
        # Zero amount
        # -------------------------------------------------

        if amount == 0:
            continue

        # -------------------------------------------------
        # Positive item
        # -------------------------------------------------

        weighted_amount = (
            amount
            * weight
        )

        total_positive_amount += (
            amount
        )

        total_weighted_amount += (
            weighted_amount
        )

        weighted_positive_events.append(
            {
                **event,

                "weight":
                    weight,

                "weighted_amount":
                    weighted_amount,

                "reason":
                    "positive_non_core_item"
            }
        )

    return {
        "positive_events":
            weighted_positive_events,

        "negative_events":
            negative_events,

        "ignored_events":
            ignored_events,

        "positive_amount":
            total_positive_amount,

        "weighted_amount":
            total_weighted_amount,

        "negative_amount":
            total_negative_amount
    }


# =========================================================
# Main Analysis
# =========================================================

def analyze_non_core_earnings(
    ticker
):
    """
    Weighted Non-Core Earnings V2.

    Pipeline:

        Materiality Engine
              ↓
        Topic classification
              ↓
        Weight assignment
              ↓
        Weighted positive non-core earnings
              ↓
        Weighted contribution to pretax
              ↓
        Earnings-quality score
    """

    materiality_report = (
        analyze_materiality(
            ticker
        )
    )

    pretax_data = (
        materiality_report.get(
            "pretax_data"
        )
    )

    if not pretax_data:

        return {
            "ticker":
                ticker.upper(),

            "fiscal_year":
                None,

            "pretax_income":
                None,

            "positive_non_core_amount":
                None,

            "weighted_non_core_amount":
                None,

            "raw_positive_ratio":
                None,

            "weighted_non_core_ratio":
                None,

            "negative_non_core_amount":
                None,

            "score":
                None,

            "quality":
                "Unknown",

            "positive_events":
                [],

            "negative_events":
                [],

            "ignored_events":
                []
        }

    pretax_income = (
        pretax_data.get(
            "pretax_income"
        )
    )

    fiscal_year = (
        pretax_data.get(
            "fiscal_year"
        )
    )

    if (
        pretax_income is None
        or pretax_income == 0
    ):

        return {
            "ticker":
                ticker.upper(),

            "fiscal_year":
                fiscal_year,

            "pretax_income":
                pretax_income,

            "positive_non_core_amount":
                None,

            "weighted_non_core_amount":
                None,

            "raw_positive_ratio":
                None,

            "weighted_non_core_ratio":
                None,

            "negative_non_core_amount":
                None,

            "score":
                None,

            "quality":
                "Unknown",

            "positive_events":
                [],

            "negative_events":
                [],

            "ignored_events":
                []
        }

    # -----------------------------------------------------
    # Weighted events
    # -----------------------------------------------------

    weighted = (
        calculate_weighted_non_core_events(
            materiality_report
        )
    )

    positive_amount = (
        weighted[
            "positive_amount"
        ]
    )

    weighted_amount = (
        weighted[
            "weighted_amount"
        ]
    )

    negative_amount = (
        weighted[
            "negative_amount"
        ]
    )

    # -----------------------------------------------------
    # Ratios
    # -----------------------------------------------------

    denominator = abs(
        pretax_income
    )

    raw_positive_ratio = (
        positive_amount
        / denominator
    )

    weighted_ratio = (
        weighted_amount
        / denominator
    )

    # -----------------------------------------------------
    # Score
    # -----------------------------------------------------

    score = (
        score_weighted_non_core_ratio(
            weighted_ratio
        )
    )

    quality = (
        classify_non_core_quality(
            score
        )
    )

    return {
        "ticker":
            ticker.upper(),

        "fiscal_year":
            fiscal_year,

        "pretax_income":
            pretax_income,

        "positive_non_core_amount":
            positive_amount,

        "weighted_non_core_amount":
            weighted_amount,

        "raw_positive_ratio":
            raw_positive_ratio,

        "weighted_non_core_ratio":
            weighted_ratio,

        "negative_non_core_amount":
            negative_amount,

        "score":
            score,

        "quality":
            quality,

        "positive_events":
            weighted[
                "positive_events"
            ],

        "negative_events":
            weighted[
                "negative_events"
            ],

        "ignored_events":
            weighted[
                "ignored_events"
            ]
    }


# =========================================================
# Print Event
# =========================================================

def print_positive_event(
    event
):
    """
    Print one weighted positive event.
    """

    print(
        f"  - {event['topic']}"
    )

    print(
        f"    Amount: "
        f"{format_usd(event['event_amount'])}"
    )

    print(
        f"    Materiality: "
        f"{format_percentage(event['materiality_ratio'])}"
    )

    print(
        f"    Classifier Level: "
        f"{event['classification_level']}"
    )

    print(
        f"    Weight: "
        f"{event['weight']:.2f}"
    )

    print(
        f"    Weighted Amount: "
        f"{format_usd(event['weighted_amount'])}"
    )


def print_negative_event(
    event
):
    """
    Print negative non-core event.
    """

    print(
        f"  - {event['topic']}"
    )

    print(
        f"    Amount: "
        f"{format_usd(event['event_amount'])}"
    )

    print(
        f"    Materiality: "
        f"{format_percentage(event['materiality_ratio'])}"
    )

    print(
        f"    Assigned Weight: "
        f"{event['weight']:.2f}"
    )

    print(
        "    Earnings Quality Penalty: 0"
    )


# =========================================================
# Print Report
# =========================================================

def print_non_core_report(
    report
):
    """
    Pretty-print Weighted
    Non-Core Earnings V2.
    """

    print("\n==============================")
    print("WEIGHTED NON-CORE EARNINGS")
    print("==============================")

    print(
        f"\nTicker: "
        f"{report['ticker']}"
    )

    print(
        f"Fiscal Year: "
        f"{report['fiscal_year']}"
    )

    print(
        f"Pretax Income: "
        f"{format_usd(report['pretax_income'])}"
    )

    print(
        "\nRaw Positive Non-Core Earnings: "
        f"{format_usd(report['positive_non_core_amount'])}"
    )

    print(
        "Raw Positive Contribution: "
        f"{format_percentage(report['raw_positive_ratio'])}"
    )

    print(
        "\nWeighted Non-Core Earnings: "
        f"{format_usd(report['weighted_non_core_amount'])}"
    )

    print(
        "Weighted Non-Core Contribution: "
        f"{format_percentage(report['weighted_non_core_ratio'])}"
    )

    print(
        f"\nNon-Core Earnings Score: "
        f"{report['score']}"
    )

    print(
        f"Quality Assessment: "
        f"{report['quality']}"
    )

    print(
        "\nNegative Non-Core Items: "
        f"{format_usd(report['negative_non_core_amount'])}"
    )

    # -----------------------------------------------------
    # Positive Events
    # -----------------------------------------------------

    print("\n==============================")
    print("WEIGHTED POSITIVE EVENTS")
    print("==============================")

    positive_events = (
        report[
            "positive_events"
        ]
    )

    if not positive_events:

        print(
            "\nNone detected."
        )

    else:

        print()

        for event in positive_events:

            print_positive_event(
                event
            )

    # -----------------------------------------------------
    # Negative Events
    # -----------------------------------------------------

    print("\n==============================")
    print("NEGATIVE EVENTS")
    print("==============================")

    negative_events = (
        report[
            "negative_events"
        ]
    )

    if not negative_events:

        print(
            "\nNone detected."
        )

    else:

        print()

        for event in negative_events:

            print_negative_event(
                event
            )

    # -----------------------------------------------------
    # Ignored Events
    # -----------------------------------------------------

    ignored_events = (
        report[
            "ignored_events"
        ]
    )

    if ignored_events:

        print("\n==============================")
        print("UNWEIGHTED / REVIEW REQUIRED")
        print("==============================")

        print()

        for event in ignored_events:

            print(
                f"  - {event['topic']}"
            )

            print(
                f"    Amount: "
                f"{format_usd(event['event_amount'])}"
            )

            print(
                "    Reason: "
                "No model weight defined"
            )


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "GOOGL"

    print("\n==============================")
    print(
        f"NON-CORE EARNINGS V2: "
        f"{ticker}"
    )
    print("==============================")

    report = (
        analyze_non_core_earnings(
            ticker
        )
    )

    print_non_core_report(
        report
    )