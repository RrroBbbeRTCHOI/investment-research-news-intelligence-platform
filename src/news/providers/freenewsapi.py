import os
import json
from pathlib import Path
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv


# =========================================================
# LOAD ENV
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

RAW_DIR = Path("data/news/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# CACHE HELPERS
# =========================================================

def build_cache_file(query_name: str) -> Path:
    safe_name = (
        query_name
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
    )

    return RAW_DIR / f"freenewsapi_{safe_name}.json"


def load_cache(cache_file: Path):
    if not cache_file.exists():
        return None

    print("=" * 80)
    print("USING LOCAL CACHE")
    print("FILE:", cache_file)
    print("=" * 80)

    with open(cache_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache_file: Path, data):
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("RAW RESPONSE SAVED:")
    print(cache_file)


# =========================================================
# API REQUEST
# =========================================================

def fetch_news(
    query_name: str,
    params: dict,
    force_refresh: bool = False
):
    cache_file = build_cache_file(query_name)

    # -----------------------------------------------------
    # Use cache first
    # -----------------------------------------------------

    if not force_refresh:
        cached_data = load_cache(cache_file)

        if cached_data is not None:
            return cached_data

    # -----------------------------------------------------
    # API request
    # -----------------------------------------------------

    print("=" * 80)
    print("CALLING FREENEWSAPI")
    print("QUERY:", query_name)
    print("=" * 80)

    response = requests.get(
        f"{BASE_URL}/news",
        headers=HEADERS,
        params=params,
        timeout=30
    )

    print("HTTP STATUS:", response.status_code)

    if response.status_code != 200:
        print()
        print("API RESPONSE:")
        print(response.text)

    response.raise_for_status()

    raw_data = response.json()

    # -----------------------------------------------------
    # Add ingestion metadata
    # -----------------------------------------------------

    wrapped_data = {
        "_ingestion": {
            "provider": "freenewsapi",
            "query_name": query_name,
            "fetched_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "request_params": params
        },
        "raw_response": raw_data
    }

    save_cache(
        cache_file,
        wrapped_data
    )

    return wrapped_data


# =========================================================
# TEST QUERY
# =========================================================

def main():

    params = {
        "language": "en",
        "country": "us",
    }

    data = fetch_news(
        query_name="nvidia_test",
        params=params,
        force_refresh=False
    )

    print()
    print("=" * 80)
    print("INGESTION SUCCESS")
    print("=" * 80)

    ingestion = data.get(
        "_ingestion",
        {}
    )

    print(
        "Provider:",
        ingestion.get("provider")
    )

    print(
        "Fetched at:",
        ingestion.get("fetched_at")
    )

    raw_response = data.get(
        "raw_response",
        {}
    )

    print()
    print("RAW RESPONSE TYPE:")
    print(type(raw_response))

    print()
    print("TOP-LEVEL KEYS:")

    if isinstance(raw_response, dict):
        for key in raw_response.keys():
            print("-", key)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()