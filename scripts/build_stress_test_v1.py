import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =========================================================
# NEWS INTELLIGENCE — FROZEN STRESS TEST v1 BUILDER
#
# IMPORTANT:
# - LOCAL FILES ONLY
# - ZERO API REQUESTS
# - DOES NOT CALL PERIGON
# - DOES NOT CALL GEMINI
# - DOES NOT MODIFY CORE PIPELINE
#
# Outputs:
#
# data/news/benchmarks/stress_test_v1/
#   ├── source_articles.json
#   ├── ground_truth.json
#   ├── manifest.json
#   └── README.md
#
# =========================================================


# =========================================================
# PATHS
# =========================================================

PERIGON_DIR = Path(
    "data/news/raw/perigon_benchmark_hunt"
)

NORMALIZED_DIR = Path(
    "data/news/normalized"
)

OUTPUT_DIR = Path(
    "data/news/benchmarks/stress_test_v1"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


SOURCE_OUTPUT = (
    OUTPUT_DIR
    / "source_articles.json"
)

GROUND_TRUTH_OUTPUT = (
    OUTPUT_DIR
    / "ground_truth.json"
)

MANIFEST_OUTPUT = (
    OUTPUT_DIR
    / "manifest.json"
)

README_OUTPUT = (
    OUTPUT_DIR
    / "README.md"
)


# =========================================================
# FROZEN PERIGON ARTICLE SELECTION
#
# These IDs were selected from the already-cached
# Perigon benchmark hunt.
#
# NO NEW API CALLS ARE REQUIRED.
# =========================================================

PERIGON_CASES = [

    # -----------------------------------------------------
    # ST01 — FED RATE DECISION
    # -----------------------------------------------------

    {
        "case_id":
            "ST01",

        "category":
            "macro_monetary_policy",

        "source_file":
            "macro_fed_policy.json",

        "article_id":
            "dfbdde28ff504f1ea3e07aa83382d063",

        "selection_reason":
            (
                "Clean Federal Reserve rate decision. "
                "Tests monetary-policy classification "
                "without a direct MAG7 company event."
            ),
    },


    # -----------------------------------------------------
    # ST02 — US CPI RELEASE
    # -----------------------------------------------------

    {
        "case_id":
            "ST02",

        "category":
            "macro_inflation",

        "source_file":
            "macro_us_inflation.json",

        "article_id":
            "0b7de0537f3b48d6bcfdc39bd0da406d",

        "selection_reason":
            (
                "Clean CPI data release containing headline "
                "inflation, core inflation and expectations."
            ),
    },


    # -----------------------------------------------------
    # ST03 — NVIDIA / CHINA EXPORT CONTROLS
    # -----------------------------------------------------

    {
        "case_id":
            "ST03",

        "category":
            "regulatory_export_controls",

        "source_file":
            "policy_ai_chip_controls.json",

        "article_id":
            "5964056afdd442d698678f1e5bbbfc3b",

        "selection_reason":
            (
                "Direct NVDA company subject combined with "
                "US export-control and China exposure."
            ),
    },


    # -----------------------------------------------------
    # ST04 — EXPORT CONTROL ENFORCEMENT / SMUGGLING
    # -----------------------------------------------------

    {
        "case_id":
            "ST04",

        "category":
            "regulatory_enforcement",

        "source_file":
            "policy_ai_chip_controls.json",

        "article_id":
            "c1099c00ab9449058b3e7776c401a008",

        "selection_reason":
            (
                "Tests distinction between Nvidia products "
                "being mentioned and Nvidia itself being the "
                "target of regulatory enforcement."
            ),
    },


    # -----------------------------------------------------
    # ST05 — TSMC PACKAGING CAPACITY
    # -----------------------------------------------------

    {
        "case_id":
            "ST05",

        "category":
            "semiconductor_supply_chain",

        "source_file":
            "semiconductor_tsmc_disruption.json",

        "article_id":
            "904695ffdc3e4a2c872e463cc9003011",

        "selection_reason":
            (
                "TSMC advanced-packaging capacity / supplier "
                "infrastructure case. Tests supply-chain context "
                "without inventing MAG7 relationships."
            ),
    },


    # -----------------------------------------------------
    # ST06 — COWOS / MAG7 DEPENDENCY
    # -----------------------------------------------------

    {
        "case_id":
            "ST06",

        "category":
            "advanced_packaging_dependency",

        "source_file":
            "semiconductor_tsmc_disruption.json",

        "article_id":
            "b4aea7ad2f90413ba77a7be85d1e09a1",

        "selection_reason":
            (
                "Microsoft / Nvidia / TSMC packaging-capacity case. "
                "Tests advanced-packaging exposure and relationship "
                "qualification."
            ),
    },


    # -----------------------------------------------------
    # ST07 — AWS OUTAGE
    # -----------------------------------------------------

    {
        "case_id":
            "ST07",

        "category":
            "cloud_infrastructure_outage",

        "source_file":
            "cloud_outage.json",

        "article_id":
            "331d0a271d0a4bfe9f3ec9ff1c8152d8",

        "selection_reason":
            (
                "Major AWS outage affecting multiple services. "
                "Tests operational event detection and AMZN relationship."
            ),
    },


    # -----------------------------------------------------
    # ST08 — AZURE / MICROSOFT OUTAGE
    # -----------------------------------------------------

    {
        "case_id":
            "ST08",

        "category":
            "cloud_infrastructure_outage",

        "source_file":
            "cloud_outage.json",

        "article_id":
            "9b901bc54a3a41458f5a01e53c0643a4",

        "selection_reason":
            (
                "Microsoft 365 / Azure outage caused by maintenance "
                "failure. Tests MSFT operational-event detection."
            ),
    },


    # -----------------------------------------------------
    # ST09 — HORMUZ BLOCKADE
    # -----------------------------------------------------

    {
        "case_id":
            "ST09",

        "category":
            "geopolitics_energy_shipping",

        "source_file":
            "geopolitics_hormuz.json",

        "article_id":
            "1f00f61492f14bfeb4580c1a678ca601",

        "selection_reason":
            (
                "Strait of Hormuz blockade event. Tests geopolitics, "
                "shipping, energy channels and event geography."
            ),
    },


    # -----------------------------------------------------
    # ST10 — HORMUZ TANKER ATTACK
    # -----------------------------------------------------

    {
        "case_id":
            "ST10",

        "category":
            "geopolitics_physical_disruption",

        "source_file":
            "geopolitics_hormuz.json",

        "article_id":
            "0e9eac2b14924963ad21b50afe8628dc",

        "selection_reason":
            (
                "Physical tanker incident in the Strait of Hormuz. "
                "Tests physical-event severity and geography."
            ),
    },
]


# =========================================================
# LOCAL CONTROL CASES
#
# These are intentionally taken from previous local samples.
#
# ST11 = commentary control
# ST12 = irrelevant-noise control
# =========================================================

LOCAL_CASES = [

    {
        "case_id":
            "ST11",

        "category":
            "company_commentary_control",

        "headline":
            (
                "Nvidia boss rejects AI extinction fears "
                "as 'doomsday narratives'"
            ),

        "selection_reason":
            (
                "Known NVIDIA commentary case. Expected to remain "
                "Low severity with no operational or fundamental change."
            ),
    },


    {
        "case_id":
            "ST12",

        "category":
            "irrelevant_noise_control",

        "headline":
            (
                "Missing Carnival Panorama passenger jumped "
                "overboard off Mexico's coast"
            ),

        "selection_reason":
            (
                "Known non-economic noise article. Expected to be "
                "rejected before LLM enrichment."
            ),
    },
]


# =========================================================
# GROUND TRUTH
#
# Important:
#
# HARD EXPECTATIONS:
#   objective behaviors suitable for pass/fail.
#
# SOFT EXPECTATIONS:
#   analyst-review expectations; should NOT automatically
#   fail the benchmark until policies are calibrated.
#
# The model / Gemini MUST NEVER receive this file as input.
# =========================================================

GROUND_TRUTH = {

    "ST01": {

        "description":
            "Federal Reserve interest-rate decision",

        "hard_expectations": {

            "should_surface":
                True,

            "should_be_noise_rejected":
                False,

            "event_family":
                "monetary_policy",

            "operational_event":
                False,

            "direct_mag7_tickers":
                [],

            "must_not_invent_company_relationship":
                True,
        },

        "soft_expectations": {

            "country":
                "United States",

            "severity":
                [
                    "Low",
                    "Medium",
                ],

            "channels":
                [
                    "monetary_policy",
                    "interest_rates",
                ],
        },
    },


    "ST02": {

        "description":
            "US consumer-price inflation release",

        "hard_expectations": {

            "should_surface":
                True,

            "should_be_noise_rejected":
                False,

            "event_family":
                "inflation_data",

            "operational_event":
                False,

            "direct_mag7_tickers":
                [],

            "must_not_invent_company_relationship":
                True,
        },

        "soft_expectations": {

            "country":
                "United States",

            "channels":
                [
                    "inflation",
                    "monetary_policy",
                ],

            "financial_impact_should_remain_unquantified":
                True,
        },
    },


    "ST03": {

        "description":
            "Nvidia customer controls under US export restrictions",

        "hard_expectations": {

            "should_surface":
                True,

            "should_be_noise_rejected":
                False,

            "event_family":
                "export_control",

            "required_direct_tickers":
                [
                    "NVDA",
                ],

            "must_preserve_regulatory_context":
                True,

            "must_not_infer_price_direction":
                True,
        },

        "soft_expectations": {

            "channels":
                [
                    "regulatory_policy",
                    "semiconductors",
                    "china_exposure",
                ],

            "severity":
                [
                    "Medium",
                    "High",
                ],
        },
    },


    "ST04": {

        "description":
            "US probe involving alleged Nvidia-chip smuggling",

        "hard_expectations": {

            "should_surface":
                True,

            "should_be_noise_rejected":
                False,

            "event_family":
                "regulatory_enforcement",

            "nvda_is_mentioned":
                True,

            "must_not_treat_nvda_as_target_of_probe_without_evidence":
                True,

            "must_not_infer_financial_impact":
                True,
        },

        "soft_expectations": {

            "channels":
                [
                    "regulatory_policy",
                    "export_control",
                    "semiconductors",
                ],
        },
    },


    "ST05": {

        "description":
            "TSMC advanced-packaging supplier infrastructure",

        "hard_expectations": {

            "should_be_noise_rejected":
                False,

            "event_family":
                "semiconductor_supply_chain",

            "must_not_invent_mag7_relationship":
                True,

            "must_not_infer_price_direction":
                True,
        },

        "soft_expectations": {

            "allowed_feed_states":
                [
                    "surface",
                    "background",
                ],

            "channels":
                [
                    "advanced_packaging",
                    "semiconductor_supply_chain",
                ],

            "country":
                "Taiwan",
        },
    },


    "ST06": {

        "description":
            "CoWoS capacity and MAG7 dependency",

        "hard_expectations": {

            "should_be_noise_rejected":
                False,

            "event_family":
                "advanced_packaging_capacity",

            "mentioned_tickers_expected":
                [
                    "MSFT",
                    "NVDA",
                ],

            "relationship_requires_evidence":
                True,

            "must_not_infer_price_direction":
                True,
        },

        "soft_expectations": {

            "channels":
                [
                    "advanced_packaging",
                    "semiconductor_supply_chain",
                    "ai_infrastructure",
                ],
        },
    },


    "ST07": {

        "description":
            "Major Amazon Web Services outage",

        "hard_expectations": {

            "should_surface":
                True,

            "should_be_noise_rejected":
                False,

            "event_family":
                "infrastructure_outage",

            "operational_event":
                True,

            "required_direct_tickers":
                [
                    "AMZN",
                ],

            "must_not_infer_price_direction":
                True,
        },

        "soft_expectations": {

            "severity":
                [
                    "Medium",
                    "High",
                ],

            "channels":
                [
                    "cloud_infrastructure",
                    "service_outage",
                ],
        },
    },


    "ST08": {

        "description":
            "Microsoft 365 / Azure outage",

        "hard_expectations": {

            "should_surface":
                True,

            "should_be_noise_rejected":
                False,

            "event_family":
                "infrastructure_outage",

            "operational_event":
                True,

            "required_direct_tickers":
                [
                    "MSFT",
                ],

            "must_not_infer_price_direction":
                True,
        },

        "soft_expectations": {

            "severity":
                [
                    "Medium",
                    "High",
                ],

            "channels":
                [
                    "cloud_infrastructure",
                    "service_outage",
                ],
        },
    },


    "ST09": {

        "description":
            "Strait of Hormuz blockade",

        "hard_expectations": {

            "should_surface":
                True,

            "should_be_noise_rejected":
                False,

            "event_family":
                "geopolitical_shipping_disruption",

            "location_expected":
                "Strait of Hormuz",

            "must_not_invent_mag7_direct_ticker":
                True,

            "must_not_infer_price_direction":
                True,
        },

        "soft_expectations": {

            "channels":
                [
                    "geopolitics",
                    "energy",
                    "shipping",
                    "oil",
                ],

            "severity":
                [
                    "Medium",
                    "High",
                ],
        },
    },


    "ST10": {

        "description":
            "Tanker hit in Strait of Hormuz",

        "hard_expectations": {

            "should_surface":
                True,

            "should_be_noise_rejected":
                False,

            "event_family":
                "physical_shipping_disruption",

            "operational_event":
                True,

            "location_expected":
                "Strait of Hormuz",

            "must_not_invent_mag7_direct_ticker":
                True,
        },

        "soft_expectations": {

            "channels":
                [
                    "geopolitics",
                    "shipping",
                    "energy",
                ],

            "severity":
                [
                    "Medium",
                    "High",
                ],
        },
    },


    "ST11": {

        "description":
            "Nvidia CEO AI-extinction commentary",

        "hard_expectations": {

            "should_surface":
                True,

            "should_be_noise_rejected":
                False,

            "event_family":
                "company_commentary",

            "required_direct_tickers":
                [
                    "NVDA",
                ],

            "operational_event":
                False,

            "fundamental_change_detected":
                False,

            "final_severity":
                "Low",

            "financial_impact_should_be_null":
                True,
        },

        "soft_expectations": {

            "research_priority":
                "Low",
        },
    },


    "ST12": {

        "description":
            "Irrelevant passenger incident",

        "hard_expectations": {

            "should_be_noise_rejected":
                True,

            "should_surface":
                False,

            "llm_should_be_skipped":
                True,

            "direct_mag7_tickers":
                [],
        },

        "soft_expectations": {},
    },
}


# =========================================================
# JSON HELPERS
# =========================================================

def load_json(
    path: Path
) -> Any:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def save_json(
    path: Path,
    data: Any
):

    path.write_text(

        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),

        encoding="utf-8"
    )


def canonical_hash(
    data: Any
) -> str:

    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":"
        ),
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        canonical
    ).hexdigest()


# =========================================================
# PERIGON ARTICLE FINDER
# =========================================================

def find_perigon_article(
    source_file: str,
    article_id: str
) -> Dict[str, Any]:

    path = (
        PERIGON_DIR
        / source_file
    )


    if not path.exists():

        raise FileNotFoundError(
            f"Missing Perigon cache: {path}"
        )


    data = load_json(
        path
    )


    articles = (

        data
        .get(
            "raw_response",
            {}
        )
        .get(
            "articles",
            []
        )
    )


    for article in articles:

        current_id = (

            article.get(
                "articleId"
            )

            or

            article.get(
                "_id"
            )

            or

            article.get(
                "id"
            )
        )


        if (
            current_id
            == article_id
        ):

            return article


    raise RuntimeError(
        f"Article {article_id} "
        f"not found in {path}"
    )


# =========================================================
# NORMALIZED FILE SCANNER
# =========================================================

def extract_article_list(
    data: Any
) -> List[Dict[str, Any]]:

    if isinstance(
        data,
        list
    ):

        return [
            x
            for x in data
            if isinstance(
                x,
                dict
            )
        ]


    if isinstance(
        data,
        dict
    ):

        for key in [
            "articles",
            "items",
            "data",
            "results",
        ]:

            value = data.get(
                key
            )

            if isinstance(
                value,
                list
            ):

                return [
                    x
                    for x in value
                    if isinstance(
                        x,
                        dict
                    )
                ]


    return []


def get_headline(
    article: Dict[str, Any]
) -> Optional[str]:

    return (

        article.get(
            "headline"
        )

        or

        article.get(
            "title"
        )
    )


def find_local_article(
    target_headline: str
):

    if not NORMALIZED_DIR.exists():

        raise FileNotFoundError(
            f"Missing normalized directory: "
            f"{NORMALIZED_DIR}"
        )


    # Search every local normalized JSON.
    # No API is used.

    for path in sorted(
        NORMALIZED_DIR.rglob(
            "*.json"
        )
    ):

        try:

            data = load_json(
                path
            )

        except Exception:

            continue


        for article in extract_article_list(
            data
        ):

            headline = get_headline(
                article
            )


            if (
                headline
                == target_headline
            ):

                return (
                    article,
                    path
                )


    raise RuntimeError(
        "Could not find local article:\n"
        f"{target_headline}"
    )


# =========================================================
# BUILD FROZEN SOURCE ARTICLES
# =========================================================

def build_source_articles():

    frozen_cases = []


    # -----------------------------------------------------
    # PERIGON CASES
    # -----------------------------------------------------

    for spec in PERIGON_CASES:

        article = find_perigon_article(

            source_file=
                spec["source_file"],

            article_id=
                spec["article_id"],
        )


        frozen_cases.append({

            "case_id":
                spec["case_id"],

            "category":
                spec["category"],

            "source_provider":
                "perigon",

            "source_file":
                str(
                    PERIGON_DIR
                    / spec["source_file"]
                ),

            "selection_reason":
                spec[
                    "selection_reason"
                ],

            "frozen_sha256":
                canonical_hash(
                    article
                ),

            "article":
                article,
        })


    # -----------------------------------------------------
    # LOCAL CONTROL CASES
    # -----------------------------------------------------

    for spec in LOCAL_CASES:

        (
            article,
            source_path
        ) = find_local_article(
            spec["headline"]
        )


        frozen_cases.append({

            "case_id":
                spec["case_id"],

            "category":
                spec["category"],

            "source_provider":
                "local_normalized_sample",

            "source_file":
                str(
                    source_path
                ),

            "selection_reason":
                spec[
                    "selection_reason"
                ],

            "frozen_sha256":
                canonical_hash(
                    article
                ),

            "article":
                article,
        })


    # -----------------------------------------------------
    # ORDER CASES
    # -----------------------------------------------------

    frozen_cases.sort(
        key=lambda x:
            x["case_id"]
    )


    return frozen_cases


# =========================================================
# VALIDATION
# =========================================================

def validate_cases(
    cases
):

    expected_ids = {
        f"ST{i:02d}"
        for i in range(
            1,
            13
        )
    }


    actual_ids = {
        c["case_id"]
        for c in cases
    }


    if (
        actual_ids
        != expected_ids
    ):

        missing = (
            expected_ids
            - actual_ids
        )

        extra = (
            actual_ids
            - expected_ids
        )

        raise RuntimeError(

            "Stress test case IDs invalid.\n"
            f"Missing: {sorted(missing)}\n"
            f"Extra: {sorted(extra)}"
        )


    # -----------------------------------------------------
    # DUPLICATE CONTENT CHECK
    # -----------------------------------------------------

    hashes = [
        c[
            "frozen_sha256"
        ]
        for c in cases
    ]


    if (
        len(hashes)
        != len(set(hashes))
    ):

        raise RuntimeError(
            "Duplicate frozen articles detected."
        )


    # -----------------------------------------------------
    # GROUND TRUTH CHECK
    # -----------------------------------------------------

    gt_ids = set(
        GROUND_TRUTH.keys()
    )


    if (
        gt_ids
        != expected_ids
    ):

        raise RuntimeError(
            "Ground truth case IDs "
            "do not match ST01-ST12."
        )


# =========================================================
# MANIFEST
# =========================================================

def build_manifest(
    cases
):

    return {

        "benchmark_name":
            "News Intelligence Stress Test v1",

        "benchmark_version":
            "1.0",

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "frozen":
            True,

        "api_requests_used_to_build":
            0,

        "case_count":
            len(cases),

        "policy": {

            "source_articles_are_frozen":
                True,

            "ground_truth_is_evaluation_only":
                True,

            "ground_truth_must_not_be_passed_to_llm":
                True,

            "future_versions_should_not_modify_v1_articles":
                True,

            "new_cases_require_new_benchmark_version":
                True,
        },

        "cases": [

            {

                "case_id":
                    case["case_id"],

                "category":
                    case["category"],

                "source_provider":
                    case[
                        "source_provider"
                    ],

                "source_file":
                    case[
                        "source_file"
                    ],

                "frozen_sha256":
                    case[
                        "frozen_sha256"
                    ],

                "headline":
                    get_headline(
                        case["article"]
                    ),

            }

            for case in cases
        ],
    }


# =========================================================
# README
# =========================================================

README_TEXT = """# News Intelligence Stress Test v1

This directory contains the frozen benchmark for the News Intelligence pipeline.

## Files

- `source_articles.json`
  Frozen input articles.

- `ground_truth.json`
  Human-defined expected behavior.

- `manifest.json`
  Benchmark metadata and SHA-256 hashes.

## Important

`ground_truth.json` is evaluation-only.

It must NEVER be passed to Gemini, another LLM, the normalizer, or the research pipeline as source context.

The benchmark articles must remain unchanged after v1 is frozen.

If the benchmark needs new or changed cases, create a new benchmark version instead of silently changing v1.

## Benchmark structure

ST01 — Federal Reserve rate decision

ST02 — US CPI release

ST03 — Nvidia / China export controls

ST04 — Export-control enforcement / smuggling

ST05 — TSMC packaging infrastructure

ST06 — CoWoS / MAG7 dependency

ST07 — AWS outage

ST08 — Azure / Microsoft outage

ST09 — Strait of Hormuz blockade

ST10 — Strait of Hormuz tanker incident

ST11 — Nvidia CEO commentary control

ST12 — Irrelevant noise control
"""


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=" * 80
    )

    print(
        "BUILDING FROZEN "
        "STRESS TEST v1"
    )

    print(
        "=" * 80
    )

    print(
        "API requests: 0"
    )

    print()


    cases = build_source_articles()


    validate_cases(
        cases
    )


    source_document = {

        "benchmark_name":
            "News Intelligence Stress Test v1",

        "version":
            "1.0",

        "frozen":
            True,

        "case_count":
            len(cases),

        "cases":
            cases,
    }


    ground_truth_document = {

        "benchmark_name":
            "News Intelligence Stress Test v1",

        "version":
            "1.0",

        "evaluation_only":
            True,

        "warning":
            (
                "Do not pass this file "
                "to Gemini or the "
                "research pipeline."
            ),

        "cases":
            GROUND_TRUTH,
    }


    manifest = build_manifest(
        cases
    )


    save_json(
        SOURCE_OUTPUT,
        source_document
    )


    save_json(
        GROUND_TRUTH_OUTPUT,
        ground_truth_document
    )


    save_json(
        MANIFEST_OUTPUT,
        manifest
    )


    README_OUTPUT.write_text(
        README_TEXT,
        encoding="utf-8"
    )


    print(
        "Cases frozen:",
        len(cases)
    )

    print()


    for case in cases:

        print(
            case["case_id"],
            "|",
            case["category"]
        )

        print(
            "   ",
            get_headline(
                case["article"]
            )
        )

        print(
            "    SHA256:",
            case[
                "frozen_sha256"
            ][:16]
            + "..."
        )

        print()


    print(
        "=" * 80
    )

    print(
        "OUTPUT"
    )

    print(
        "=" * 80
    )

    print(
        SOURCE_OUTPUT
    )

    print(
        GROUND_TRUTH_OUTPUT
    )

    print(
        MANIFEST_OUTPUT
    )

    print(
        README_OUTPUT
    )

    print()

    print(
        "SUCCESS — "
        "Stress Test v1 is frozen."
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()