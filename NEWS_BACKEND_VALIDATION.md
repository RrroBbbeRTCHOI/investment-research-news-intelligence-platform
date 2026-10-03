# News Backend V1 — validation and delivery

Validation date: 2026-09-18. Runtime: Python 3.13.0. No provider calls, model API
calls or package installations were required. Only additive files were created.

## Test results

- `python3 -m unittest discover -s tests/news -t tests`: **51 tests passed**.
- `python3 tests/run.py`: **270 tests run in 91.372 seconds; 3 failing
  subtests in one existing cache-hash test; zero errors**. The full suite is
  therefore **not completely green**. All new news tests and the remaining
  legacy tests passed, including all seven full-pipeline golden tests covering
  the 42 ticker/tab combinations.
- Python syntax validation passed. JSON output inspection passed.
- Each of the 175 copied original files was compared byte for byte against the
  supplied ZIP: zero modified or missing files. This includes all 93 files
  covered by the existing News UI preservation hash manifest.

The three failures are in
`test_news_ui.NewsUITests.test_research_and_financial_sources_unchanged`:

| Existing file under data/cache/historical_financials/ | Supplied ZIP SHA-256 (also copied output) | Manifest expected SHA-256 |
|---|---|---|
| AAPL_balance_sheet_statement_5y.json | 1462d3d4b08d6bd616467794fe56d6850bc602084950785e0cf646a28580acf4 | e085d8d8930e33dfa337491a2a4dcef03429cf9e5e260ca400329cc011f53ed7 |
| AAPL_cash_flow_statement_5y.json | 395fd19aa2329f1a7155a9f2c8fbc1b867ad9b76533f74cd9ae673ea9c300639 | 6d065a1a13659d256b356a30818715d4579b5b62ecb25a1212138b9810068578 |
| AAPL_income_statement_5y.json | 4d0f779332f7ed3d9e3d6d342248cadb8dafa68e8b0e9d1992fea42c221cd91c | 98bdf62d6c4d8ff78741436fb303489f3d984e1d170d7f5270643a1dfb3d3dc8 |

These mismatches already exist in the user's input ZIP. Neither the caches nor
the manifest/golden baselines were rewritten to make tests pass. Reconciliation
of that existing cache provenance is outside this news-only implementation.

## Actual supplied article batch

`python3 -m src.news.pipeline` completed successfully:

| Measurement | Count |
|---|---:|
| Articles loaded / full text available | 10 / 10 |
| Accepted events | 0 |
| Rejected articles | 10 |
| Candidate channels | 0 |
| Knowledge-layer company matches | 0 |

The marriage-deficit opinion, sports, entertainment and nutrition articles
produce no investable events. The SpaceX/Starliner story's tentative prospective
plans do not satisfy this version's asserted-current-event gate. No acceptance
quota is enforced. This conservative rejection does not establish that such a
story could never have economic importance.

The three generated JSON files were inspected: the events and matches arrays
are empty, all ten rejection records are present, and missing knowledge is
explicitly reported. Positive extraction, exact joins and a one-company match
are exercised by synthetic test fixtures, not fabricated production results.

## Exposure status

`missing_workbook`: no
`MAG7_News_Intelligence_Exposure_Knowledge_Layer_V1.xlsx` exists in the supplied
project. No ordinal matrices or invented edges were substituted. The loader,
sheet parsing, evidence restrictions, subtype compatibility, future/expired
timestamp rejection and planned-facility rejection were tested using temporary
synthetic XLSX fixtures. A real workbook still requires data-owner provenance
review and end-to-end validation against its actual rows.

## Added files

Source / news-specific dependency:

- `src/news/constants.py`
- `src/news/schemas.py`
- `src/news/event_gate.py`
- `src/news/event_extractor.py`
- `src/news/channel_generator.py`
- `src/news/exposure_matcher.py`
- `src/news/pipeline.py`
- `src/news/requirements.txt`

Tests:

- `tests/news/__init__.py`
- `tests/news/helpers.py`
- `tests/news/test_event_gate.py`
- `tests/news/test_event_extractor.py`
- `tests/news/test_channel_generator.py`
- `tests/news/test_exposure_matcher.py`
- `tests/news/test_news_pipeline.py`

Documentation / generated data:

- `NEWS_BACKEND_V1.md`
- `NEWS_BACKEND_VALIDATION.md`
- `data/news/events/events_v1.json`
- `data/news/events/candidate_channels_v1.json`
- `data/news/matches/event_company_matches_v1.json`

**Modified existing files: none.** Existing package initializers, normalized
schema, provider pipeline, templates, assets, routes, financial methodology,
ratings, scoring and cache architecture remain unchanged.

## Archive and limitations

The standalone folder is `STOCK_SCREENER_NEWS_INTELLIGENCE_BACKEND_V1` and the
archive is `STOCK_SCREENER_NEWS_INTELLIGENCE_BACKEND_V1.zip`. Packaging excludes
`.env`, credentials, interpreter/test caches and macOS metadata. Known credential
values from the working `.env` are scanned against every archive member. The
working `.env` is preserved, never overwritten or printed.

The backend is deterministic English rule extraction, not ML, sentiment or
causal inference. Heuristic scores are uncalibrated. Unknown facts and absent
knowledge stay unknown; this version does not reconstruct historical article
revisions or perform advanced event clustering. Read `NEWS_BACKEND_V1.md` for
the exact scoring formula, timestamp assumptions, conservative subtype matching
and known recall limitations.
