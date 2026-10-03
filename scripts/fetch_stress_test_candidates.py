from src.news.providers.freenewsapi import fetch_news


QUERIES = {
    # =============================
    # MACRO / MONETARY POLICY
    # =============================
    "stress_fed": {
        "language": "en",
        "in_title": "Federal Reserve",
        "order_by": "archive",
    },

    "stress_cpi": {
        "language": "en",
        "in_title": "CPI",
        "order_by": "archive",
    },

    "stress_pboc": {
        "language": "en",
        "in_title": "PBOC",
        "order_by": "archive",
    },

    # =============================
    # POLICY / REGULATION
    # =============================
    "stress_export_controls": {
        "language": "en",
        "in_title": "export controls",
        "order_by": "archive",
    },

    "stress_antitrust": {
        "language": "en",
        "in_title": "antitrust",
        "order_by": "archive",
    },

    # =============================
    # SEMICONDUCTOR
    # =============================
    "stress_tsmc": {
        "language": "en",
        "in_title": "TSMC",
        "order_by": "archive",
    },

    "stress_nvidia": {
        "language": "en",
        "in_title": "Nvidia",
        "order_by": "archive",
    },

    # =============================
    # CLOUD / INFRASTRUCTURE
    # =============================
    "stress_aws": {
        "language": "en",
        "in_title": "AWS",
        "order_by": "archive",
    },

    # =============================
    # GEOPOLITICS / ENERGY
    # =============================
    "stress_hormuz": {
        "language": "en",
        "in_title": "Hormuz",
        "order_by": "archive",
    },

    # =============================
    # SUPPLY CHAIN
    # =============================
    "stress_taiwan": {
        "language": "en",
        "in_title": "Taiwan",
        "order_by": "archive",
    },
}

def main():
    print("=" * 80)
    print("NEWS INTELLIGENCE STRESS TEST — CANDIDATE FETCH")
    print("=" * 80)

    for query_name, params in QUERIES.items():
        print()
        print("#" * 80)
        print(query_name)
        print("#" * 80)

        try:
            data = fetch_news(
                query_name=query_name,
                params=params,
                force_refresh=True,
            )

            raw = data.get("raw_response", {})
            articles = raw.get("data", [])

            print("ARTICLES RETURNED:", len(articles))

            for i, article in enumerate(articles[:5], 1):
                print(
                    f"{i}. "
                    f"{article.get('title')} "
                    f"| {article.get('publisher')} "
                    f"| {article.get('published_at')}"
                )

        except Exception as exc:
            print("ERROR:", repr(exc))


if __name__ == "__main__":
    main()