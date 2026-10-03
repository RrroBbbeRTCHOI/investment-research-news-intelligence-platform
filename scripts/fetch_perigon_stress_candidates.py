from src.news.providers.perigon import fetch_articles


QUERIES = {
    "stress_fed_rates":
        '"Federal Reserve" AND ("interest rates" OR "rate decision")',

    "stress_us_cpi":
        '("CPI" OR "consumer prices") AND ("inflation" OR "Federal Reserve")',

    "stress_nvidia_export_controls":
        '"Nvidia" AND ("export controls" OR "China")',

    "stress_tsmc_taiwan":
        '"TSMC" AND ("Taiwan" OR "semiconductor")',

    "stress_aws_outage":
        '"AWS" AND ("outage" OR "service disruption")',

    "stress_hormuz":
        '"Hormuz" AND ("oil" OR "shipping" OR "disruption")',
}


def main():
    for query_name, query in QUERIES.items():
        print()
        print("#" * 90)
        print(query_name)
        print("#" * 90)

        try:
            data = fetch_articles(
                query_name=query_name,
                query=query,
                size=5,
                force_refresh=True,
            )

            raw = data.get("raw_response", {})
            articles = raw.get("articles", [])

            print("RESULTS:", len(articles))

            for i, article in enumerate(articles, 1):
                source = article.get("source") or {}
                domain = source.get("domain")

                print()
                print(f"{i}. {article.get('title')}")
                print("DOMAIN:", domain)
                print("DATE:", article.get("pubDate"))
                print("URL:", article.get("url"))
                print("ID:", article.get("articleId") or article.get("_id"))

        except Exception as exc:
            print("ERROR:", repr(exc))


if __name__ == "__main__":
    main()