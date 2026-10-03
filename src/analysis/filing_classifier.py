import json
import re
from pathlib import Path

from src.data.sec_filings import get_filing_text


# =========================================================
# Paths
# =========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
    .parent
)

KEYWORD_FILE = (
    BASE_DIR
    / "data"
    / "research_keywords.json"
)


# =========================================================
# Level Configuration
# =========================================================

LEVEL_PRIORITY = {
    "level_3_high_risk": 3,
    "level_2_materiality_candidate": 2,
    "level_1_relevant": 1,
    "level_0_context": 0
}


LEVEL_LABELS = {
    3: "HIGH RISK",
    2: "MATERIALITY",
    1: "RELEVANT",
    0: "CONTEXT"
}


# =========================================================
# Context Signals
# =========================================================

RISK_FACTOR_SIGNALS = [
    "risk factors",
    "could adversely affect",
    "may adversely affect",
    "may result in",
    "could result in",
    "we are exposed to the risk",
    "there can be no assurance"
]


HYPOTHETICAL_SIGNALS = [
    "may incur",
    "may experience",
    "may result",
    "may be required",
    "may recognize",
    "may record",
    "could incur",
    "could experience",
    "could result",
    "could recognize",
    "could record",
    "can result",
    "can be exposed",
    "can adversely affect",
    "might result",
    "might incur",
    "potential impairment",
    "potential write-down",
    "potential write-off",
    "could be subject to",
    "may be subject to",
    "if the company",
    "if we are unable",
    "future fluctuations",
    "future changes"
]


ACTUAL_EVENT_SIGNALS = [
    "recognized a",
    "recognized an",
    "recognized gains",
    "recognized losses",
    "recognized gain",
    "recognized loss",

    "recorded a",
    "recorded an",
    "recorded gains",
    "recorded losses",
    "recorded gain",
    "recorded loss",
    "recorded impairment",
    "recorded restructuring",

    "incurred a",
    "incurred an",
    "incurred charges",
    "incurred costs",
    "incurred expenses",

    "included a gain",
    "included a loss",
    "included gains",
    "included losses",

    "resulted in a gain",
    "resulted in a loss",
    "resulted in gains",
    "resulted in losses",

    "realized a gain",
    "realized a loss",
    "realized gains",
    "realized losses",

    "was recognized",
    "were recognized",
    "was recorded",
    "were recorded",

    "we recognized",
    "we recorded",
    "the company recognized",
    "the company recorded"
]


FINANCIAL_RESULT_SIGNALS = [
    "included net gains",
    "included gains",
    "included losses",
    "increased by",
    "decreased by",
    "primarily due to",
    "primarily related to",
    "for the year ended",
    "year ended",
    "other income (expense), net",
    "other income/(expense), net",
    "gain (loss) on equity securities",
    "gain (loss) on debt securities",
    "income before provision for income taxes",
    "income before income taxes"
]


OCI_SIGNALS = [
    "other comprehensive income",
    "accumulated other comprehensive income",
    "other comprehensive loss",
    "oci"
]


ACCOUNTING_POLICY_SIGNALS = [
    "accounting treatment",
    "accounting policy",
    "are recorded at fair value",
    "is recorded at fair value",
    "are measured at fair value",
    "is measured at fair value",
    "the company records",
    "the company recognizes",
    "we record",
    "we recognize",
    "accounted for under"
]


CUMULATIVE_BALANCE_SIGNALS = [
    "cumulative upward adjustments",
    "cumulative downward adjustments",
    "cumulative net gains",
    "carrying value",
    "as of december 31",
    "balance as of"
]


DEFERRED_TAX_SIGNALS = [
    "deferred tax assets",
    "deferred tax liabilities",
    "net deferred tax assets",
    "net deferred tax liabilities",
    "valuation allowance"
]


EARNINGS_IMPACT_SIGNALS = [
    "net income",
    "income before income taxes",
    "income before taxes",
    "pretax income",
    "pre-tax income",
    "other income",
    "other income (expense)",
    "other income/(expense)",
    "recognized in earnings",
    "recognized through earnings",
    "recognized in net income",
    "included in net income",
    "included in earnings"
]


INVESTMENT_SIGNALS = [
    "equity securities",
    "equity investments",
    "non-marketable equity",
    "marketable equity",
    "investments",
    "investment",
    "observable price",
    "measurement alternative"
]


DEBT_HEDGE_SIGNALS = [
    "term debt",
    "long-term debt",
    "fixed-rate notes",
    "interest rate swap",
    "interest rate swaps",
    "hedge accounting",
    "debt principal"
]


DERIVATIVE_HEDGE_SIGNALS = [
    "cash flow hedge",
    "hedge effectiveness",
    "derivative instruments",
    "foreign exchange risk",
    "interest rate risk"
]


# =========================================================
# Load Keyword Library
# =========================================================

def load_keyword_library(keyword_file=None):

    keyword_file = Path(keyword_file) if keyword_file is not None else KEYWORD_FILE

    if not keyword_file.exists():

        raise FileNotFoundError(
            f"Keyword file not found: "
            f"{keyword_file}"
        )

    with open(
        keyword_file,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# =========================================================
# Basic Text Helpers
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    return (
        text
        .lower()
        .replace("\n", " ")
        .strip()
    )


def contains_any(
    text,
    phrases
):

    normalized = (
        normalize_text(
            text
        )
    )

    for phrase in phrases:

        if phrase.lower() in normalized:
            return True

    return False


# =========================================================
# Amount Detection
# =========================================================

def extract_amounts(
    context
):
    """
    Extract financial-looking amounts.

    Examples:
        $24.1 billion
        $382 million
        24,080
        (1,043)

    Important:
    This only detects candidate amounts.
    It does NOT yet know which exact line
    the amount belongs to.
    """

    if not context:
        return []

    amounts = []

    patterns = [

        # $24.1 billion / $382 million
        r"\$\s*\d+(?:\.\d+)?\s*(?:billion|million|thousand)",

        # $24,080 / $540
        r"\$\s*\d{1,3}(?:,\d{3})+(?:\.\d+)?",

        # (1,043)
        r"\(\s*\d{1,3}(?:,\d{3})+\s*\)",

        # 24,080
        r"(?<![\d$])\d{1,3}(?:,\d{3})+(?!\d)"
    ]

    for pattern in patterns:

        matches = (
            re.findall(
                pattern,
                context,
                flags=re.IGNORECASE
            )
        )

        for match in matches:

            clean = (
                match
                .strip()
            )

            if clean not in amounts:
                amounts.append(clean)

    return amounts


# =========================================================
# Extract Keyword Contexts
# =========================================================

def extract_keyword_contexts(
    text,
    keyword,
    context_chars=400,
    max_contexts=5
):

    if not text:
        return []

    keyword_lower = (
        keyword.lower()
    )

    text_lower = (
        text.lower()
    )

    results = []

    start_position = 0

    while True:

        index = (
            text_lower.find(
                keyword_lower,
                start_position
            )
        )

        if index == -1:
            break

        context_start = max(
            0,
            index - context_chars
        )

        context_end = min(
            len(text),
            index
            + len(keyword)
            + context_chars
        )

        context = (
            text[
                context_start:
                context_end
            ]
            .strip()
        )

        results.append(
            {
                "position":
                    index,

                "context":
                    context
            }
        )

        if (
            len(results)
            >= max_contexts
        ):
            break

        start_position = (
            index
            + len(keyword_lower)
        )

    return results


# =========================================================
# Scan Keyword Families
# =========================================================

def scan_keyword_candidates(
    text,
    context_chars=400,
    max_contexts_per_keyword=5,
    keyword_library=None
):

    if keyword_library is None:
        keyword_library = load_keyword_library()

    candidates = []

    for level_name, level_data in (
        keyword_library.items()
    ):

        if not isinstance(
            level_data,
            dict
        ):
            continue

        for topic_name, topic_data in (
            level_data.items()
        ):

            if topic_name == "description":
                continue

            category = (
                topic_data.get(
                    "category"
                )
            )

            keywords = (
                topic_data.get(
                    "keywords",
                    []
                )
            )

            topic_matches = []
            matched_keywords = []

            for keyword in keywords:

                contexts = (
                    extract_keyword_contexts(
                        text=text,
                        keyword=keyword,
                        context_chars=context_chars,
                        max_contexts=(
                            max_contexts_per_keyword
                        )
                    )
                )

                if not contexts:
                    continue

                matched_keywords.append(
                    keyword
                )

                for context_item in contexts:

                    topic_matches.append(
                        {
                            "keyword":
                                keyword,

                            "position":
                                context_item[
                                    "position"
                                ],

                            "context":
                                context_item[
                                    "context"
                                ]
                        }
                    )

            if not topic_matches:
                continue

            candidates.append(
                {
                    "original_level":
                        LEVEL_PRIORITY.get(
                            level_name,
                            0
                        ),

                    "topic":
                        topic_name,

                    "category":
                        category,

                    "matched_keywords":
                        matched_keywords,

                    "matches":
                        topic_matches
                }
            )

    return candidates


# =========================================================
# Actual Event Detection
# =========================================================

def detect_actual_event(
    context
):

    hypothetical = (
        contains_any(
            context,
            HYPOTHETICAL_SIGNALS
        )
    )

    actual = (
        contains_any(
            context,
            ACTUAL_EVENT_SIGNALS
        )
    )

    if actual:

        return {
            "event_type":
                "actual_event",

            "actual":
                True,

            "hypothetical":
                hypothetical
        }

    if hypothetical:

        return {
            "event_type":
                "hypothetical",

            "actual":
                False,

            "hypothetical":
                True
        }

    return {
        "event_type":
            "unclear",

        "actual":
            False,

        "hypothetical":
            False
    }


# =========================================================
# Evidence Gate
# =========================================================

def evaluate_evidence_gate(
    context,
    event_info
):
    """
    Determine whether context contains
    enough evidence to preserve Level 2/3.

    Evidence can come from:

    1. Actual-event language
    2. Financial-result language
    3. Earnings-impact language
    4. Financial amount

    Context-only signals such as
    cumulative balances or deferred-tax
    tables weaken the evidence.
    """

    amounts = (
        extract_amounts(
            context
        )
    )

    actual_event = (
        event_info[
            "actual"
        ]
    )

    financial_result = (
        contains_any(
            context,
            FINANCIAL_RESULT_SIGNALS
        )
    )

    earnings_impact = (
        contains_any(
            context,
            EARNINGS_IMPACT_SIGNALS
        )
    )

    cumulative_balance = (
        contains_any(
            context,
            CUMULATIVE_BALANCE_SIGNALS
        )
    )

    deferred_tax = (
        contains_any(
            context,
            DEFERRED_TAX_SIGNALS
        )
    )

    accounting_policy = (
        contains_any(
            context,
            ACCOUNTING_POLICY_SIGNALS
        )
    )

    evidence_score = 0

    reasons = []

    if actual_event:

        evidence_score += 2

        reasons.append(
            "evidence_actual_event"
        )

    if financial_result:

        evidence_score += 2

        reasons.append(
            "evidence_financial_result"
        )

    if earnings_impact:

        evidence_score += 1

        reasons.append(
            "evidence_earnings_context"
        )

    if amounts:

        evidence_score += 1

        reasons.append(
            "evidence_amount_detected"
        )

    # -----------------------------------------------------
    # Negative Evidence
    # -----------------------------------------------------

    if cumulative_balance:

        evidence_score -= 2

        reasons.append(
            "cumulative_balance_context"
        )

    if deferred_tax:

        evidence_score -= 3

        reasons.append(
            "deferred_tax_context"
        )

    if (
        accounting_policy
        and not actual_event
        and not financial_result
    ):

        evidence_score -= 2

        reasons.append(
            "policy_only_context"
        )

    passed = (
        evidence_score >= 2
    )

    return {
        "passed":
            passed,

        "score":
            evidence_score,

        "amounts":
            amounts,

        "reasons":
            reasons
    }


# =========================================================
# Context Classification
# =========================================================

def classify_context(
    topic,
    category,
    original_level,
    context
):

    reasons = []

    context_lower = (
        normalize_text(
            context
        )
    )

    event_info = (
        detect_actual_event(
            context
        )
    )

    evidence = (
        evaluate_evidence_gate(
            context=context,
            event_info=event_info
        )
    )

    # =====================================================
    # Start Hard Cap
    # =====================================================

    hard_cap = (
        original_level
    )

    # -----------------------------------------------------
    # Risk / Hypothetical
    # -----------------------------------------------------

    if contains_any(
        context_lower,
        RISK_FACTOR_SIGNALS
    ):

        hard_cap = min(
            hard_cap,
            0
        )

        reasons.append(
            "risk_or_hypothetical_context"
        )

    if (
        event_info[
            "event_type"
        ]
        == "hypothetical"
    ):

        hard_cap = min(
            hard_cap,
            0
        )

        reasons.append(
            "hypothetical_not_actual_event"
        )

    # -----------------------------------------------------
    # OCI
    # -----------------------------------------------------

    if contains_any(
        context_lower,
        OCI_SIGNALS
    ):

        hard_cap = min(
            hard_cap,
            1
        )

        reasons.append(
            "oci_not_direct_net_income"
        )

    # -----------------------------------------------------
    # Debt Hedge
    # -----------------------------------------------------

    if (
        topic
        in {
            "fair_value_remeasurement",
            "unrealized_gains",
            "derivatives"
        }

        and contains_any(
            context_lower,
            DEBT_HEDGE_SIGNALS
        )
    ):

        hard_cap = min(
            hard_cap,
            0
        )

        reasons.append(
            "debt_hedge_context"
        )

    # -----------------------------------------------------
    # Derivative / FX Hedge
    # -----------------------------------------------------

    if (
        category
        in {
            "derivative_income",
            "derivative_valuation",
            "foreign_exchange"
        }

        and contains_any(
            context_lower,
            DERIVATIVE_HEDGE_SIGNALS
        )
    ):

        hard_cap = min(
            hard_cap,
            1
        )

        reasons.append(
            "hedging_policy_context"
        )

    # -----------------------------------------------------
    # Accounting Policy Only
    # -----------------------------------------------------

    if (
        contains_any(
            context_lower,
            ACCOUNTING_POLICY_SIGNALS
        )

        and not event_info[
            "actual"
        ]

        and not contains_any(
            context_lower,
            FINANCIAL_RESULT_SIGNALS
        )
    ):

        hard_cap = min(
            hard_cap,
            1
        )

        reasons.append(
            "accounting_policy_context"
        )

    # -----------------------------------------------------
    # Cumulative Balance
    # -----------------------------------------------------

    if contains_any(
        context_lower,
        CUMULATIVE_BALANCE_SIGNALS
    ):

        hard_cap = min(
            hard_cap,
            1
        )

        reasons.append(
            "cumulative_not_current_period_event"
        )

    # -----------------------------------------------------
    # Deferred Tax
    # -----------------------------------------------------

    if contains_any(
        context_lower,
        DEFERRED_TAX_SIGNALS
    ):

        hard_cap = min(
            hard_cap,
            1
        )

        reasons.append(
            "deferred_tax_not_operating_event"
        )

    # =====================================================
    # Evidence Gate for Level 2 / 3
    # =====================================================

    if (
        original_level >= 2
        and not evidence[
            "passed"
        ]
    ):

        hard_cap = min(
            hard_cap,
            1
        )

        reasons.append(
            "failed_evidence_gate"
        )

    # =====================================================
    # Positive Research Signals
    # =====================================================

    investment_related = (
        contains_any(
            context_lower,
            INVESTMENT_SIGNALS
        )
    )

    earnings_related = (
        contains_any(
            context_lower,
            EARNINGS_IMPACT_SIGNALS
        )
    )

    if (
        original_level >= 2
        and investment_related
        and earnings_related
    ):

        reasons.append(
            "investment_and_earnings_context"
        )

    if (
        original_level >= 2
        and event_info[
            "actual"
        ]
    ):

        reasons.append(
            "actual_event_language"
        )

    # =====================================================
    # Final
    # =====================================================

    final_level = (
        min(
            original_level,
            hard_cap
        )
    )

    if final_level >= 2:

        status = (
            "research_hit"
        )

    elif final_level == 1:

        status = (
            "relevant_context"
        )

    else:

        status = (
            "context_only"
        )

    return {
        "final_level":
            final_level,

        "hard_cap":
            hard_cap,

        "status":
            status,

        "event_type":
            event_info[
                "event_type"
            ],

        "evidence_passed":
            evidence[
                "passed"
            ],

        "evidence_score":
            evidence[
                "score"
            ],

        "amounts":
            evidence[
                "amounts"
            ],

        "reasons":
            reasons
            + evidence[
                "reasons"
            ]
    }


# =========================================================
# Validate Candidate
# =========================================================

def validate_candidate(
    candidate
):

    validated_matches = []

    highest_level = 0

    for match in (
        candidate[
            "matches"
        ]
    ):

        classification = (
            classify_context(
                topic=(
                    candidate[
                        "topic"
                    ]
                ),

                category=(
                    candidate[
                        "category"
                    ]
                ),

                original_level=(
                    candidate[
                        "original_level"
                    ]
                ),

                context=(
                    match[
                        "context"
                    ]
                )
            )
        )

        final_level = (
            classification[
                "final_level"
            ]
        )

        highest_level = max(
            highest_level,
            final_level
        )

        validated_matches.append(
            {
                **match,

                "final_level":
                    final_level,

                "hard_cap":
                    classification[
                        "hard_cap"
                    ],

                "status":
                    classification[
                        "status"
                    ],

                "event_type":
                    classification[
                        "event_type"
                    ],

                "evidence_passed":
                    classification[
                        "evidence_passed"
                    ],

                "evidence_score":
                    classification[
                        "evidence_score"
                    ],

                "amounts":
                    classification[
                        "amounts"
                    ],

                "reasons":
                    classification[
                        "reasons"
                    ]
            }
        )

    confirmed_hits = [
        item
        for item
        in validated_matches
        if item[
            "final_level"
        ] >= 2
    ]

    actual_hits = [
        item
        for item
        in confirmed_hits
        if item[
            "event_type"
        ] == "actual_event"
    ]

    evidence_hits = [
        item
        for item
        in confirmed_hits
        if item[
            "evidence_passed"
        ]
    ]

    return {
        **candidate,

        "final_level":
            highest_level,

        "confirmed_hit_count":
            len(
                confirmed_hits
            ),

        "actual_event_count":
            len(
                actual_hits
            ),

        "evidence_hit_count":
            len(
                evidence_hits
            ),

        "validated_matches":
            validated_matches
    }


# =========================================================
# Full Filing Classification
# =========================================================

def classify_filing_text(
    text,
    keyword_library=None
):

    candidates = (
        scan_keyword_candidates(
            text, keyword_library=keyword_library
        )
    )

    results = []

    for candidate in candidates:

        results.append(
            validate_candidate(
                candidate
            )
        )

    return results


# =========================================================
# SEC Filing Wrapper
# =========================================================

def classify_sec_filing(
    ticker,
    form_type="10-K",
    keyword_file=None
):
    # Existing scoring callers retain their frozen vocabulary. Evidence callers
    # explicitly pass KEYWORD_FILE to use the expanded user-supplied library.
    if keyword_file is None:
        keyword_file = BASE_DIR / "data" / "research_keywords_legacy.json"

    filing_text = (
        get_filing_text(
            ticker,
            form_type=form_type
        )
    )

    if filing_text is None:
        return []

    return classify_filing_text(
        filing_text, keyword_library=load_keyword_library(keyword_file)
    )


# =========================================================
# Summary
# =========================================================

def summarize_results(
    results
):

    summary = {
        3: {
            "candidate_topics": 0,
            "final_topics": 0,
            "confirmed_hits": 0,
            "actual_events": 0,
            "evidence_hits": 0
        },

        2: {
            "candidate_topics": 0,
            "final_topics": 0,
            "confirmed_hits": 0,
            "actual_events": 0,
            "evidence_hits": 0
        },

        1: {
            "candidate_topics": 0,
            "final_topics": 0,
            "confirmed_hits": 0,
            "actual_events": 0,
            "evidence_hits": 0
        },

        0: {
            "candidate_topics": 0,
            "final_topics": 0,
            "confirmed_hits": 0,
            "actual_events": 0,
            "evidence_hits": 0
        }
    }

    for item in results:

        original_level = (
            item[
                "original_level"
            ]
        )

        final_level = (
            item[
                "final_level"
            ]
        )

        summary[
            original_level
        ][
            "candidate_topics"
        ] += 1

        summary[
            final_level
        ][
            "final_topics"
        ] += 1

        summary[
            final_level
        ][
            "confirmed_hits"
        ] += (
            item[
                "confirmed_hit_count"
            ]
        )

        summary[
            final_level
        ][
            "actual_events"
        ] += (
            item[
                "actual_event_count"
            ]
        )

        summary[
            final_level
        ][
            "evidence_hits"
        ] += (
            item[
                "evidence_hit_count"
            ]
        )

    return summary


# =========================================================
# Print Summary
# =========================================================

def print_summary(
    summary
):

    print("\n==============================")
    print("CLASSIFIER V2.3 SUMMARY")
    print("==============================")

    for level in [
        3,
        2,
        1,
        0
    ]:

        data = (
            summary[
                level
            ]
        )

        print(
            f"\nLEVEL {level} - "
            f"{LEVEL_LABELS[level]}"
        )

        print(
            "Candidate Topics: "
            f"{data['candidate_topics']}"
        )

        print(
            "Final Topics: "
            f"{data['final_topics']}"
        )

        print(
            "Confirmed Hits: "
            f"{data['confirmed_hits']}"
        )

        print(
            "Confirmed Actual Events: "
            f"{data['actual_events']}"
        )

        print(
            "Evidence-Passed Hits: "
            f"{data['evidence_hits']}"
        )


# =========================================================
# Print Confirmed Research Results
# =========================================================

def print_confirmed_results(
    results,
    minimum_level=2
):

    print("\n==============================")
    print("CONFIRMED RESEARCH RESULTS")
    print("==============================")

    found = False

    sorted_results = sorted(
        results,
        key=lambda item: (
            item[
                "final_level"
            ],
            item[
                "evidence_hit_count"
            ],
            item[
                "actual_event_count"
            ]
        ),
        reverse=True
    )

    for item in sorted_results:

        if (
            item[
                "final_level"
            ]
            < minimum_level
        ):
            continue

        found = True

        print(
            f"\nTopic: "
            f"{item['topic']}"
        )

        print(
            f"Category: "
            f"{item['category']}"
        )

        print(
            f"Original Level: "
            f"{item['original_level']}"
        )

        print(
            f"Final Level: "
            f"{item['final_level']}"
        )

        print(
            f"Confirmed Hits: "
            f"{item['confirmed_hit_count']}"
        )

        print(
            f"Actual Events: "
            f"{item['actual_event_count']}"
        )

        print(
            f"Evidence Hits: "
            f"{item['evidence_hit_count']}"
        )

        print(
            "Matched Keywords: "
            + ", ".join(
                item[
                    "matched_keywords"
                ]
            )
        )

        confirmed_matches = [
            match
            for match
            in item[
                "validated_matches"
            ]
            if match[
                "final_level"
            ] >= minimum_level
        ]

        for index, match in (
            enumerate(
                confirmed_matches[:3],
                start=1
            )
        ):

            print(
                f"\nContext {index}:"
            )

            print(
                match[
                    "context"
                ]
            )

            print(
                f"\nEvent Type: "
                f"{match['event_type']}"
            )

            print(
                f"Hard Cap: "
                f"{match['hard_cap']}"
            )

            print(
                f"Evidence Passed: "
                f"{match['evidence_passed']}"
            )

            print(
                f"Evidence Score: "
                f"{match['evidence_score']}"
            )

            if match[
                "amounts"
            ]:

                print(
                    "Amounts Detected: "
                    + ", ".join(
                        match[
                            "amounts"
                        ][:10]
                    )
                )

            if match[
                "reasons"
            ]:

                print(
                    "Reasons:"
                )

                for reason in (
                    match[
                        "reasons"
                    ]
                ):

                    print(
                        f"- {reason}"
                    )

    if not found:

        print(
            "\nNo confirmed "
            "Level 2 or Level 3 results."
        )


# =========================================================
# Print Downgraded Candidates
# =========================================================

def print_downgraded_results(
    results
):

    print("\n==============================")
    print("DOWNGRADED CANDIDATES")
    print("==============================")

    found = False

    for item in results:

        if (
            item[
                "original_level"
            ] < 2
        ):
            continue

        if (
            item[
                "final_level"
            ] >= 2
        ):
            continue

        found = True

        print(
            f"\nTopic: "
            f"{item['topic']}"
        )

        print(
            f"Original Level: "
            f"{item['original_level']}"
        )

        print(
            f"Final Level: "
            f"{item['final_level']}"
        )

        reason_set = set()
        event_types = set()
        hard_caps = set()
        evidence_scores = set()

        for match in (
            item[
                "validated_matches"
            ]
        ):

            event_types.add(
                match[
                    "event_type"
                ]
            )

            hard_caps.add(
                match[
                    "hard_cap"
                ]
            )

            evidence_scores.add(
                match[
                    "evidence_score"
                ]
            )

            for reason in (
                match[
                    "reasons"
                ]
            ):

                reason_set.add(
                    reason
                )

        print(
            "Event Types: "
            + ", ".join(
                sorted(
                    event_types
                )
            )
        )

        print(
            "Hard Caps Seen: "
            + ", ".join(
                str(value)
                for value
                in sorted(
                    hard_caps
                )
            )
        )

        print(
            "Evidence Scores Seen: "
            + ", ".join(
                str(value)
                for value
                in sorted(
                    evidence_scores
                )
            )
        )

        if reason_set:

            print(
                "Reasons:"
            )

            for reason in sorted(
                reason_set
            ):

                print(
                    f"- {reason}"
                )

    if not found:

        print(
            "\nNo downgraded candidates."
        )


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "GOOGL"

    print("\n==============================")
    print(
        f"FILING CLASSIFIER V2.3: "
        f"{ticker}"
    )
    print("==============================")

    results = (
        classify_sec_filing(
            ticker=ticker,
            form_type="10-K"
        )
    )

    print(
        f"\nKeyword Families Hit: "
        f"{len(results)}"
    )

    summary = (
        summarize_results(
            results
        )
    )

    print_summary(
        summary
    )

    print_confirmed_results(
        results,
        minimum_level=2
    )

    print_downgraded_results(
        results
    )