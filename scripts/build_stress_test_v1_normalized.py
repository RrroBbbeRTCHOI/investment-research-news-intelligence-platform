import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =========================================================
# NEWS INTELLIGENCE
# STRESS TEST v1 — NORMALIZED INPUT BUILDER
#
# Input:
#   data/news/benchmarks/stress_test_v1/source_articles.json
#
# Output:
#   data/news/normalized/stress_test_v1.json
#
# IMPORTANT:
#
# - LOCAL FILES ONLY
# - ZERO API REQUESTS
# - ZERO GEMINI CALLS
# - DOES NOT READ ground_truth.json
# - DOES NOT MODIFY FROZEN SOURCE ARTICLES
# - DOES NOT MODIFY CORE V3.x PIPELINE
#
# Perigon policy:
#
#   description
#       -> normalized summary
#
#   provider summary
#       -> normalized body
#
#   truncated content preview
#       -> raw_detail only
#
#   has_full_text
#       -> False
#
# FreeNewsAPI local controls:
#
#   preserve original normalized article
#   preserve original real body/full-text status
#
# =========================================================


# =========================================================
# PATHS
# =========================================================

SOURCE_PATH = Path(
    "data/news/benchmarks/stress_test_v1/source_articles.json"
)

OUTPUT_PATH = Path(
    "data/news/normalized/stress_test_v1.json"
)

OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# REQUIRED NORMALIZED SCHEMA
# =========================================================

REQUIRED_FIELDS = [
    "article_id",
    "provider",
    "provider_article_id",
    "headline",
    "summary",
    "body",
    "source",
    "article_url",
    "thumbnail",
    "authors",
    "topics",
    "countries",
    "languages",
    "published_at",
    "fetched_at",
    "has_full_text",
    "raw_listing",
    "raw_detail",
]


# =========================================================
# BASIC HELPERS
# =========================================================

def load_json(
    path: Path,
) -> Any:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def save_json(
    path: Path,
    data: Any,
):

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def first_nonempty(
    *values,
):

    for value in values:

        if value is None:
            continue

        if isinstance(
            value,
            str,
        ):

            value = value.strip()

            if value:
                return value

        elif value:
            return value

    return None


def normalize_list(
    value: Any,
) -> List[str]:

    if value is None:
        return []

    result: List[str] = []

    if isinstance(
        value,
        str,
    ):

        value = value.strip()

        if value:
            result.append(
                value
            )

        return result

    if not isinstance(
        value,
        list,
    ):
        return result

    for item in value:

        if isinstance(
            item,
            str,
        ):

            item = item.strip()

            if (
                item
                and
                item not in result
            ):
                result.append(
                    item
                )

        elif isinstance(
            item,
            dict,
        ):

            name = first_nonempty(
                item.get("name"),
                item.get("label"),
                item.get("title"),
                item.get("value"),
                item.get("topic"),
                item.get("category"),
            )

            if name:

                text = str(
                    name
                ).strip()

                if (
                    text
                    and
                    text not in result
                ):
                    result.append(
                        text
                    )

    return result


# =========================================================
# PERIGON HELPERS
# =========================================================

def perigon_provider_id(
    article: Dict[str, Any],
) -> str:

    value = first_nonempty(
        article.get("articleId"),
        article.get("_id"),
        article.get("id"),
    )

    if not value:

        raise RuntimeError(
            "Perigon article has no article ID."
        )

    return str(
        value
    )


def source_name_from_perigon(
    article: Dict[str, Any],
) -> str:

    source = (
        article.get("source")
        or {}
    )

    if isinstance(
        source,
        str,
    ):

        return (
            source.strip()
            or
            "Unknown"
        )

    if isinstance(
        source,
        dict,
    ):

        return (
            first_nonempty(
                source.get("name"),
                source.get("domain"),
            )
            or
            "Unknown"
        )

    return "Unknown"


def source_domain_from_perigon(
    article: Dict[str, Any],
) -> Optional[str]:

    source = (
        article.get("source")
        or {}
    )

    if isinstance(
        source,
        dict,
    ):

        return source.get(
            "domain"
        )

    return None


def detect_truncated_content(
    content: Any,
) -> bool:

    if not isinstance(
        content,
        str,
    ):
        return False

    text = content.strip()

    if not text:
        return False

    # Examples observed:
    #
    # "... [3996 symbols]"
    # "... [14563 symbols]"
    #
    # Keep this deliberately narrow so we do not label
    # unrelated bracketed text as truncation.

    pattern = (
        r"\[\s*\d+\s+symbols?\s*\]\s*$"
    )

    if re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    ):
        return True

    return False


def extract_perigon_authors(
    article: Dict[str, Any],
) -> List[str]:

    authors_byline = article.get(
        "authorsByline"
    )

    authors = normalize_list(
        authors_byline
    )

    if authors:
        return authors

    matched_authors = article.get(
        "matchedAuthors"
    )

    return normalize_list(
        matched_authors
    )


def extract_perigon_topics(
    article: Dict[str, Any],
) -> List[str]:

    result: List[str] = []

    for field in [
        "topics",
        "categories",
        "keywords",
    ]:

        values = normalize_list(
            article.get(field)
        )

        for value in values:

            if value not in result:
                result.append(
                    value
                )

    return result


# =========================================================
# NORMALIZE PERIGON ARTICLE
# =========================================================

def normalize_perigon_article(
    case: Dict[str, Any],
) -> Dict[str, Any]:

    case_id = case[
        "case_id"
    ]

    article = case[
        "article"
    ]

    provider_id = (
        perigon_provider_id(
            article
        )
    )


    # -----------------------------------------------------
    # HEADLINE
    # -----------------------------------------------------

    headline = first_nonempty(
        article.get("title"),
    )

    if not headline:

        raise RuntimeError(
            f"{case_id}: missing title"
        )


    # -----------------------------------------------------
    # NORMALIZED SUMMARY
    #
    # Keep this concise and close to publisher-facing
    # metadata.
    #
    # We deliberately prefer description over provider
    # generated summary.
    # -----------------------------------------------------

    summary = first_nonempty(
        article.get("description"),
        article.get("shortSummary"),
        article.get("summary"),
    )


    # -----------------------------------------------------
    # NORMALIZED BODY
    #
    # IMPORTANT:
    #
    # Perigon Free-tier "content" has been observed to be
    # a truncated preview such as:
    #
    #   "... [3996 symbols]"
    #
    # Therefore it must NOT be treated as full article text.
    #
    # We use the longer Perigon provider summary as the
    # richest locally cached representation available.
    #
    # Original content remains untouched in raw_detail.
    # -----------------------------------------------------

    body = first_nonempty(
        article.get("summary"),
        article.get("description"),
        article.get("shortSummary"),
        article.get("content"),
    )


    # -----------------------------------------------------
    # CONTENT AUDIT
    # -----------------------------------------------------

    original_content = article.get(
        "content"
    )

    content_preview_truncated = (
        detect_truncated_content(
            original_content
        )
    )


    # -----------------------------------------------------
    # AUTHORS
    # -----------------------------------------------------

    authors = (
        extract_perigon_authors(
            article
        )
    )


    # -----------------------------------------------------
    # TOPICS
    # -----------------------------------------------------

    topics = (
        extract_perigon_topics(
            article
        )
    )


    # -----------------------------------------------------
    # COUNTRIES
    #
    # IMPORTANT:
    #
    # Do NOT inject Perigon provider geography into the
    # normalized event geography.
    #
    # The research pipeline must independently establish
    # event geography from article evidence.
    #
    # Provider country / location metadata remains
    # preserved in raw_detail.
    # -----------------------------------------------------

    countries: List[str] = []


    # -----------------------------------------------------
    # LANGUAGES
    # -----------------------------------------------------

    languages = normalize_list(
        article.get(
            "language"
        )
    )

    if not languages:

        languages = [
            "en"
        ]


    # -----------------------------------------------------
    # FETCHED AT
    # -----------------------------------------------------

    fetched_at = first_nonempty(
        article.get("addDate"),
        article.get("refreshDate"),
        article.get("pubDate"),
    )

    if not fetched_at:

        fetched_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )


    # -----------------------------------------------------
    # FULL TEXT STATUS
    #
    # Never infer this from character count.
    #
    # These Perigon frozen benchmark records do NOT contain
    # independently verified complete article text.
    # -----------------------------------------------------

    has_full_text = False


    # -----------------------------------------------------
    # NORMALIZED ARTICLE
    # -----------------------------------------------------

    normalized = {

        "article_id":
            (
                f"stress_v1_"
                f"{case_id}_"
                f"{provider_id}"
            ),

        "provider":
            "perigon",

        "provider_article_id":
            provider_id,

        "headline":
            headline,

        "summary":
            summary,

        "body":
            body,

        "source":
            source_name_from_perigon(
                article
            ),

        "article_url":
            article.get(
                "url"
            ),

        "thumbnail":
            article.get(
                "imageUrl"
            ),

        "authors":
            authors,

        "topics":
            topics,

        "countries":
            countries,

        "languages":
            languages,

        "published_at":
            article.get(
                "pubDate"
            ),

        "fetched_at":
            fetched_at,

        "has_full_text":
            has_full_text,


        # -------------------------------------------------
        # RAW LISTING
        #
        # Contains benchmark metadata only.
        #
        # IMPORTANT:
        # This is NOT ground truth.
        # -------------------------------------------------

        "raw_listing": {

            "_benchmark":
                True,

            "_benchmark_name":
                "stress_test_v1",

            "_benchmark_case_id":
                case_id,

            "_benchmark_category":
                case.get(
                    "category"
                ),

            "_frozen_sha256":
                case.get(
                    "frozen_sha256"
                ),


            # ---------------------------------------------
            # TEXT PROVENANCE
            # ---------------------------------------------

            "text_basis":
                "perigon_provider_summary",

            "full_text_verified":
                False,

            "content_preview_truncated":
                content_preview_truncated,

            "original_content_chars":
                (
                    len(
                        original_content
                    )
                    if isinstance(
                        original_content,
                        str,
                    )
                    else 0
                ),

            "normalized_summary_chars":
                (
                    len(summary)
                    if isinstance(
                        summary,
                        str,
                    )
                    else 0
                ),

            "normalized_body_chars":
                (
                    len(body)
                    if isinstance(
                        body,
                        str,
                    )
                    else 0
                ),


            # ---------------------------------------------
            # PROVIDER METADATA
            # ---------------------------------------------

            "articleId":
                provider_id,

            "title":
                headline,

            "pubDate":
                article.get(
                    "pubDate"
                ),

            "domain":
                source_domain_from_perigon(
                    article
                ),

            "clusterId":
                article.get(
                    "clusterId"
                ),

            "reprint":
                article.get(
                    "reprint"
                ),

            "provider_country_metadata":
                article.get(
                    "country"
                ),
        },


        # -------------------------------------------------
        # RAW DETAIL
        #
        # Preserve the COMPLETE frozen Perigon object.
        #
        # This means original content preview,
        # summary, entities, companies, locations,
        # sentiment, etc. remain auditable.
        # -------------------------------------------------

        "raw_detail":
            article,
    }


    return normalized


# =========================================================
# NORMALIZE LOCAL CONTROL ARTICLE
# =========================================================

def normalize_local_article(
    case: Dict[str, Any],
) -> Dict[str, Any]:

    case_id = case[
        "case_id"
    ]

    article = dict(
        case[
            "article"
        ]
    )


    # -----------------------------------------------------
    # ORIGINAL ID
    # -----------------------------------------------------

    original_id = first_nonempty(
        article.get(
            "article_id"
        ),
        article.get(
            "provider_article_id"
        ),
    )

    if not original_id:

        raise RuntimeError(
            f"{case_id}: "
            "local article has no ID"
        )


    # -----------------------------------------------------
    # PREFIX BENCHMARK CASE ID
    # -----------------------------------------------------

    article[
        "article_id"
    ] = (
        f"stress_v1_"
        f"{case_id}_"
        f"{original_id}"
    )


    # -----------------------------------------------------
    # RAW LISTING
    # -----------------------------------------------------

    raw_listing = article.get(
        "raw_listing"
    )

    if not isinstance(
        raw_listing,
        dict,
    ):

        raw_listing = {}


    raw_listing[
        "_benchmark"
    ] = True

    raw_listing[
        "_benchmark_name"
    ] = "stress_test_v1"

    raw_listing[
        "_benchmark_case_id"
    ] = case_id

    raw_listing[
        "_benchmark_category"
    ] = case.get(
        "category"
    )

    raw_listing[
        "_frozen_sha256"
    ] = case.get(
        "frozen_sha256"
    )


    # -----------------------------------------------------
    # LOCAL TEXT PROVENANCE
    #
    # These two control articles originated from the
    # existing FreeNewsAPI normalized pipeline and already
    # contain real article bodies.
    # -----------------------------------------------------

    raw_listing[
        "text_basis"
    ] = "existing_normalized_article"

    raw_listing[
        "full_text_verified"
    ] = bool(
        article.get(
            "has_full_text"
        )
    )


    article[
        "raw_listing"
    ] = raw_listing


    return article


# =========================================================
# NORMALIZE CASE
# =========================================================

def normalize_case(
    case: Dict[str, Any],
) -> Dict[str, Any]:

    provider = case.get(
        "source_provider"
    )

    if provider == "perigon":

        return (
            normalize_perigon_article(
                case
            )
        )


    if (
        provider
        ==
        "local_normalized_sample"
    ):

        return (
            normalize_local_article(
                case
            )
        )


    raise RuntimeError(

        "Unsupported source provider "
        f"for {case.get('case_id')}: "
        f"{provider}"
    )


# =========================================================
# VALIDATION
# =========================================================

def validate_article(
    article: Dict[str, Any],
):

    missing = [

        field

        for field
        in REQUIRED_FIELDS

        if field not in article
    ]


    if missing:

        raise RuntimeError(

            f"{article.get('article_id')}: "
            f"missing fields {missing}"
        )


    if not article.get(
        "headline"
    ):

        raise RuntimeError(

            f"{article.get('article_id')}: "
            "empty headline"
        )


    if not article.get(
        "published_at"
    ):

        raise RuntimeError(

            f"{article.get('article_id')}: "
            "missing published_at"
        )


    raw_listing = article.get(
        "raw_listing"
    )


    if not isinstance(
        raw_listing,
        dict,
    ):

        raise RuntimeError(

            f"{article.get('article_id')}: "
            "raw_listing is not dict"
        )


    case_id = raw_listing.get(
        "_benchmark_case_id"
    )


    if not case_id:

        raise RuntimeError(

            f"{article.get('article_id')}: "
            "missing benchmark case id"
        )


    # -----------------------------------------------------
    # PERIGON SAFETY CHECK
    # -----------------------------------------------------

    if (
        article.get("provider")
        ==
        "perigon"
    ):

        if article.get(
            "has_full_text"
        ):

            raise RuntimeError(

                f"{case_id}: "
                "Perigon benchmark article "
                "must not be marked full text."
            )


        if (
            raw_listing.get(
                "full_text_verified"
            )
            is not False
        ):

            raise RuntimeError(

                f"{case_id}: "
                "Perigon full_text_verified "
                "must be False."
            )


# =========================================================
# VALIDATE ENTIRE BENCHMARK
# =========================================================

def validate_benchmark(
    articles: List[
        Dict[str, Any]
    ],
):

    if len(
        articles
    ) != 12:

        raise RuntimeError(

            "Expected 12 normalized "
            f"articles, got {len(articles)}."
        )


    # -----------------------------------------------------
    # UNIQUE ARTICLE IDS
    # -----------------------------------------------------

    article_ids = [

        article[
            "article_id"
        ]

        for article
        in articles
    ]


    if (
        len(article_ids)
        !=
        len(
            set(article_ids)
        )
    ):

        raise RuntimeError(
            "Duplicate article_id detected."
        )


    # -----------------------------------------------------
    # BENCHMARK CASE IDS
    # -----------------------------------------------------

    benchmark_case_ids = [

        article[
            "raw_listing"
        ][
            "_benchmark_case_id"
        ]

        for article
        in articles
    ]


    expected_case_ids = [

        f"ST{i:02d}"

        for i
        in range(
            1,
            13
        )
    ]


    if (
        sorted(
            benchmark_case_ids
        )
        !=
        expected_case_ids
    ):

        raise RuntimeError(

            "Benchmark case IDs "
            "do not match ST01-ST12.\n"
            f"Found: "
            f"{sorted(benchmark_case_ids)}"
        )


    # -----------------------------------------------------
    # EACH ARTICLE
    # -----------------------------------------------------

    for article in articles:

        validate_article(
            article
        )


# =========================================================
# TERMINAL REPORT
# =========================================================

def print_article_report(
    article: Dict[str, Any],
):

    raw_listing = article[
        "raw_listing"
    ]

    case_id = raw_listing[
        "_benchmark_case_id"
    ]

    body = (
        article.get(
            "body"
        )
        or ""
    )

    summary = (
        article.get(
            "summary"
        )
        or ""
    )


    print(
        case_id,
        "|",
        article[
            "provider"
        ]
    )

    print(
        "   ",
        article[
            "headline"
        ]
    )

    print(
        "    summary chars:",
        len(summary)
    )

    print(
        "    body chars   :",
        len(body)
    )

    print(
        "    full text    :",
        article[
            "has_full_text"
        ]
    )


    if (
        article["provider"]
        ==
        "perigon"
    ):

        print(
            "    preview trunc:",
            raw_listing.get(
                "content_preview_truncated"
            )
        )

        print(
            "    text basis   :",
            raw_listing.get(
                "text_basis"
            )
        )


    print()


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=" * 84
    )

    print(
        "BUILDING NORMALIZED "
        "STRESS TEST v1"
    )

    print(
        "=" * 84
    )

    print(
        "API requests : 0"
    )

    print(
        "Gemini calls : 0"
    )

    print(
        "Ground truth : NOT READ"
    )

    print()


    # -----------------------------------------------------
    # SOURCE EXISTS
    # -----------------------------------------------------

    if not SOURCE_PATH.exists():

        raise FileNotFoundError(

            "Missing frozen benchmark "
            f"source file:\n{SOURCE_PATH}"
        )


    # -----------------------------------------------------
    # LOAD FROZEN SOURCE
    # -----------------------------------------------------

    source = load_json(
        SOURCE_PATH
    )


    cases = source.get(
        "cases"
    )


    if not isinstance(
        cases,
        list,
    ):

        raise RuntimeError(

            "source_articles.json "
            "does not contain a "
            "valid cases list."
        )


    if len(
        cases
    ) != 12:

        raise RuntimeError(

            "Expected 12 frozen "
            f"cases, got {len(cases)}."
        )


    # -----------------------------------------------------
    # NORMALIZE
    # -----------------------------------------------------

    normalized_articles = []


    for case in cases:

        article = (
            normalize_case(
                case
            )
        )

        normalized_articles.append(
            article
        )


    # -----------------------------------------------------
    # VALIDATE
    # -----------------------------------------------------

    validate_benchmark(
        normalized_articles
    )


    # -----------------------------------------------------
    # OUTPUT DOCUMENT
    #
    # Keep top-level schema identical to existing
    # normalized pipeline:
    #
    # {
    #   "articles": [...]
    # }
    # -----------------------------------------------------

    output = {

        "articles":
            normalized_articles
    }


    save_json(
        OUTPUT_PATH,
        output
    )


    # -----------------------------------------------------
    # REPORT
    # -----------------------------------------------------

    print(
        "Normalized articles:",
        len(
            normalized_articles
        )
    )

    print()


    for article in normalized_articles:

        print_article_report(
            article
        )


    # -----------------------------------------------------
    # PROVIDER COUNTS
    # -----------------------------------------------------

    perigon_count = sum(

        1

        for article
        in normalized_articles

        if (
            article.get(
                "provider"
            )
            ==
            "perigon"
        )
    )


    local_count = (

        len(
            normalized_articles
        )
        -
        perigon_count
    )


    # -----------------------------------------------------
    # FULL TEXT COUNTS
    # -----------------------------------------------------

    full_text_count = sum(

        1

        for article
        in normalized_articles

        if article.get(
            "has_full_text"
        )
    )


    partial_text_count = (

        len(
            normalized_articles
        )
        -
        full_text_count
    )


    print(
        "=" * 84
    )

    print(
        "SUMMARY"
    )

    print(
        "=" * 84
    )

    print(
        "Perigon cases       :",
        perigon_count
    )

    print(
        "Local control cases :",
        local_count
    )

    print(
        "Verified full text  :",
        full_text_count
    )

    print(
        "Partial/provider text:",
        partial_text_count
    )

    print()


    print(
        "=" * 84
    )

    print(
        "OUTPUT"
    )

    print(
        "=" * 84
    )

    print(
        OUTPUT_PATH
    )

    print()


    print(
        "SUCCESS — "
        "Stress Test v1 normalized "
        "input is ready."
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()