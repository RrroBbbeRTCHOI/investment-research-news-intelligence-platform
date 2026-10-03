import os
import json
from pathlib import Path
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv


# =========================================================
# ENV
# =========================================================

load_dotenv(".env")

API_KEY = os.getenv("PERIGON_API_KEY")

if not API_KEY:
    raise RuntimeError("PERIGON_API_KEY not found in .env")


# =========================================================
# CONFIG
# =========================================================

BASE_URL = "https://api.perigon.io/v1/articles/all"

HEADERS = {
    "x-api-key": API_KEY
}

RAW_DIR = Path("data/news/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# HELPERS
# =========================================================

def build_cache_file(query_name: str) -> Path:
    safe = (
        query_name
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
    )
    return RAW_DIR / f"perigon_{safe}.json"


def fetch_articles(
    query_name: str,
    query: str,
    size: int = 10,
    force_refresh: bool = True,
):
    cache_file = build_cache_file(query_name)

    if cache_file.exists() and not force_refresh:
        print("USING CACHE:", cache_file)
        return json.loads(cache_file.read_text(encoding="utf-8"))

    params = {
        "q": query,
        "language": "en",
        "size": size,
        "sortBy": "date",
    }

    print("=" * 80)
    print("CALLING PERIGON")
    print("QUERY:", query)
    print("=" * 80)

    r = requests.get(
        BASE_URL,
        headers=HEADERS,
        params=params,
        timeout=30,
    )

    print("HTTP STATUS:", r.status_code)

    if r.status_code != 200:
        print(r.text[:3000])

    r.raise_for_status()

    raw = r.json()

    wrapped = {
        "_ingestion": {
            "provider": "perigon",
            "query_name": query_name,
            "query": query,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
        "raw_response": raw,
    }

    cache_file.write_text(
        json.dumps(wrapped, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("SAVED:", cache_file)

    return wrapped


# =========================================================
# TEST
# =========================================================

def fetch_incremental_page(query, start, end, page=0, size=50):
    """Additive live entry point; existing fetch/cache interface stays unchanged.

    A fixed added-date window also captures articles indexed after publication.
    The runner persists each returned page before advancing its cursor.
    """
    from src.news.llm.analyzer import atomic_json
    import time
    params = {'q': query, 'language': 'en', 'addDateFrom': start,
              'addDateTo': end, 'sortBy': 'date', 'page': page, 'size': size}
    for attempt in range(3):
        try:
            response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep((2, 5)[attempt])
                continue
            if response.status_code != 200:
                raise RuntimeError('news_provider_unavailable')
            raw = response.json()
            if not isinstance(raw, dict) or not isinstance(raw.get('articles'), list):
                raise RuntimeError('news_provider_invalid_response')
            wrapped = {'_ingestion': {'provider': 'perigon', 'fetched_at': datetime.now(timezone.utc).isoformat(),
                                      'window_start': start, 'window_end': end, 'page': page}, 'raw_response': raw}
            atomic_json(build_cache_file('live_latest_page'), wrapped)
            return raw['articles']
        except (requests.RequestException, ValueError):
            if attempt == 2: raise RuntimeError('news_provider_unavailable') from None
            time.sleep((2, 5)[attempt])


def main():
    data = fetch_articles(
        query_name="nvidia_test",
        query='"Nvidia"',
        size=5,
        force_refresh=True,
    )

    raw = data.get("raw_response", {})

    print()
    print("TOP LEVEL KEYS:", list(raw.keys()))

    articles = raw.get("articles") or raw.get("data") or []

    print("ARTICLES:", len(articles))

    for i, article in enumerate(articles[:5], 1):
        print()
        print(i, article.get("title"))
        print("SOURCE:", article.get("source"))
        print("DATE:", article.get("pubDate") or article.get("publishedAt"))


if __name__ == "__main__":
    main()
