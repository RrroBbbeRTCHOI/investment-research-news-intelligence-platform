# Relevance First V1 — Regression Report

## Result

- **278/278 News tests passed**, including all 254 existing News tests and 24 new tests.
- Complete project runner: **497 tests run, three failed subtests in one pre-existing integrity test**.
- Unmodified baseline copy: **473 tests run, the same three failed subtests**. Exact failure identities and compared file hashes match.
- **All 388 copied original files retain identical SHA-256 hashes**, including existing product code, tests, data, historical ML predictions/metrics, labels, workbook, UI assets and Research files. Only new files were added.
- Frozen gate, event objects, candidate channels and matcher outputs: **11 input files / 146 article occurrences / zero differences**. The adapter also retains the same event objects, candidate channels, raw matched evidence and legacy scores.
- Existing golden Research tests and ticker/tab checks passed. No snapshot was regenerated.

## Existing failures — not hidden or repaired

`tests/test_news_ui.py::NewsUITests::test_research_and_financial_sources_unchanged` has stale/different recorded hashes for:

- `data/cache/historical_financials/AAPL_balance_sheet_statement_5y.json`
- `data/cache/historical_financials/AAPL_cash_flow_statement_5y.json`
- `data/cache/historical_financials/AAPL_income_statement_5y.json`

All three actual files are byte-identical to the user's original input and the start-of-task hash capture. The unmodified input reproduces all three failures. Changing Research cache data or its old checksum manifest would cross the explicitly excluded scope, so neither was changed. Accordingly, **the full suite is not claimed green**. No previously passing test regressed.

## New behavior verification

17 research-assembly tests: qualified indirect match; mention-only review; named qualified exposure; unsupported relationship; future/expired/blocked/missing-provenance/time; explicit replay guard; temporal metadata disclosure; multiple ticker/edge aggregation; duplicate IDs; evidence-versus-relevance separation; severity/materiality separation; priority ordering; ML independence; rejected events; input immutability; safe new output writing; empty input.

7 archived-context tests: explicit valid binding and all 15 model/threshold records; no inferred case mapping; wrong event/ticker/date; bad source provenance; malformed probability/maturity/train membership/target; duplicate predictions; incomplete threshold outputs.

Original behavior comparisons use a fixed extraction timestamp of `2026-09-21T00:00:00Z` and the unchanged original replay resolver. Their full output digests, not just acceptance counts, are compared before/after. Inputs include H01–H120, provider sample, positive controls, stress cases and TSMC specificity QA. These are deterministic fixture checks, not independent validation of the real-world financial/exposure facts.

## Actual supplied examples

| Input | Accepted | Rejected | Qualified event/ticker pairs | Mention-only review candidates |
|---|---:|---:|---:|---:|
| TSMC specificity | 2 | 1 | 3 | 0 |
| H31–H60 | 28 | 2 | 2 | 28 |

Fabrication: AAPL Edge 6 and NVDA Edge 1, not packaging Edge 2. Packaging: NVDA Edge 2, not wafer-fab Edge 1. Employee training remains rejected. Explicit archived context for H31 and H57 is available as retrospective OOS context; neither gains a qualified exposure from ML.

## Scope

No provider calls or historical model retraining were made by the new pipeline. Existing offline tests still exercise their original synthetic ML fits. No model/threshold/feature/validation tuning occurred. No Research files, route, template, JS or CSS changed. No source evidence was independently fact-checked or dates revised.

## Commands

```sh
python3 -m unittest discover -s tests/news -t tests
python3 tests/run.py
python3 -m src.news.research_intelligence --input data/news/normalized/tsmc_specificity_test.json --output data/news/research/tsmc_run1.json
```

Use a fresh JSON output filename; existing files are preserved. The full runner will still report the three baseline integrity subtest failures described above.
