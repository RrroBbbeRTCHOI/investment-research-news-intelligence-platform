from src.data.reuse import scoped
import time

from src.analysis.filing_classifier import (
    classify_sec_filing
)

from src.analysis.financial_line_extractor import (
    extract_lines_from_results,
    deduplicate_extractions,
    format_usd
)

from src.data.sec_data import (
    get_sec_pretax_income
)


# =========================================================
# Materiality Thresholds
# =========================================================

LOW_THRESHOLD = 0.01
MODERATE_THRESHOLD = 0.05
HIGH_THRESHOLD = 0.10


# =========================================================
# Materiality Classification
# =========================================================

def classify_materiality(
    ratio
):
    """
    Classify event materiality based on:

        absolute event amount
        /
        pretax income

    Thresholds:

        < 1%      Low
        1% - 5%   Moderate
        5% - 10%  Material
        >= 10%    Highly Material
    """

    if ratio is None:
        return "Unknown"

    if ratio < LOW_THRESHOLD:
        return "Low"

    if ratio < MODERATE_THRESHOLD:
        return "Moderate"

    if ratio < HIGH_THRESHOLD:
        return "Material"

    return "Highly Material"


# =========================================================
# Earnings Direction
# =========================================================

def classify_earnings_direction(
    amount
):
    """
    Determine whether the event increased
    or reduced pretax earnings.
    """

    if amount is None:
        return "Unknown"

    if amount > 0:
        return "Positive"

    if amount < 0:
        return "Negative"

    return "Neutral"


# =========================================================
# Research Priority
# =========================================================

def classify_research_priority(
    classification_level,
    materiality_ratio
):
    """
    Combine classifier level with
    financial materiality.

    This is NOT the final stock rating.

    It only tells the research system
    how urgently an item should be reviewed.
    """

    if materiality_ratio is None:
        return "Unknown"

    # -----------------------------------------------------
    # Highest Priority
    # -----------------------------------------------------

    if (
        classification_level >= 3
        and materiality_ratio >= 0.10
    ):
        return "High"

    # -----------------------------------------------------
    # Important
    # -----------------------------------------------------

    if (
        materiality_ratio >= 0.05
        or (
            classification_level >= 3
            and materiality_ratio >= 0.01
        )
    ):
        return "Medium-High"

    # -----------------------------------------------------
    # Normal Review
    # -----------------------------------------------------

    if materiality_ratio >= 0.01:
        return "Medium"

    return "Low"


# =========================================================
# Calculate One Event
# =========================================================

def calculate_event_materiality(
    event_amount,
    pretax_income
):
    """
    Calculate:

        absolute materiality ratio
        signed earnings contribution

    Example:

        Equity gains = +24.08B
        Pretax = 158.826B

        Materiality = 15.16%
        Signed contribution = +15.16%
    """

    if (
        event_amount is None
        or pretax_income is None
    ):
        return None

    if pretax_income == 0:
        return None

    denominator = (
        abs(
            pretax_income
        )
    )

    absolute_ratio = (
        abs(
            event_amount
        )
        / denominator
    )

    signed_ratio = (
        event_amount
        / denominator
    )

    return {
        "absolute_ratio":
            absolute_ratio,

        "signed_ratio":
            signed_ratio,

        "direction":
            classify_earnings_direction(
                event_amount
            ),

        "materiality":
            classify_materiality(
                absolute_ratio
            )
    }


# =========================================================
# Get Pretax Income
# =========================================================

def get_materiality_base(
    ticker
):
    """
    Retrieve annual pretax income directly
    from the SEC Company Facts pipeline.

    This intentionally reuses sec_data.py
    rather than duplicating financial-data
    logic.
    """

    result = (
        get_sec_pretax_income(
            ticker,
            period="annual"
        )
    )

    if result is None:
        return None

    value = (
        result.get(
            "value"
        )
    )

    fiscal_year = (
        result.get(
            "fiscal_year"
        )
    )

    period_end = (
        result.get(
            "end"
        )
    )

    if value is None:
        return None

    return {
        "pretax_income":
            value,

        "fiscal_year":
            fiscal_year,

        "period_end":
            period_end,

        "source":
            "SEC Company Facts"
    }


# =========================================================
# Analyze Extracted Financial Line
# =========================================================

def analyze_financial_line_materiality(
    extracted_line,
    pretax_data
):
    """
    Compare one extracted research event
    against SEC pretax income.
    """

    latest_value = (
        extracted_line.get(
            "latest_value"
        )
    )

    if not latest_value:
        return None

    event_amount = (
        latest_value.get(
            "usd_value"
        )
    )

    if event_amount is None:
        return None

    event_year = (
        extracted_line.get(
            "latest_year"
        )
    )

    pretax_income = (
        pretax_data.get(
            "pretax_income"
        )
    )

    pretax_year = (
        pretax_data.get(
            "fiscal_year"
        )
    )

    calculation = (
        calculate_event_materiality(
            event_amount=event_amount,
            pretax_income=pretax_income
        )
    )

    if calculation is None:
        return None

    classification_level = (
        extracted_line.get(
            "classification_level",
            0
        )
    )

    # -----------------------------------------------------
    # Fiscal Year Validation
    # -----------------------------------------------------

    year_match = (
        event_year
        == pretax_year
    )

    # -----------------------------------------------------
    # Research Priority
    # -----------------------------------------------------

    research_priority = (
        classify_research_priority(
            classification_level=(
                classification_level
            ),
            materiality_ratio=(
                calculation[
                    "absolute_ratio"
                ]
            )
        )
    )

    return {
        "topic":
            extracted_line.get(
                "topic"
            ),

        "financial_line":
            extracted_line.get(
                "financial_line"
            ),

        "classification_level":
            classification_level,

        "event_year":
            event_year,

        "event_amount":
            event_amount,

        "pretax_year":
            pretax_year,

        "pretax_income":
            pretax_income,

        "year_match":
            year_match,

        "materiality_ratio":
            calculation[
                "absolute_ratio"
            ],

        "signed_contribution":
            calculation[
                "signed_ratio"
            ],

        "direction":
            calculation[
                "direction"
            ],

        "materiality":
            calculation[
                "materiality"
            ],

        "research_priority":
            research_priority,

        "pretax_source":
            pretax_data.get(
                "source"
            )
    }


# =========================================================
# Full Materiality Analysis
# =========================================================

@scoped
def analyze_materiality(
    ticker
):
    """
    Full Materiality Engine V1.

    Pipeline:

        SEC 10-K
            ↓
        Filing Classifier
            ↓
        Financial Line Extractor
            ↓
        SEC Pretax Income
            ↓
        Materiality Analysis

    PERFORMANCE:
        This version adds profiling only.
        No analytical logic is changed.
    """

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
        f"[MATERIALITY PROFILE] "
        f"ANALYZE MATERIALITY: {ticker}"
    )

    print("=" * 60)

    # =====================================================
    # Step 1: Classify Filing
    # =====================================================

    classifier_start = (
        time.perf_counter()
    )

    classifier_results = (
        classify_sec_filing(
            ticker=ticker,
            form_type="10-K"
        )
    )

    classifier_elapsed = (
        time.perf_counter()
        - classifier_start
    )

    print(
        "[MATERIALITY PROFILE] Filing Classifier : "
        f"{classifier_elapsed:.3f}s"
    )

    # =====================================================
    # Step 2: Extract Financial Lines
    # =====================================================

    extraction_start = (
        time.perf_counter()
    )

    extracted_lines = (
        extract_lines_from_results(
            classifier_results,
            minimum_level=2
        )
    )

    extraction_elapsed = (
        time.perf_counter()
        - extraction_start
    )

    print(
        "[MATERIALITY PROFILE] Line Extraction   : "
        f"{extraction_elapsed:.3f}s"
    )

    # =====================================================
    # Step 3: Deduplicate
    # =====================================================

    dedupe_start = (
        time.perf_counter()
    )

    extracted_lines = (
        deduplicate_extractions(
            extracted_lines
        )
    )

    dedupe_elapsed = (
        time.perf_counter()
        - dedupe_start
    )

    print(
        "[MATERIALITY PROFILE] Deduplication     : "
        f"{dedupe_elapsed:.6f}s"
    )

    # =====================================================
    # Step 4: Pretax Income
    # =====================================================

    pretax_start = (
        time.perf_counter()
    )

    pretax_data = (
        get_materiality_base(
            ticker
        )
    )

    pretax_elapsed = (
        time.perf_counter()
        - pretax_start
    )

    print(
        "[MATERIALITY PROFILE] Pretax Income     : "
        f"{pretax_elapsed:.3f}s"
    )

    # -----------------------------------------------------
    # Pretax unavailable
    # -----------------------------------------------------

    if pretax_data is None:

        total_elapsed = (
            time.perf_counter()
            - total_start
        )

        print(
            "[MATERIALITY PROFILE] Event Analysis    : "
            "0.000000s"
        )

        print("-" * 60)

        print(
            "[MATERIALITY PROFILE] TOTAL             : "
            f"{total_elapsed:.3f}s"
        )

        print("=" * 60)
        print("\n")

        return {
            "ticker":
                ticker,

            "pretax_data":
                None,

            "events":
                []
        }

    # =====================================================
    # Step 5: Calculate Event Materiality
    # =====================================================

    event_start = (
        time.perf_counter()
    )

    analyzed_events = []

    for line in (
        extracted_lines
    ):

        result = (
            analyze_financial_line_materiality(
                extracted_line=line,
                pretax_data=pretax_data
            )
        )

        if result is None:
            continue

        analyzed_events.append(
            result
        )

    # -----------------------------------------------------
    # Sort largest materiality first
    # -----------------------------------------------------

    analyzed_events = (
        sorted(
            analyzed_events,
            key=lambda item:
                item[
                    "materiality_ratio"
                ],
            reverse=True
        )
    )

    event_elapsed = (
        time.perf_counter()
        - event_start
    )

    print(
        "[MATERIALITY PROFILE] Event Analysis    : "
        f"{event_elapsed:.6f}s"
    )

    # =====================================================
    # Total
    # =====================================================

    total_elapsed = (
        time.perf_counter()
        - total_start
    )

    print("-" * 60)

    print(
        "[MATERIALITY PROFILE] TOTAL             : "
        f"{total_elapsed:.3f}s"
    )

    print("=" * 60)
    print("\n")

    return {
        "ticker":
            ticker,

        "pretax_data":
            pretax_data,

        "events":
            analyzed_events
    }


# =========================================================
# Aggregate Research Exposure
# =========================================================

def calculate_total_detected_exposure(
    report
):
    """
    Calculate sum of ABSOLUTE detected
    event amounts.

    IMPORTANT:

    This is NOT adjusted earnings.

    It is only a research exposure metric.

    Example:

        equity gains +24B
        FX loss -0.4B

    Absolute exposure:

        24B + 0.4B

    We do NOT claim this is an
    accounting subtotal.
    """

    events = (
        report.get(
            "events",
            []
        )
    )

    pretax_data = (
        report.get(
            "pretax_data"
        )
    )

    if not pretax_data:
        return None

    pretax_income = (
        pretax_data.get(
            "pretax_income"
        )
    )

    if (
        pretax_income is None
        or pretax_income == 0
    ):
        return None

    total = (
        sum(
            abs(
                event[
                    "event_amount"
                ]
            )
            for event
            in events
        )
    )

    ratio = (
        total
        / abs(
            pretax_income
        )
    )

    return {
        "absolute_detected_amount":
            total,

        "ratio":
            ratio
    }


# =========================================================
# Percentage Formatting
# =========================================================

def format_percentage(
    value
):
    """
    Convert ratio to readable percentage.
    """

    if value is None:
        return "N/A"

    return (
        f"{value * 100:.2f}%"
    )


# =========================================================
# Pretty Print
# =========================================================

def print_materiality_report(
    report
):
    """
    Print Materiality Engine output.
    """

    print("\n==============================")
    print("MATERIALITY ANALYSIS")
    print("==============================")

    print(
        f"\nTicker: "
        f"{report['ticker']}"
    )

    pretax_data = (
        report.get(
            "pretax_data"
        )
    )

    if not pretax_data:

        print(
            "\nPretax Income: N/A"
        )

        return

    print(
        f"Fiscal Year: "
        f"{pretax_data['fiscal_year']}"
    )

    print(
        f"Pretax Income: "
        f"{format_usd(pretax_data['pretax_income'])}"
    )

    print(
        f"Source: "
        f"{pretax_data['source']}"
    )

    events = (
        report.get(
            "events",
            []
        )
    )

    print(
        f"\nResearch Events: "
        f"{len(events)}"
    )

    if not events:

        print(
            "\nNo materiality events available."
        )

        return

    for index, event in (
        enumerate(
            events,
            start=1
        )
    ):

        print(
            "\n------------------------------"
        )

        print(
            f"EVENT {index}"
        )

        print(
            "------------------------------"
        )

        print(
            f"Topic: "
            f"{event['topic']}"
        )

        print(
            f"Financial Line: "
            f"{event['financial_line']}"
        )

        print(
            f"Classifier Level: "
            f"{event['classification_level']}"
        )

        print(
            f"Event Year: "
            f"{event['event_year']}"
        )

        print(
            f"Event Amount: "
            f"{format_usd(event['event_amount'])}"
        )

        print(
            f"Pretax Income: "
            f"{format_usd(event['pretax_income'])}"
        )

        print(
            f"Materiality Ratio: "
            f"{format_percentage(event['materiality_ratio'])}"
        )

        print(
            f"Signed Contribution: "
            f"{format_percentage(event['signed_contribution'])}"
        )

        print(
            f"Direction: "
            f"{event['direction']}"
        )

        print(
            f"Materiality: "
            f"{event['materiality']}"
        )

        print(
            f"Research Priority: "
            f"{event['research_priority']}"
        )

        print(
            f"Fiscal Year Match: "
            f"{event['year_match']}"
        )

    # =====================================================
    # Exposure Summary
    # =====================================================

    exposure = (
        calculate_total_detected_exposure(
            report
        )
    )

    if exposure:

        print(
            "\n=============================="
        )

        print(
            "DETECTED RESEARCH EXPOSURE"
        )

        print(
            "=============================="
        )

        print(
            "Absolute Detected Amount: "
            f"{format_usd(exposure['absolute_detected_amount'])}"
        )

        print(
            "Share of Pretax Income: "
            f"{format_percentage(exposure['ratio'])}"
        )

        print(
            "\nNote: This is a research exposure "
            "metric, not adjusted earnings."
        )


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "GOOGL"

    print("\n==============================")
    print(
        f"MATERIALITY ENGINE V1: "
        f"{ticker}"
    )
    print("==============================")

    report = (
        analyze_materiality(
            ticker
        )
    )

    print_materiality_report(
        report
    )