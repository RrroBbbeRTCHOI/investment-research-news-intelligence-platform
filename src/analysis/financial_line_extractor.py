import re

from src.analysis.filing_classifier import (
    classify_sec_filing
)


# =========================================================
# Known Financial Lines
# =========================================================

FINANCIAL_LINE_PATTERNS = {
    "equity_security_gains": [
        "gain (loss) on equity securities, net",
        "gain (loss) on equity securities"
    ],

    "debt_security_gains": [
        "gain (loss) on debt securities, net",
        "gain (loss) on debt securities"
    ],

    "foreign_exchange": [
        "foreign currency exchange gain (loss), net",
        "foreign exchange gain (loss), net"
    ],

    "equity_method": [
        "income (loss) and impairment from equity method investments, net",
        "income (loss) from equity method investments, net"
    ],

    "interest_income": [
        "interest income"
    ],

    "interest_expense": [
        "interest expense"
    ],

    "other_income": [
        "other income (expense), net",
        "other income/(expense), net"
    ]
}


# =========================================================
# Helpers
# =========================================================

def normalize_line(
    text
):
    """
    Normalize whitespace while
    preserving financial wording.
    """

    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def parse_number(
    value
):
    """
    Convert accounting-style text
    to numeric value.

    Examples:

        24,080  -> 24080
        (382)   -> -382
        540     -> 540
    """

    if value is None:
        return None

    value = (
        str(value)
        .strip()
    )

    negative = (
        value.startswith("(")
        and value.endswith(")")
    )

    value = (
        value
        .replace("$", "")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )

    try:

        number = float(value)

    except ValueError:

        return None

    if negative:
        number = -number

    return number


# =========================================================
# Financial Number Detection
# =========================================================

FINANCIAL_NUMBER_PATTERN = re.compile(
    r"""
    (?:
        \(\s*
        \d{1,3}(?:,\d{3})*
        (?:\.\d+)?
        \s*\)
    )
    |
    (?:
        \d{1,3}(?:,\d{3})+
        (?:\.\d+)?
    )
    |
    (?:
        \d+(?:\.\d+)?
    )
    """,
    re.VERBOSE
)


def extract_numbers_from_text(
    text
):
    """
    Extract accounting-style numbers.
    """

    matches = (
        FINANCIAL_NUMBER_PATTERN
        .findall(
            text
        )
    )

    results = []

    for match in matches:

        parsed = (
            parse_number(
                match
            )
        )

        if parsed is None:
            continue

        results.append(
            {
                "raw":
                    match.strip(),

                "value":
                    parsed
            }
        )

    return results


# =========================================================
# Locate Exact Financial Line
# =========================================================

def find_financial_line_position(
    context,
    patterns
):
    """
    Find the best matching financial
    line inside a context.
    """

    context_lower = (
        context.lower()
    )

    matches = []

    for pattern in patterns:

        index = (
            context_lower.find(
                pattern.lower()
            )
        )

        if index == -1:
            continue

        matches.append(
            {
                "pattern":
                    pattern,

                "position":
                    index
            }
        )

    if not matches:
        return None

    return min(
        matches,
        key=lambda item:
            item["position"]
    )


# =========================================================
# Extract Text After Financial Line
# =========================================================

def extract_after_line(
    context,
    line_position,
    line_text,
    chars_after=180
):
    """
    Extract a short local window AFTER
    the financial line.

    This is intentionally much narrower
    than the classifier context.
    """

    start = (
        line_position
        + len(line_text)
    )

    end = min(
        len(context),
        start
        + chars_after
    )

    return context[
        start:end
    ]


# =========================================================
# Detect Years
# =========================================================

def extract_years(
    context
):
    """
    Detect fiscal years appearing
    in the local financial table.

    Example:
        2023
        2024
        2025
    """

    years = re.findall(
        r"\b20\d{2}\b",
        context
    )

    cleaned = []

    for year in years:

        year_int = int(
            year
        )

        if year_int not in cleaned:
            cleaned.append(
                year_int
            )

    return cleaned


# =========================================================
# Remove Obvious Years From Numbers
# =========================================================

def remove_year_numbers(
    numbers,
    years
):
    """
    Prevent years such as 2024 / 2025
    being interpreted as dollar amounts.
    """

    year_values = set(
        float(year)
        for year in years
    )

    return [
        item
        for item
        in numbers
        if item["value"]
        not in year_values
    ]


# =========================================================
# Match Years to Values
# =========================================================

def map_years_to_values(
    years,
    values
):
    """
    Basic V1 year-value mapping.

    Assumption:
    financial line values follow
    the column order shown in table.

    Example:

        Years:
        2024 2025

        Line:
        3,714 24,080

    Output:

        2024 -> 3714
        2025 -> 24080
    """

    if not years:
        return {}

    if not values:
        return {}

    if len(values) < len(years):
        return {}

    values = (
        values[:len(years)]
    )

    return {
        year:
            value["value"]

        for year, value
        in zip(
            years,
            values
        )
    }


# =========================================================
# Determine Unit
# =========================================================

def detect_financial_unit(
    context
):
    """
    Detect financial table unit.

    Handles SEC formatting such as:

        (in millions)
        ( in millions )
        in
        millions
    """

    if not context:
        return "unknown"

    normalized = re.sub(
        r"\s+",
        " ",
        context.lower()
    )

    if re.search(
        r"\bin\s+millions\b",
        normalized
    ):
        return "millions"

    if re.search(
        r"\bin\s+thousands\b",
        normalized
    ):
        return "thousands"

    if re.search(
        r"\bin\s+billions\b",
        normalized
    ):
        return "billions"

    return "unknown"

# =========================================================
# Normalize Amount to USD
# =========================================================

def normalize_to_usd(
    value,
    unit
):
    """
    Convert table value into actual USD.
    """

    if value is None:
        return None

    if unit == "millions":

        return (
            value
            * 1_000_000
        )

    if unit == "thousands":

        return (
            value
            * 1_000
        )

    if unit == "billions":

        return (
            value
            * 1_000_000_000
        )

    return None


# =========================================================
# Extract One Financial Line
# =========================================================

def extract_financial_line(
    context,
    topic
):
    """
    Extract exact financial line
    and its annual values.
    """

    patterns = (
        FINANCIAL_LINE_PATTERNS.get(
            topic
        )
    )

    if not patterns:
        return None

    line_match = (
        find_financial_line_position(
            context=context,
            patterns=patterns
        )
    )

    if not line_match:
        return None

    line_text = (
        line_match[
            "pattern"
        ]
    )

    line_position = (
        line_match[
            "position"
        ]
    )

    local_context_start = max(
        0,
        line_position - 500
    )

    local_context_end = min(
        len(context),
        line_position + 300
    )

    local_context = context[
        local_context_start:
        local_context_end
    ]

    years = (
        extract_years(
            local_context
        )
    )

    after_line = (
        extract_after_line(
            context=context,
            line_position=line_position,
            line_text=line_text,
            chars_after=160
        )
    )

    numbers = (
        extract_numbers_from_text(
            after_line
        )
    )

    numbers = (
        remove_year_numbers(
            numbers,
            years
        )
    )

    unit = (
        detect_financial_unit(
            local_context
        )
    )

    if unit == "unknown":
        unit = (
            detect_financial_unit(
                context
        )
    )

    year_values = (
        map_years_to_values(
            years=years,
            values=numbers
        )
    )
    
    if not year_values:
        return None

    normalized_values = {}

    for year, value in (
        year_values.items()
    ):

        normalized_values[
            year
        ] = {
            "reported_value":
                value,

            "unit":
                unit,

            "usd_value":
                normalize_to_usd(
                    value,
                    unit
                )
        }

    latest_year = None
    latest_value = None

    if normalized_values:

        latest_year = max(
            normalized_values.keys()
        )

        latest_value = (
            normalized_values[
                latest_year
            ]
        )

    return {
        "topic":
            topic,

        "financial_line":
            line_text,

        "years":
            years,

        "values":
            normalized_values,

        "latest_year":
            latest_year,

        "latest_value":
            latest_value,

        "local_context":
            local_context
    }


# =========================================================
# Extract Lines From Classifier Results
# =========================================================

def extract_lines_from_results(
    classifier_results,
    minimum_level=2
):
    """
    Take confirmed classifier hits
    and attempt exact financial-line
    extraction.
    """

    extracted = []

    for result in (
        classifier_results
    ):

        if (
            result[
                "final_level"
            ]
            < minimum_level
        ):
            continue

        topic = (
            result[
                "topic"
            ]
        )

        # Only topics with known
        # financial line patterns
        if (
            topic
            not in FINANCIAL_LINE_PATTERNS
        ):
            continue

        for match in (
            result[
                "validated_matches"
            ]
        ):

            if (
                match[
                    "final_level"
                ]
                < minimum_level
            ):
                continue

            extraction = (
                extract_financial_line(
                    context=(
                        match[
                            "context"
                        ]
                    ),
                    topic=topic
                )
            )

            if extraction is None:
                continue

            extraction[
                "classification_level"
            ] = (
                result[
                    "final_level"
                ]
            )

            extracted.append(
                extraction
            )

    return extracted


# =========================================================
# Deduplicate Financial Lines
# =========================================================

def deduplicate_extractions(
    extractions
):
    """
    Multiple keywords may point to
    the same financial table.

    Deduplicate using:

        topic
        financial line
        latest year
        latest reported value
    """

    unique = {}

    for item in extractions:

        latest_value = (
            item.get(
                "latest_value"
            )
        )

        reported_value = None

        if latest_value:

            reported_value = (
                latest_value.get(
                    "reported_value"
                )
            )

        key = (
            item.get(
                "topic"
            ),

            item.get(
                "financial_line"
            ),

            item.get(
                "latest_year"
            ),

            reported_value
        )

        if key not in unique:

            unique[
                key
            ] = item

    return list(
        unique.values()
    )


# =========================================================
# Pretty USD
# =========================================================

def format_usd(
    value
):
    """
    Human-readable USD formatting.
    """

    if value is None:
        return "N/A"

    absolute = abs(
        value
    )

    sign = (
        "-"
        if value < 0
        else ""
    )

    if absolute >= 1_000_000_000:

        return (
            f"{sign}$"
            f"{absolute / 1_000_000_000:.3f}B"
        )

    if absolute >= 1_000_000:

        return (
            f"{sign}$"
            f"{absolute / 1_000_000:.3f}M"
        )

    if absolute >= 1_000:

        return (
            f"{sign}$"
            f"{absolute / 1_000:.3f}K"
        )

    return (
        f"{sign}$"
        f"{absolute:.2f}"
    )


# =========================================================
# Print Results
# =========================================================

def print_financial_line_results(
    results
):

    print("\n==============================")
    print("FINANCIAL LINE EXTRACTION")
    print("==============================")

    if not results:

        print(
            "\nNo financial lines extracted."
        )

        return

    for item in results:

        print(
            f"\nTopic: "
            f"{item['topic']}"
        )

        print(
            f"Classification Level: "
            f"{item['classification_level']}"
        )

        print(
            f"Financial Line: "
            f"{item['financial_line']}"
        )

        print(
            f"Years Detected: "
            f"{item['years']}"
        )

        print(
            "Values:"
        )

        for year, data in (
            item[
                "values"
            ].items()
        ):

            print(
                f"  {year}: "
                f"{data['reported_value']} "
                f"({data['unit']})"
            )

        latest = (
            item[
                "latest_value"
            ]
        )

        if latest:

            print(
                f"Latest Year: "
                f"{item['latest_year']}"
            )

            print(
                f"Latest Reported Value: "
                f"{latest['reported_value']}"
            )

            print(
                f"Normalized USD: "
                f"{format_usd(latest['usd_value'])}"
            )


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "GOOGL"

    print("\n==============================")
    print(
        f"FINANCIAL LINE TEST: "
        f"{ticker}"
    )
    print("==============================")

    classifier_results = (
        classify_sec_filing(
            ticker=ticker,
            form_type="10-K"
        )
    )

    extracted = (
        extract_lines_from_results(
            classifier_results,
            minimum_level=2
        )
    )

    extracted = (
        deduplicate_extractions(
            extracted
        )
    )

    print(
        f"\nExtracted Lines: "
        f"{len(extracted)}"
    )

    print_financial_line_results(
        extracted
    )