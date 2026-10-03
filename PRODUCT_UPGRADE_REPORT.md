# News Intelligence Live Product V3.2

## Architecture and scope

This standalone copy continues the accepted V3.1.6 UI integration. Research semantics remain frozen. Product operation, analyst-attention presentation and portfolio arithmetic are additive. No Redis, Celery, Kafka, WebSockets, new database, ML model or brokerage integration was introduced.

Before:

```text
Previously generated frozen research JSON → read-only Flask API → one-time browser load
Market tape: unavailable; position: page-session arithmetic with no quote
```

After:

```text
Independent live_runner (600 seconds, opt-in)
  Perigon incremental page → normalize → durable identity dedupe/pending queue
  → existing cheap filter → existing content/prompt/model enrichment cache
  → quota-wrapped existing Analyzer (including retries/fallback)
  → unchanged V3.1.6 research → atomic completed-record snapshot
                                            ↓
Read-only Flask API → additive backend product scores → browser poll (45 seconds)
                                            ↓
Feed / existing globe / analyst panel / qualified-only portfolio linkage

Independent market cadence in worker (180 seconds, opt-in)
  existing yahoo_provider → persistent atomic quote snapshot → read-only Flask API
  → market tape and browser-local manual portfolio
```

Flask does not instantiate a live runner or request quotes. Browser polling only reads Flask snapshots. The original project is not overwritten.

## Modified files

| File | Change |
|---|---|
| `.env.v3.example` | Opt-in worker settings and automatic demo/live snapshot selection |
| `app.py` | News-only config/wrapper and read-only `/api/news/markets` endpoint |
| `src/news/ui_api.py` | Additive product wrapper, operational whitelist, stale state, poll interval; legacy API schema retained |
| `src/news/providers/perigon.py` | New independent `fetch_incremental_page`; existing fetch entry point unchanged |
| `static/js/news_ui.js` | Score hierarchy, geography, supplied reasons, polling, market rendering, portfolio editor/persistence/matches |
| `static/js/news_globe.js` | Update markers in place without recreating globe/camera; preserve source coordinates |
| `static/css/news.css` | Compact score strip, portfolio rows and restrained marker sizes |
| `templates/news.html` | Existing position editor supports persisted positions and removal |

## New files

- `src/news/live_config.py`: centralized operational settings.
- `src/news/live_runner.py`: incremental runner, durable queue/dedupe, quota guard and snapshot publication.
- `src/news/product_scores.py`: additive auditable relevance/urgency; does not alter original scores.
- `src/news/market_snapshot.py`: background sampling and read-only stale-aware snapshot reader.
- `static/js/news_product.js`: pure portfolio, persistence, score-formatting and polling-identity helpers.
- `tests/news/test_live_runner.py`, `test_product_scores.py`, `test_market_snapshot.py`, `test_product_api.py`.
- `tests/news_product_test.mjs`.
- `scripts/smoke_news_product_offline.py`.
- This report and `PRODUCT_INTEGRITY.json`.

No existing test was edited or relaxed in this upgrade.

## Ingestion, incremental coverage and failure behavior

One page is requested per cycle, with a fixed added-date window and persistent page number. The initial window is the previous hour. A short page completes the window, commits `last_successful_fetch_utc`, and the next window starts with a 120-second overlap. Full pages continue in later cycles without advancing the completion watermark. This bounds provider work; large backlogs can take multiple cycles.

The additive provider entry point uses the existing endpoint/authentication and raw-cache directory. Added-date bounds capture late-indexed articles rather than depending only on publication time. Parameters are documented by [Perigon Dates & Times](https://perigon.io/docs/api/dates-times). A fixed window protects pagination from newly added articles shifting the query, subject to provider indexing consistency.

Identity evidence is checked in order: provider ID, normalized URL, content hash, then headline/source/publication fallback only when stronger content identity is absent. Tracking parameters and URL fragments do not cause re-enrichment. Alias identities are retained. A changed article with an already-seen provider ID/URL is currently treated as the same article, not a revision event.

The cursor is committed only with its durable pending records. Pending records survive restart. Obvious cheap-filter rejects never call Gemini. Each useful new article uses the unchanged V3.1.6 pipeline and existing Analyzer cache. Cache identity includes content, prompt/schema version, provider and model; successful cache hits consume no new LLM quota. Existing failure results are not treated as completed research. Deferred records rotate behind other pending records to avoid starvation.

Both request limits count actual outbound generate attempts, including existing retries and model fallback. A durable daily reservation is written before every request, so crashes may conservatively overcount but do not undercount reserved requests. Limits are per state directory and UTC day. A process lock prevents simultaneous ingestion cycles sharing that state directory. Do not run independent state directories to share one provider quota.

Provider failure retains the last valid snapshot. Per-article enrichment failure leaves that article pending and allows other articles to complete. Successful complete records may be added while other records are pending; failed/half-built records never replace prior valid records. Operational status is written separately and marks this as degraded. Atomic JSON replacement uses the existing helper (temporary file, closed write, replace); no partially written snapshot is exposed.

The visible snapshot keeps the latest 500 completed records by processing order. Durable identity/history state is not pruned automatically; monitor disk size for long-running use. Missing/corrupt operational state fails conservatively rather than silently resetting paid-call accounting.

## Relevance and urgency policy

The old `quantitative.relevance` is a supported-terms heuristic, but does not enforce the required qualification hierarchy. It is preserved and reused as a small bounded bonus in new `product_relevance` / `product_scores` fields. These backend fields are separate from original research scoring and qualification.

Relevance = qualification-band base + 10 × existing normalized supported-terms value (clamped to 0…1).

| Backend relationship | Base | Possible range |
|---|---:|---:|
| Qualified direct event/company subject | 80 | 80–90 |
| Other Qualified exposure | 60 | 60–70 |
| Candidate requires review | 20 | 20–30 |
| Mention only | 10 | 10–20 |
| No supported relationship | 0 | 0 |

The bonus is zero when there is no relationship. Explicit Review qualification takes precedence over a contradictory relationship-type label. Article-level relevance is the maximum existing ticker relevance, never a fabricated ticker. Full original terms, base, bonus, method and interpretation are supplied for audit. These are internal research scores, not calibrated probabilities or financial-impact estimates.

Urgency:

```text
S = Critical 100 / High 80 / Medium 50 / Low 20 / Unknown 0
R = article-level relevance score
P = original priority Urgent 100 / High 80 / Medium 50 / Low 20 / other 0
D = exp(-ln(2) × nonnegative age_hours / 72), or 0 if date invalid/future
base = max(0.75 × S, 0.40 × R, 0.50 × P)
urgency = base × (0.75 + 0.25 × D), rounded to 2 decimals
```

Non-surface records receive zero and `Not surfaced`. Surface levels: High ≥60, Medium ≥30, Low >0; zero remains Review. Unknown severity supplies no established severity points; it does not establish safety. Recency cannot elevate a zero base. No sentiment, return labels, benchmark labels or post-event market movements are inputs. Scores are evaluated as of the snapshot generation time for deterministic replay, and include that timestamp. Old frozen events can have low current inspection urgency while retaining Medium severity/High relevance. No probability or direction is inferred.

## Panel and globe

The panel now puts Severity / Relevance / Urgency directly below the headline, followed by Event, separate Geography, distinct Qualified/Review groups and supplied reasoning. Financial impact/direction remain source-supplied; unavailable remains Unknown. Confidence, low-level score components and stale legacy prose remain in disclosures/Audit. Internal ordinal decimals displayed in Score Details carry their scale.

Selection uses the existing shared selection function. Polling retains the selected ID if it remains, clears it if removed, and preserves old results on API failure. Snapshot/marker identity checks avoid unnecessary rerendering and globe work. Changed marker sets update in place, preserving camera/country state. Severity changes attention only. Null geography never receives a marker. Existing screen-space separation preserves separate ST09/ST10 click targets without moving geographic anchors.

## Market data and portfolio

Uses the existing `src.data.yahoo_provider.history` boundary, not a second quote provider. The worker requests latest available unadjusted one-minute closes from five-day history. Absolute/percentage changes use the previous observed exchange-local session close. Timestamp, currency, source, definition and delayed/stale status accompany quotes. The project’s financial/current-price definitions are unchanged.

Mappings: Hang Seng `^HSI`, Shanghai A `000002.SS`, crude oil `CL=F`, Dow `^DJI`, S&P 500 `^GSPC`, Nasdaq `^IXIC`. Provider entitlement/availability is not assumed. Failed sampling keeps earlier quotes as stale; genuine missing values remain unavailable. Quote timestamps older than twice the market interval are stale, including closed-market periods. Sampling runs independently of news processing in the same standalone worker process (or via the market module). No per-frame/render/card provider calls occur.

Manual long positions (ticker, shares, average cost) are stored under browser-local `news_positions_v1`; add/update/remove up to 30 positions. Empty portfolio starts empty. Storage failure is disclosed as session-only. Value = shares × quote; basis = shares × cost; unrealized P/L = value − basis; percentage = P/L / basis ×100, with zero basis → N/M. Aggregation is USD-only: unsupported/missing/non-USD positions make total market value/P&L unavailable rather than misleadingly partial. Stale quotes may be used only with a visible stale label. No FX conversion or today's portfolio-change estimate is invented.

Only positive holdings with backend Qualified relationships produce Portfolio Match. Review/ownership alone do not qualify. Default equity quotes cover MAG7; configure additional US-dollar equity tickers explicitly in the worker. Browser position edits never trigger quote fetching.

## Configuration and commands

Use a local virtual environment with the existing project requirements. All commands below run from this extracted project directory. Copy `.env.v3.example` to a private `.env` and configure actual keys locally; never put them in source control or reports. Demo mode needs no key.

| Variable | Default |
|---|---|
| `NEWS_LIVE_ENABLED` | false |
| `NEWS_LIVE_INTERVAL_SECONDS` | 600 |
| `NEWS_LIVE_OVERLAP_SECONDS` | 120 |
| `NEWS_LIVE_PAGE_SIZE` | 50 |
| `NEWS_MAX_ARTICLES_PER_CYCLE` | 20 |
| `NEWS_MAX_LLM_CALLS_PER_CYCLE` | 6 actual requests |
| `NEWS_MAX_LLM_CALLS_PER_DAY` | 60 actual requests |
| `NEWS_LIVE_STATE_DIR` | data/news/live |
| `NEWS_LIVE_OUTPUT` | data/news/research/news_research_live_current.json |
| `NEWS_UI_POLL_SECONDS` | 45, minimum 30 |
| `NEWS_MARKET_ENABLED` | false |
| `NEWS_MARKET_INTERVAL_SECONDS` | 180, browser minimum 60 |
| `NEWS_MARKET_TICKERS` | AAPL,MSFT,GOOGL,NVDA,AMZN,META,TSLA |
| `NEWS_LIVE_QUERY` | MAG7 names plus semiconductor/economy/shipping; see LiveConfig |

Existing `LLM_PROVIDER`, `GEMINI_MODEL`, `GEMINI_API_KEY`, optional `GEMINI_FALLBACK_MODEL`, `LLM_CACHE_DIR`, timeouts and source policy are reused. `PERIGON_API_KEY` supplies the news provider. `NEWS_INTELLIGENCE_OUTPUT_PATH` is an optional explicit Flask override: leave unset for automatic demo/live selection. Frozen replay is never a worker destination.

Demo:

```sh
NEWS_LIVE_ENABLED=false python3 -m flask --app app run --port 5077
```

After local configuration, normal live operation:

```sh
# Terminal 1: enable live news and, optionally, delayed quote sampling in .env
python3 -m src.news.live_runner
# Terminal 2: same .env, separate process
python3 -m flask --app app run --port 5077
```

Open http://127.0.0.1:5077/news. Live mode does not silently fall back to benchmark articles before its first valid snapshot. Header shows LIVE / STALE / DEGRADED / DEMO; footer gives update age. Audit exposes safe operation counters and timestamps, never exception bodies or keys.

Optional market-only worker (do not run alongside an already market-enabled live runner):

```sh
NEWS_MARKET_ENABLED=true python3 -m src.news.market_snapshot
```

## Tests and observed results

Focused commands used by phase:

```sh
python3 -m unittest tests.news.test_live_runner -v
python3 -m unittest tests.news.test_product_scores -v
node tests/news_presentation_test.mjs
node tests/news_model_test.mjs
python3 -m unittest tests.news.test_market_snapshot -v
node tests/news_product_test.mjs
python3 -m unittest tests.news.test_product_api -v
python3 -m unittest tests.news.test_ui_api tests.news.test_v3.V3Tests.test_no_key -v
node tests/news_v316_integration_test.mjs
```

During development, only failed/added related test methods were rerun (daily budget; URL alias; one-article failure; unusable content). Focused live coverage includes dedupe across restarts, cache reuse, cycle/daily/retry quota, pagination, noise, disabled operation, atomic reader safety and failure preservation. Market coverage includes read-without-fetch, stale preservation, unavailable and disabled states. JS covers arithmetic, missing quotes, persistence, qualified-only linkage and retained/removed selection.

One full Python regression was executed after focused tests:

```sh
python3 -m unittest discover -s tests/news -t . -v
for f in tests/news*_test.mjs; do node "$f" || exit 1; done
```

Result: **440 Python tests passed in 59.325 seconds** (413 accepted tests +27 new tests). All **9 News JS suites passed**. The JS sequence found two existing confidence-disclaimer expectations after moving that content into a disclosure; the original explanatory wording was restored. Only failing/remaining JS suites were then run, not the whole regression again. Existing tests were not changed.

Modified Python compilation and JS syntax checks passed. A final visual-only score-strip CSS fix and neutral unavailable-P/L styling were checked in browser; modified JS syntax was rechecked.

Browser QA verified ST01/ST03/ST05/ST07/ST08/ST09/ST10/ST11 and reject ST12; original classification/severity/geography/qualifications were preserved. Normal feed 11; All Global Wire 12; six non-rejected markers. Both Hormuz markers were clicked independently. A temporary snapshot update preserved ST03 selection, then removing ST03 cleared it gracefully; globe canvas count remained one. Manual test positions persisted through reload. A mock NVDA quote of 120 against 10 shares at 100 cost displayed 1,200 value, +200 P/L and +20%; stale status remained visible. AAPL ownership alone did not create an AWS Portfolio Match. Test data lived outside the delivered project.

Offline end-to-end smoke (also executed successfully after regression):

```sh
python3 -m scripts.smoke_news_product_offline
```

Observed: one mock Gemini call, second-cycle duplicate skipped, two read-only Flask polls, **zero real News API/Gemini calls**. The smoke script explicitly blocks HTTP transports and uses a temporary directory.

## Minimal real live smoke: still requires local credentials

No Perigon/Gemini credentials or model were configured in this copy, so a real provider/Gemini smoke was **not run**. Do not interpret fixture validation as proof of provider entitlement, connectivity or model availability. After configuring keys and model locally, run one deliberately bounded cycle:

```sh
NEWS_LIVE_ENABLED=true NEWS_MARKET_ENABLED=false NEWS_LIVE_PAGE_SIZE=5 \
NEWS_MAX_ARTICLES_PER_CYCLE=2 NEWS_MAX_LLM_CALLS_PER_CYCLE=1 \
NEWS_MAX_LLM_CALLS_PER_DAY=1 python3 -m src.news.live_runner --once

NEWS_LIVE_ENABLED=true python3 -m flask --app app run --port 5077
```

Inspect the safe runner counters and UI. A successful first article is sufficient; others can remain deferred. Provider errors may use up to three news HTTP attempts. Only one actual Gemini request is allowed in this smoke, so transient failures may defer the article rather than succeed. Do not repeatedly rerun to chase success. Restore normal limits before ongoing operation. Persistent cache behavior was already proven offline, so an extra paid live cycle is unnecessary solely for cache QA.

## Integrity and remaining limits

The included integrity manifest compares this project to the accepted UI-integration directory. All original files except the eight explicitly listed integration/product files are byte-identical. In particular research_policy, event_geography, v3_validation, research_v3, v3_scoring, Analyzer/Gemini adapters, financial logic, exposure workbook, benchmark source/ground truth/manifest and frozen replay remain unchanged. The added Perigon function does not replace the old provider function. No benchmark labels enter new production logic.

Defaults are opt-in and no secrets ship. The complete project retains existing source/templates/tests/data. External live video playback was not tested. Yahoo values are delayed/unadjusted observations, not guaranteed real-time prices. No provider credentials means real live interoperability remains unverified. Windows is not currently supported by the Unix `fcntl` ingestion lock. This is a single-machine portfolio project: the durable JSON state needs manual monitoring/backup, not multi-host orchestration. A backlog or sustained quota shortage extends latency; status and pending counters disclose this. Research/quote snapshots are separate and may have different as-of times. The underlying frozen research limitations remain valid; no QA-grade/accuracy claim is added.
