import json
from pathlib import Path
from datetime import datetime, timezone


# =========================================================
# PATHS
# =========================================================

LISTING_FILE = Path(
    "data/news/raw/freenewsapi_nvidia_test.json"
)

DETAILS_DIR = Path(
    "data/news/raw/details"
)

NORMALIZED_DIR = Path(
    "data/news/normalized"
)

NORMALIZED_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    NORMALIZED_DIR
    / "freenewsapi_articles_normalized.json"
)


# =========================================================
# LOAD HELPERS
# =========================================================

def load_json(path: Path):

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# =========================================================
# LOAD DETAIL FILE
# =========================================================

def load_detail(
    article_uuid: str
):

    detail_file = (
        DETAILS_DIR
        / f"{article_uuid}.json"
    )

    if not detail_file.exists():
        return None

    detail_data = load_json(
        detail_file
    )

    return detail_data


# =========================================================
# NORMALIZE ARTICLE
# =========================================================

def normalize_article(
    listing_article: dict,
    listing_ingestion: dict
):

    article_uuid = listing_article.get(
        "uuid"
    )

    detail_wrapper = load_detail(
        article_uuid
    )

    detail_article = {}

    detail_fetched_at = None

    if detail_wrapper:

        detail_article = (
            detail_wrapper
            .get("raw_response", {})
            .get("data", {})
        )

        detail_fetched_at = (
            detail_wrapper
            .get("_ingestion", {})
            .get("fetched_at")
        )

    # Prefer details endpoint values
    title = (
        detail_article.get("title")
        or listing_article.get("title")
    )

    publisher = (
        detail_article.get("publisher")
        or listing_article.get("publisher")
    )

    published_at = (
        detail_article.get("published_at")
        or listing_article.get("published_at")
    )

    normalized = {

        # -----------------------------------------
        # Identity
        # -----------------------------------------

        "article_id": (
            f"freenewsapi_{article_uuid}"
            if article_uuid
            else None
        ),

        "provider": "freenewsapi",

        "provider_article_id": article_uuid,

        # -----------------------------------------
        # Content
        # -----------------------------------------

        "headline": title,

        "summary": detail_article.get(
            "incipit"
        ),

        "body": detail_article.get(
            "body"
        ),

        # -----------------------------------------
        # Source
        # -----------------------------------------

        "source": publisher,

        "article_url": (detail_article.get("original_url") or listing_article.get("original_url") or listing_article.get("url")),

        "thumbnail": detail_article.get(
            "thumbnail"
        ),

        # -----------------------------------------
        # Metadata
        # -----------------------------------------

        "authors": (
            detail_article.get("authors")
            or []
        ),

        "topics": (
            detail_article.get("topics")
            or []
        ),

        "countries": (
            detail_article.get("countries")
            or []
        ),

        "languages": (
            detail_article.get("languages")
            or []
        ),

        # -----------------------------------------
        # Time
        # -----------------------------------------

        "published_at": published_at,

        "fetched_at": (
            detail_fetched_at
            or listing_ingestion.get(
                "fetched_at"
            )
        ),

        # -----------------------------------------
        # Detail status
        # -----------------------------------------

        "has_full_text": bool(
            detail_article.get("body")
        ),

        # -----------------------------------------
        # Traceability
        # -----------------------------------------

        "raw_listing": listing_article,

        "raw_detail": (
            detail_article
            if detail_article
            else None
        )
    }

    return normalized


# =========================================================
# NORMALIZE ALL
# =========================================================

def normalize_all():

    listing_wrapper = load_json(
        LISTING_FILE
    )

    listing_ingestion = (
        listing_wrapper.get(
            "_ingestion",
            {}
        )
    )

    raw_response = (
        listing_wrapper.get(
            "raw_response",
            {}
        )
    )

    listing_articles = (
        raw_response.get(
            "data",
            []
        )
    )

    normalized = []

    for article in listing_articles:

        normalized_article = (
            normalize_article(
                listing_article=article,
                listing_ingestion=(
                    listing_ingestion
                )
            )
        )

        normalized.append(
            normalized_article
        )

    return normalized


# =========================================================
# SAVE
# =========================================================

def save_normalized(
    articles
):

    full_text_count = sum(
        1
        for article in articles
        if article.get(
            "has_full_text"
        )
    )

    output = {

        "_metadata": {

            "schema": (
                "normalized_article_v2"
            ),

            "generated_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "article_count": len(
                articles
            ),

            "full_text_count": (
                full_text_count
            )
        },

        "articles": articles
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 80)

    print(
        "NORMALIZED NEWS SAVED"
    )

    print("=" * 80)

    print(
        "FILE:",
        OUTPUT_FILE
    )

    print(
        "ARTICLES:",
        len(articles)
    )

    print(
        "FULL TEXT:",
        full_text_count
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 80)

    print(
        "NEWS NORMALIZER V2"
    )

    print("=" * 80)

    articles = normalize_all()

    save_normalized(
        articles
    )

    print()

    if articles:

        print(
            "FIRST ARTICLE:"
        )

        print(
            json.dumps(
                articles[0],
                ensure_ascii=False,
                indent=2
            )
        )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()