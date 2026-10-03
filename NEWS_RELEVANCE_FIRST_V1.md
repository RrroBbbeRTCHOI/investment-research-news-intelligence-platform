# News Intelligence — Relevance First V1

Read `docs/NEWS_RELEVANCE_FIRST_ARCHITECTURE_AUDIT.md` for the required 18-section audit, and `docs/NEWS_RELEVANCE_FIRST.md` for commands, output contract and limits.

Start the offline research backend:

```sh
python3 -m src.news.research_intelligence --input data/news/normalized/tsmc_specificity_test.json --output data/news/research/tsmc_run1.json
```

The existing News page is still the unchanged demo. This release adds the research JSON contract and ranked queue, not a UI redesign or live feed. Original Research Mode and all historical ML work remain intact. Secrets/environment files are excluded from this copy; configure your own environment only if running the original provider-backed application features.

News tests: 278 passed. Full project suite: three pre-existing AAPL financial-cache checksum subtest failures, reproduced in the unmodified input. Read `docs/NEWS_RELEVANCE_FIRST_REGRESSION_REPORT.md`; no baselines or Research caches were changed to hide them.

DIRECTION REQUIRES ANALYST JUDGMENT.
