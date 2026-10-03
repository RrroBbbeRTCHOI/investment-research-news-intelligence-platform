import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Tuple

import requests
from dotenv import load_dotenv


# =========================================================
# NEWS INTELLIGENCE — PERIGON BENCHMARK HUNT v1.1
#
# Goal:
#   Build a high-signal frozen candidate pool for Stress Test v1
#   while protecting a small monthly API quota.
#
# Quota behavior:
#   - 6 benchmark categories
#   - maximum 6 live requests per run
#   - 25 candidates per request
#   - successful responses are cached
#   - reruns without --refresh use cache
#   - no automatic retries
#
# This script is standalone.
# It does NOT alter the core V3.x research pipeline.
# =========================================================


# =========================================================
# ENV
# =========================================================

load_dotenv(".env")

API_KEY = os.getenv("PERIGON_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "PERIGON_API_KEY not found in .env"
    )


# =========================================================
# CONFIG
# =========================================================

BASE_URL = "https://api.perigon.io/v1/articles/all"

HEADERS = {
    "x-api-key": API_KEY
}

RAW_DIR = Path(
    "data/news/raw/perigon_benchmark_hunt"
)

RAW_DIR.mkdir(
    parents=True,
    exist_ok=True
)

MANIFEST_PATH = (
    RAW_DIR / "manifest.json"
)

# Maximum API calls allowed by THIS script per run.
MAX_LIVE_REQUESTS = 6

# One request can return many candidate articles.
RESULTS_PER_QUERY = 25

# Conservative recent-history window.
NOW_UTC = datetime.now(
    timezone.utc
)

FROM_DATE = (
    NOW_UTC - timedelta(days=90)
).date().isoformat()

TO_DATE = (
    NOW_UTC.date().isoformat()
)


# =========================================================
# QUALITY FILTERS
# =========================================================

# We want hard-news / event-oriented benchmark candidates.
#
# These are excluded only during benchmark hunting.
# They do NOT change the normal production pipeline.

EXCLUDE_LABELS = [
    "Opinion",
    "Paid News",
    "Non-news",
    "Press Release",
    "Roundup",
    "Low Content",
    "Synthetic",
]


# =========================================================
# BENCHMARK HUNT QUERIES
# =========================================================
#
# Strategy:
#
# 1. One query = one research mechanism.
# 2. Queries are event-oriented, not simple company searches.
# 3. Use higher-quality source groups.
# 4. Sort by relevance.
# 5. Exclude reprints and low-signal formats.
#
# 6 queries = maximum 6 API requests.
# =========================================================

QUERIES: Dict[str, Dict[str, Any]] = {

    # -----------------------------------------------------
    # 1. FED / MONETARY POLICY
    # -----------------------------------------------------

    "macro_fed_policy": {

        "q": (
            '"Federal Reserve" AND '
            '("rate decision" OR '
            '"rate cut" OR '
            '"rate hike" OR '
            '"interest rates" OR '
            '"Federal Open Market Committee")'
        ),

        "source_groups": [
            "top25finance",
            "top100",
        ],

        "purpose": (
            "Monetary-policy event classification "
            "and broad-market transmission."
        ),
    },


    # -----------------------------------------------------
    # 2. US INFLATION / CPI
    # -----------------------------------------------------

    "macro_us_inflation": {

        "q": (
            '("US CPI" OR '
            '"U.S. CPI" OR '
            '"consumer price index" OR '
            '"consumer prices") '
            'AND inflation'
        ),

        "source_groups": [
            "top25finance",
            "top100",
        ],

        "purpose": (
            "Macro data-release classification "
            "and non-company event handling."
        ),
    },


    # -----------------------------------------------------
    # 3. AI CHIP EXPORT CONTROLS / CHINA
    # -----------------------------------------------------

    "policy_ai_chip_controls": {

        "q": (
            '(Nvidia OR NVIDIA OR '
            'semiconductor OR "AI chip") '
            'AND '
            '("export controls" OR '
            '"export restrictions" OR '
            '"chip restrictions") '
            'AND China'
        ),

        "source_groups": [
            "top25finance",
            "top50tech",
            "top100",
        ],

        "purpose": (
            "Regulatory/political policy, "
            "China exposure, and direct-vs-indirect "
            "semiconductor relevance."
        ),
    },


    # -----------------------------------------------------
    # 4. TSMC / SEMICONDUCTOR DISRUPTION
    # -----------------------------------------------------

    "semiconductor_tsmc_disruption": {

        "q": (
            'TSMC AND '
            '(earthquake OR '
            'outage OR '
            'disruption OR '
            'shutdown OR '
            '"production halt" OR '
            'packaging OR '
            'CoWoS)'
        ),

        "source_groups": [
            "top25finance",
            "top50tech",
            "top100",
        ],

        "purpose": (
            "Supply-chain and semiconductor "
            "dependency stress test."
        ),
    },


    # -----------------------------------------------------
    # 5. CLOUD OUTAGE
    # -----------------------------------------------------

    "cloud_outage": {

        "q": (
            '(AWS OR '
            '"Amazon Web Services" OR '
            'Azure OR '
            '"Google Cloud") '
            'AND '
            '(outage OR '
            'disruption OR '
            'unavailable OR '
            'downtime)'
        ),

        "source_groups": [
            "top50tech",
            "top100",
        ],

        "purpose": (
            "Cloud infrastructure outage, "
            "direct company event, "
            "and downstream exposure."
        ),
    },


    # -----------------------------------------------------
    # 6. HORMUZ / OIL / SHIPPING
    # -----------------------------------------------------

    "geopolitics_hormuz": {

        "q": (
            '"Strait of Hormuz" AND '
            '(oil OR '
            'shipping OR '
            'blockade OR '
            'reopen OR '
            'disruption OR '
            'tanker)'
        ),

        "source_groups": [
            "top25finance",
            "top100",
        ],

        "purpose": (
            "Geopolitical / energy / shipping "
            "transmission and event geography."
        ),
    },
}


# =========================================================
# HELPERS
# =========================================================

def safe_name(
    name: str
) -> str:

    return (
        name
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )


def cache_path(
    query_name: str
) -> Path:

    return (
        RAW_DIR
        / f"{safe_name(query_name)}.json"
    )


def load_cache(
    path: Path
):

    if not path.exists():
        return None

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


def article_domain(
    article: Dict[str, Any]
) -> str:

    source = (
        article.get("source")
        or {}
    )

    if isinstance(
        source,
        dict
    ):
        return (
            source.get("domain")
            or ""
        )

    return ""


def article_id(
    article: Dict[str, Any]
) -> str:

    return (
        article.get("articleId")
        or article.get("_id")
        or article.get("id")
        or ""
    )


# =========================================================
# REQUEST PARAMETERS
# =========================================================

def build_params(
    spec: Dict[str, Any]
) -> Dict[str, Any]:

    return {

        "q":
            spec["q"],

        "language":
            "en",

        # Multiple source groups.
        "sourceGroup":
            spec["source_groups"],

        # Remove low-value formats.
        "excludeLabel":
            EXCLUDE_LABELS,

        # Historical range.
        "from":
            FROM_DATE,

        "to":
            TO_DATE,

        # Benchmark hunting:
        # relevance matters more than freshness.
        "sortBy":
            "relevance",

        # Reduce duplicate syndicated articles.
        "showReprints":
            "false",

        "showNumResults":
            "true",

        "page":
            0,

        "size":
            RESULTS_PER_QUERY,
    }


# =========================================================
# FETCH ONE QUERY
# =========================================================

def fetch_one(
    query_name: str,
    spec: Dict[str, Any],
    refresh: bool,
) -> Tuple[
    Dict[str, Any],
    bool
]:

    path = cache_path(
        query_name
    )

    # -----------------------------------------------------
    # CACHE FIRST
    # -----------------------------------------------------

    if (
        path.exists()
        and not refresh
    ):

        cached = load_cache(
            path
        )

        print(
            "=" * 92
        )

        print(
            "USING CACHE"
        )

        print(
            "QUERY:",
            query_name
        )

        print(
            "FILE :",
            path
        )

        print(
            "=" * 92
        )

        return (
            cached,
            False
        )


    # -----------------------------------------------------
    # LIVE REQUEST
    # -----------------------------------------------------

    params = build_params(
        spec
    )

    print(
        "=" * 92
    )

    print(
        "CALLING PERIGON"
    )

    print(
        "QUERY NAME   :",
        query_name
    )

    print(
        "PURPOSE      :",
        spec["purpose"]
    )

    print(
        "QUERY        :",
        spec["q"]
    )

    print(
        "SOURCE GROUPS:",
        ", ".join(
            spec["source_groups"]
        )
    )

    print(
        "WINDOW       :",
        FROM_DATE,
        "to",
        TO_DATE
    )

    print(
        "=" * 92
    )


    response = requests.get(

        BASE_URL,

        headers=HEADERS,

        params=params,

        timeout=45,
    )


    print(
        "HTTP STATUS:",
        response.status_code
    )


    if (
        response.status_code
        != 200
    ):

        print()

        print(
            "API RESPONSE:"
        )

        print(
            response.text[:3000]
        )


    response.raise_for_status()


    raw = response.json()


    wrapped = {

        "_ingestion": {

            "provider":
                "perigon",

            "endpoint":
                BASE_URL,

            "query_name":
                query_name,

            "purpose":
                spec["purpose"],

            "fetched_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "request_params":
                params,
        },

        "raw_response":
            raw,
    }


    save_json(
        path,
        wrapped
    )


    print(
        "SAVED:",
        path
    )


    return (
        wrapped,
        True
    )


# =========================================================
# ARTICLE EXTRACTION
# =========================================================

def extract_articles(
    wrapped: Dict[str, Any]
) -> List[
    Dict[str, Any]
]:

    raw = (
        wrapped.get(
            "raw_response"
        )
        or {}
    )

    articles = (
        raw.get("articles")
        or []
    )

    if not isinstance(
        articles,
        list
    ):
        return []

    return articles


# =========================================================
# TERMINAL PREVIEW
# =========================================================

def print_preview(
    query_name: str,
    wrapped: Dict[str, Any]
):

    raw = (
        wrapped.get(
            "raw_response"
        )
        or {}
    )

    articles = extract_articles(
        wrapped
    )


    print()

    print(
        f"[{query_name}] "
        f"numResults:",
        raw.get("numResults")
    )

    print(
        f"[{query_name}] "
        f"returned  :",
        len(articles)
    )


    # Show first 10 only.
    # Full 25 remain stored in JSON.

    for i, article in enumerate(
        articles[:10],
        1
    ):

        labels = (
            article.get("labels")
            or article.get("label")
        )

        print()

        print(
            f"{i:>2}. "
            f"{article.get('title')}"
        )

        print(
            "    DOMAIN :",
            article_domain(article)
        )

        print(
            "    DATE   :",
            article.get("pubDate")
        )

        print(
            "    ID     :",
            article_id(article)
        )

        print(
            "    CLUSTER:",
            article.get("clusterId")
        )

        print(
            "    LABELS :",
            labels
        )

        print(
            "    URL    :",
            article.get("url")
        )


# =========================================================
# MANIFEST
# =========================================================

def build_manifest(
    results: Dict[
        str,
        Dict[str, Any]
    ]
):

    seen_ids = set()

    candidates = []


    for (
        query_name,
        wrapped
    ) in results.items():

        ingestion = (
            wrapped.get(
                "_ingestion"
            )
            or {}
        )

        purpose = (
            ingestion.get(
                "purpose"
            )
        )


        for article in extract_articles(
            wrapped
        ):

            aid = article_id(
                article
            )

            url = article.get(
                "url"
            )


            # Prefer Perigon article ID.
            # Fall back to URL.
            dedupe_key = (
                aid
                or url
            )


            if not dedupe_key:
                continue


            if (
                dedupe_key
                in seen_ids
            ):
                continue


            seen_ids.add(
                dedupe_key
            )


            candidates.append({

                "query_name":
                    query_name,

                "purpose":
                    purpose,

                "article_id":
                    aid,

                "cluster_id":
                    article.get(
                        "clusterId"
                    ),

                "title":
                    article.get(
                        "title"
                    ),

                "pubDate":
                    article.get(
                        "pubDate"
                    ),

                "domain":
                    article_domain(
                        article
                    ),

                "labels":
                    (
                        article.get(
                            "labels"
                        )
                        or article.get(
                            "label"
                        )
                    ),

                "reprint":
                    article.get(
                        "reprint"
                    ),

                "url":
                    url,
            })


    manifest = {

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "provider":
            "perigon",

        "benchmark_hunt_version":
            "v1.1",

        "query_count":
            len(results),

        "candidate_count_after_cross_query_dedupe":
            len(candidates),

        "date_window": {

            "from":
                FROM_DATE,

            "to":
                TO_DATE,
        },

        "quality_policy": {

            "excluded_labels":
                EXCLUDE_LABELS,

            "show_reprints":
                False,
        },

        "candidates":
            candidates,
    }


    save_json(
        MANIFEST_PATH,
        manifest
    )


    print()

    print(
        "=" * 92
    )

    print(
        "MANIFEST"
    )

    print(
        "=" * 92
    )

    print(
        "Unique candidate articles:",
        len(candidates)
    )

    print(
        "Saved:",
        MANIFEST_PATH
    )


# =========================================================
# MAIN
# =========================================================

def main():

    parser = argparse.ArgumentParser(

        description=(
            "Quota-safe Perigon "
            "benchmark candidate hunter."
        )
    )


    parser.add_argument(

        "--refresh",

        action="store_true",

        help=(
            "Force live API calls even "
            "when cache exists. "
            "This consumes monthly quota."
        ),
    )


    parser.add_argument(

        "--dry-run",

        action="store_true",

        help=(
            "Print planned queries "
            "without making API calls."
        ),
    )


    args = parser.parse_args()


    print(
        "=" * 92
    )

    print(
        "NEWS INTELLIGENCE — "
        "PERIGON BENCHMARK HUNT v1.1"
    )

    print(
        "=" * 92
    )

    print(
        "Queries configured :",
        len(QUERIES)
    )

    print(
        "Max live requests  :",
        MAX_LIVE_REQUESTS
    )

    print(
        "Results per request:",
        RESULTS_PER_QUERY
    )

    print(
        "Date window        :",
        FROM_DATE,
        "to",
        TO_DATE
    )

    print(
        "Sort               :",
        "relevance"
    )

    print(
        "Exclude labels     :",
        ", ".join(
            EXCLUDE_LABELS
        )
    )

    print(
        "Refresh            :",
        args.refresh
    )

    print()


    # -----------------------------------------------------
    # HARD REQUEST BUDGET CHECK
    # -----------------------------------------------------

    if (
        len(QUERIES)
        > MAX_LIVE_REQUESTS
    ):

        raise RuntimeError(

            f"Configured queries "
            f"({len(QUERIES)}) exceed "
            f"live request budget "
            f"({MAX_LIVE_REQUESTS})."
        )


    # -----------------------------------------------------
    # DRY RUN
    # -----------------------------------------------------

    if args.dry_run:

        for (
            name,
            spec
        ) in QUERIES.items():

            print(
                name
            )

            print(
                "  purpose      :",
                spec["purpose"]
            )

            print(
                "  source groups:",
                ", ".join(
                    spec["source_groups"]
                )
            )

            print(
                "  query        :",
                spec["q"]
            )

            print()


        print(
            "DRY RUN ONLY — "
            "0 API requests used."
        )

        return


    # -----------------------------------------------------
    # FETCH
    # -----------------------------------------------------

    results: Dict[
        str,
        Dict[str, Any]
    ] = {}


    live_requests_used = 0


    for (
        query_name,
        spec
    ) in QUERIES.items():

        path = cache_path(
            query_name
        )


        will_use_live = (

            args.refresh

            or

            not path.exists()
        )


        # ---------------------------------------------
        # QUOTA GUARD
        # ---------------------------------------------

        if (
            will_use_live
            and
            live_requests_used
            >= MAX_LIVE_REQUESTS
        ):

            print()

            print(
                "REQUEST BUDGET REACHED."
            )

            print(
                "Stopping before any "
                "extra API request."
            )

            break


        try:

            (
                wrapped,
                used_live
            ) = fetch_one(

                query_name=
                    query_name,

                spec=
                    spec,

                refresh=
                    args.refresh,
            )


            results[
                query_name
            ] = wrapped


            if used_live:

                live_requests_used += 1


            print_preview(
                query_name,
                wrapped
            )


        except requests.HTTPError as exc:

            # Failed HTTP requests may
            # still count provider-side.

            if will_use_live:

                live_requests_used += 1


            print()

            print(
                "HTTP ERROR:",
                repr(exc)
            )

            print(
                "NO RETRY — "
                "protecting monthly quota."
            )


        except Exception as exc:

            print()

            print(
                "ERROR:",
                repr(exc)
            )

            print(
                "NO AUTOMATIC RETRY."
            )


        print()

        print(
            "LIVE REQUESTS USED "
            f"THIS RUN: "
            f"{live_requests_used}"
            f"/{MAX_LIVE_REQUESTS}"
        )

        print()


    # -----------------------------------------------------
    # MANIFEST
    # -----------------------------------------------------

    if results:

        build_manifest(
            results
        )


    # -----------------------------------------------------
    # FINISH
    # -----------------------------------------------------

    print()

    print(
        "=" * 92
    )

    print(
        "RUN COMPLETE"
    )

    print(
        "=" * 92
    )

    print(
        "Live requests used "
        "this run:",
        live_requests_used
    )

    print(
        "Run again WITHOUT "
        "--refresh to reuse "
        "successful cache files "
        "and avoid duplicate "
        "API requests."
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()