# V1.2 canonical balance schema regression

**171 tests passed in 61.164 seconds** (163 prior tests plus eight new alias tests). Source syntax, original-project hashes, unchanged UI/data and frozen golden hashes also passed.

Added eight test methods (with nested ticker/field/alias subcases) cover every accepted alias for all seven tickers plus ACME, both current and prior annual periods, raw transport -> atomic cache -> normalization -> second-request disk reuse, actual source-field provenance, all five liquidity calculations, working-capital comparisons, primary-value/zero preservation, malformed-primary fallback, conflicting aliases, missing fields, metadata guards and rejection of overlapping accounting totals.

All original golden fixtures and pre-implementation score/report fingerprints remain unchanged. AAPL is processed identically to every other ticker. The raw provider cache is not rewritten into a synthetic canonical dataset. Existing valid primary-field results retain their exact shape and values; only fallback aliases receive additional provenance keys.

Production change: src/analysis/financial_statement_bridges.py.
New tests: tests/test_balance_aliases.py.
Updated documentation: MOAT2_ARCHITECTURE.md, MOAT2_METHODOLOGY.md, MOAT2_REGRESSION_REPORT.md.

Available-response tests validate current and prior values for all twelve fields for AAPL, MSFT, GOOGL, NVDA, AMZN, META and TSLA, plus ACME. These are isolated synthetic HTTP responses passed through the real loader/cache; they do not establish new live provider coverage. The packaged historical data is unchanged: no live six-company balance histories have been fabricated or downloaded without credentials. A valid provider key/access remains necessary to fetch missing annual statements. Ambiguous values or incompatible source periods remain Unknown.

This section supersedes the older normalization description below; earlier audits are retained as release history.

---

# Moat 2 V1.1 balance-coverage audit

## Outcome and root cause

The original general pipeline already called balance-sheet-statement on a legitimate cache miss through the existing FMP loader and wrote successful responses to the existing cache. No ticker-specific production restriction or missing normalizer mapping was found. This environment has no effective FINANCIAL_API_KEY; the archive contains AAPL balance history but no corresponding histories for the other six. Income and cash work from their supplied caches. With no balance cache and no credential, the loader correctly rejects fetching. The old Moat 2 exception handler hid the specific cause as RuntimeError. Separately, the original offline replay deliberately returned HTTP 503 for its six unrecorded balance responses; that test-only behavior does not restrict production FMP fetching.

The production change only preserves actionable, credential-safe loader reasons in the existing limitations output. There was no basis for inventing a replacement downloader or changing financial methodology. Supplemental tests prove available-provider coverage through the actual generic loader and atomic cache writer, not a mocked completed Moat 2 service. **Live balance data completion for the six remains blocked by missing local FMP configuration.** No synthetic balance values were added to application caches.

## Tests

**163 tests passed in 62.633 seconds**: all 152 existing tests plus eleven supplemental balance-coverage tests. Source syntax compilation, original-project hash checks and unchanged golden/application-data hash checks also passed.

New tests exercise every ticker, all 12 mapped balance fields and their source/date/FY/currency provenance; the five liquidity ratios; four working-capital comparisons; debt/cash trend context; an actual AMZN Flask render with available provider data; AAPL's existing recorded result; missing individual fields; misaligned fiscal years, dates, currency and quarters; missing credentials; HTTP errors and successful retry; corrupt/expired caches; valid empty-response caching; repeat access across fresh request scopes; generic code; sanitized errors; and unchanged legacy cards, EQ and ratings when new balance data arrives.

Existing 152 tests remain in place, including frozen 42 ticker/tab and 98 report comparisons and pre-Moat-2 full-output fingerprints. The supplemental synthetic data is injected in memory inside isolated tests only. Golden fixtures and their manifest have not been updated.

## Actual packaged cache coverage (not synthetic test coverage)

The following audit calls the real Financials interpretation service against the supplied application cache with current local configuration. This validates metadata and normalization, not independent live FMP retrieval. Available means both annual values are comparable; no cache was fabricated to improve coverage.

| Ticker | Latest income/cash end | Comparable balance fields | Liquidity ratios | Actual balance status |
|---|---|---:|---:|---|
| AAPL | 2025-09-27 | 12/12 | 5/5 | Existing FMP-labelled cache; annual metadata matches |
| MSFT | 2026-06-30 | 0/12 | 0/5 | No balance cache; FMP key not configured |
| GOOGL | 2025-12-31 | 0/12 | 0/5 | No balance cache; FMP key not configured |
| NVDA | 2026-01-25 | 0/12 | 0/5 | No balance cache; FMP key not configured |
| AMZN | 2025-12-31 | 0/12 | 0/5 | No balance cache; FMP key not configured |
| META | 2025-12-31 | 0/12 | 0/5 | No balance cache; FMP key not configured |
| TSLA | 2025-12-31 | 0/12 | 0/5 | No balance cache; FMP key not configured |

For all seven tickers, the separate available-response tests establish 12/12 comparable balance fields, 5/5 liquidity calculations and 4/4 working-capital growth comparisons through the same generic path. Those are synthetic transport tests, not a claim that live providers supplied those values.

## Remaining Unknowns

In the packaged application, MSFT, GOOGL, NVDA, AMZN, META and TSLA retain Unknown for cash, short-term investments, receivables, inventory, current assets, total assets, payables, current liabilities, debt, liabilities, equity and deferred revenue because no annual balance response is available. Their current/quick ratios, cash/debt, debt/equity, net cash, working-capital comparisons and balance trends consequently remain Unknown. Their income and cash diagnostics continue to use their own existing data.

AAPL has all 12 comparable fields and five current liquidity ratios in the supplied cache. A genuine zero remains zero, but missing fields are never defaulted to zero. After provider data is obtained, individual fields may still legitimately be Unknown due to omission, unsupported metadata, duplicate rows, absent adjacent years, fiscal-date/currency mismatch or nonpositive ratio denominators. These rules are unchanged. Working-capital growth remains N/M where the prior base does not support a meaningful percentage.

## Exact changes

Modified:
- src/services/financial_interpretation_service.py — actionable sanitized source failures only; loader and arithmetic unchanged.
- MOAT2_ARCHITECTURE.md — verified loading/configuration behavior and recovery instructions.
- MOAT2_LIMITATIONS.md — distinguish original recording gaps from production coverage.
- MOAT2_REGRESSION_REPORT.md — this audit and explicit live-data limitation.

Added:
- tests/test_balance_coverage.py — eleven supplemental test methods, including seven-ticker subcases.

No templates, top Financials cards, provider files, normalizer, Moat 1 code, rating, scores, valuation, DCF, price definitions, weights, goldens or production cache data were changed. The original STOCK_SCREENER_MOAT2_V1 project is untouched. The following historical V1 report is retained as a record of that release; this V1.1 audit supersedes its coverage explanation.

---

# Moat 2 regression report

## Verification

Before implementation, the actual source-copy Financials contexts, all 14 report types and full Moat 1 outputs were recorded for all seven tickers. tests/financial_interpretation_reference.json stores the original contexts and canonical SHA-256 report/Moat 1 fingerprints. These are additional pre-implementation references; existing tests/fixtures and golden files were not rewritten. After implementation all compared fields and full fingerprints matched.

The prior Financials context comparison now excludes only the approved additive financial_interpretation key. The legacy source guard strips only the new template include before checking its prior hash. Financials is allowed to load annual data; the existing no-FMP rule still applies to unaffected tabs. New route tests cover the additive UI, while other tab rendering and frozen 42-route / 98-report comparisons remain enforced.

Final test command: `PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py`.

**152 tests passed in 54.433 seconds** (125 existing tests plus 27 new tests). Python source syntax compilation passed. Original project and golden-fixture SHA-256 checks passed.

## Before = after: original Financials cards

| Ticker | Revenue growth | ROE | ROIC | Operating margin | FCF margin | Debt/equity |
|---|---|---|---|---|---|---|
| AAPL | 4.0% | 30.0% | 25.9% | 15.0% | 13.5% | 0.45x |
| MSFT | 5.2% | 31.6% | 27.2% | 15.8% | 14.5% | 0.45x |
| GOOGL | 6.4% | 33.2% | 28.6% | 16.6% | 15.4% | 0.45x |
| NVDA | 7.6% | 34.8% | 30.0% | 17.4% | 16.4% | 0.45x |
| AMZN | 8.8% | 36.4% | 31.4% | 18.2% | 17.3% | 0.45x |
| META | 10.0% | 38.0% | 32.8% | 19.0% | 18.3% | 0.45x |
| TSLA | 11.2% | 39.6% | 34.1% | 19.8% | 19.3% | 0.45x |

## Before = after: report scores and valuation

| Ticker | EQ | Fundamental | Research | Rating | Base fair value |
|---|---:|---:|---:|---|---:|
| AAPL | 94.705882 | 76.332353 | 80.982794 | Buy | 40.586625 |
| AMZN | 96.470588 | 80.538235 | 68.296029 | Neutral | 97.480606 |
| GOOGL | 94.705882 | 79.832353 | 76.907794 | Buy | 75.775561 |
| META | 100.000000 | 85.450000 | 72.497500 | Neutral | 109.225369 |
| MSFT | 94.705882 | 79.832353 | 79.907794 | Buy | 57.604364 |
| NVDA | 96.470588 | 80.538235 | 80.296029 | Buy | 98.722793 |
| TSLA | 100.000000 | 85.450000 | 76.997500 | Neutral | 143.858415 |

The full reference comparison uses original precision, not these rounded report values. Existing Financials EQ/Fundamental/valuation fields that were N/A remain N/A; the table above reads their report outputs. No EQ, Fundamental, Research, rating, valuation, DCF, expected-return or benchmark logic was changed.

## MAG7 route and provider observations

| Ticker | Financials | Annual coverage | Leverage diagnostic | FCF driver | Cold offline seconds | Repeat provider calls |
|---|---|---|---|---|---:|---:|
| AAPL | HTTP 200 | available | roughly_proportional | both | 0.710 | 0 |
| AMZN | HTTP 200 | partial | roughly_proportional | capex_driven | 0.529 | 0 |
| GOOGL | HTTP 200 | partial | roughly_proportional | ocf_driven | 0.632 | 0 |
| META | HTTP 200 | partial | roughly_proportional | capex_driven | 0.636 | 0 |
| MSFT | HTTP 200 | partial | roughly_proportional | capex_driven | 0.504 | 0 |
| NVDA | HTTP 200 | partial | negative_operating_leverage | ocf_driven | 0.578 | 0 |
| TSLA | HTTP 200 | partial | both_declining | capex_driven | 0.769 | 0 |

All observations above use synthetic frozen data, not current investment conclusions. Full cold route measurements include the original seven-company screener: 120 recorded provider operations, of which three are the new annual income/balance/cash attempts (one each). The service itself does not invoke valuation, rating or EQ construction. A failed balance attempt remains unknown. Repeated cached page visits produced zero new calls; request-local repeated service calls also reused results. Offline timings are not live network benchmarks and no live speedup is claimed.

New numerical tests include annual/currency/duration alignment; duplicate/missing values; N/M and loss transitions; leverage and margins; below-operating/tax reconciliation; cost shares; receivable/inventory/debt/cash movements; liquidity; NI/OCF conversion; OCF-vs-CapEx FCF attribution; priority order and deterministic text; three-year trends; upstream evidence reuse/immutability; all-seven routes; no ticker-specific logic; independent service dependencies; exception isolation; cache reuse; and complete before/after output fingerprints.

Manual browser review was not completed because local server permission was rejected. Automated rendered routes all passed. This is an explicit outstanding visual-verification limitation.

## Exact file inventory

Modified:

- `src/services/financials_service.py`
- `src/ui/research_context.py`
- `templates/research.html`
- `tests/test_regression.py`

New:

- `MOAT2_ARCHITECTURE.md`
- `MOAT2_LIMITATIONS.md`
- `MOAT2_METHODOLOGY.md`
- `MOAT2_REGRESSION_REPORT.md`
- `src/analysis/financial_statement_bridges.py`
- `src/analysis/financial_statement_diagnostics.py`
- `src/services/financial_interpretation_service.py`
- `templates/financial_interpretation.html`
- `tests/financial_interpretation_reference.json`
- `tests/test_financial_interpretation.py`
