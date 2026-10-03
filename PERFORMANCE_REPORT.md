# Performance report

## Method

Identical Phase 1 frozen provider inputs were replayed against the untouched Phase 1 copy and the refactored copy. Each of 42 cases starts with fresh application/service caches and a disposable empty FMP cache, then repeats the same route warm. A separate AAPL Overview → Valuation sequence measures cross-tab reuse.

Counts are observed provider-boundary reads (Yahoo info/statements/history and replayed SEC/FMP GET calls), **not measured live HTTP traffic**. Timings are one offline sample per case, not a production SLA or statistical benchmark. The original Phase 1 test run passed before migration.

## Cold request totals across seven tickers

| Tab | Before reads | After reads | Reduction | Median before s | Median after s |
|---|---:|---:|---:|---:|---:|
| overview | 1128 | 327 | 71.0% | 0.5304 | 0.2996 |
| financials | 672 | 245 | 63.5% | 0.3310 | 0.2007 |
| valuation | 1128 | 327 | 71.0% | 0.5336 | 0.2578 |
| historical-trends | 707 | 280 | 60.4% | 0.5947 | 0.5599 |
| earnings-quality | 1128 | 327 | 71.0% | 0.5345 | 0.2811 |
| sec-filing | 672 | 245 | 63.5% | 0.3319 | 0.1896 |

All 42 cold requests: **5435 → 1751 reads (67.8% fewer)**. All 42 warm repeats issued zero provider reads, preserving the original warm behavior.

AAPL Overview → Valuation: **78 → 0 additional reads**. The full rating result is reused; its fields are not removed or replaced.

## What changed

- Basic company data: one info, one 5d price series and one of each annual statement per request scope; repeated ROIC/metric reads reuse the same inputs.
- Selected-company basic results are shared with the screener.
- Historical P/E, DCF prepared inputs, SEC metadata/Facts/text and exact-parameter Yahoo histories reuse successful request-local results.
- Cross-tab rated-company results share a bounded TTL cache keyed by ticker and ordered peers.

## Reproduction and limits

Raw per-ticker/tab counts, breakdowns and times are in `tests/results/performance_before.json` and `performance_after.json`. Run `python3 tests/measure_performance.py PROJECT_ROOT OUTPUT_JSON` against a project copy. To remeasure Phase 1, use its unchanged archived copy; the current package does not contain a second production implementation.

Historical requests still require separate company/SPY/QQQ price histories and FMP data. Request copying and chart serialization consume local CPU, so a lower call count does not imply proportional live speedup. No real API calls were issued. Persistent caches remain per process; stripe collisions may serialize some unrelated loads.
