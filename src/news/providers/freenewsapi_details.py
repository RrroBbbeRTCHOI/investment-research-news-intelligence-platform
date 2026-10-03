import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv


# =========================================================
# ENV
# =========================================================

load_dotenv()

API_KEY = os.getenv("FREENEWSAPI_KEY")

if not API_KEY:
    raise RuntimeError(
        "FREENEWSAPI_KEY not found in .env"
    )


# =========================================================
# CONFIG
# =========================================================

BASE_URL = "https://api.freenewsapi.io/v1"

HEADERS = {
    "x-api-key": API_KEY
}

LISTING_FILE = Path(
    "data/news/raw/freenewsapi_nvidia_test.json"
)

DETAILS_DIR = Path(
    "data/news/raw/details"
)

DETAILS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# JSON HELPERS
# =========================================================

def load_json(path: Path):

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_json(
    path: Path,
    data: dict
):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# CACHE
# =========================================================

def build_cache_file(
    article_uuid: str
):

    return (
        DETAILS_DIR
        / f"{article_uuid}.json"
    )


def load_cache(
    article_uuid: str
):

    cache_file = build_cache_file(
        article_uuid
    )

    if not cache_file.exists():
        return None

    return load_json(
        cache_file
    )


# =========================================================
# FETCH ONE ARTICLE
# =========================================================

def fetch_article_details(
    article_uuid: str,
    force_refresh: bool = False
):

    cache_file = build_cache_file(
        article_uuid
    )

    # -----------------------------------------
    # Cache first
    # -----------------------------------------

    if not force_refresh:

        cached = load_cache(
            article_uuid
        )

        if cached is not None:

            print(
                f"[CACHE] {article_uuid}"
            )

            return cached

    # -----------------------------------------
    # API call
    # -----------------------------------------

    print(
        f"[API] Fetching {article_uuid}"
    )

    response = requests.get(
        f"{BASE_URL}/details",
        headers=HEADERS,
        params={
            "uuid": article_uuid
        },
        timeout=30
    )

    print(
        "      HTTP:",
        response.status_code
    )

    if response.status_code != 200:

        print(
            "      RESPONSE:",
            response.text
        )

        return None

    raw_data = response.json()

    wrapped = {

        "_ingestion": {

            "provider": "freenewsapi",

            "endpoint": "details",

            "article_uuid": article_uuid,

            "fetched_at": datetime.now(
                timezone.utc
            ).isoformat()
        },

        "raw_response": raw_data
    }

    save_json(
        cache_file,
        wrapped
    )

    return wrapped


# =========================================================
# LOAD LISTING ARTICLES
# =========================================================

def load_listing_articles():

    if not LISTING_FILE.exists():

        raise FileNotFoundError(
            f"Listing file not found: {LISTING_FILE}"
        )

    wrapper = load_json(
        LISTING_FILE
    )

    raw_response = wrapper.get(
        "raw_response",
        {}
    )

    articles = raw_response.get(
        "data",
        []
    )

    return articles


# =========================================================
# BATCH FETCH
# =========================================================

def fetch_all_details():

    articles = load_listing_articles()

    total = len(articles)

    print("=" * 80)

    print(
        "FREENEWSAPI BATCH DETAIL FETCH"
    )

    print("=" * 80)

    print(
        "ARTICLES FOUND:",
        total
    )

    print()

    success_count = 0

    cache_count = 0

    failed_count = 0

    for index, article in enumerate(
        articles,
        start=1
    ):

        article_uuid = article.get(
            "uuid"
        )

        title = article.get(
            "title"
        )

        print(
            f"[{index}/{total}]"
        )

        print(
            "TITLE:",
            title
        )

        if not article_uuid:

            print(
                "SKIPPED: missing UUID"
            )

            failed_count += 1

            print()

            continue

        cache_file = build_cache_file(
            article_uuid
        )

        existed_before = (
            cache_file.exists()
        )

        result = fetch_article_details(
            article_uuid=article_uuid,
            force_refresh=False
        )

        if result is None:

            failed_count += 1

        elif existed_before:

            cache_count += 1

        else:

            success_count += 1

        print()

        # Small delay to avoid hitting API too fast
        if not existed_before:
            time.sleep(0.6)

    print("=" * 80)

    print(
        "BATCH FETCH COMPLETE"
    )

    print("=" * 80)

    print(
        "NEW API FETCHES:",
        success_count
    )

    print(
        "CACHE HITS:",
        cache_count
    )

    print(
        "FAILED:",
        failed_count
    )

    print(
        "TOTAL:",
        total
    )


# =========================================================
# MAIN
# =========================================================

def main():

    fetch_all_details()


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()