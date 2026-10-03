# Moat 1 V1.5 regression report

## Result

78 test methods passed in 36.753 seconds (Python 3.13). All 66 V1 methods remain; one V1 partial-data expectation now checks the invalid NI/OCF pair specifically, because valid independent pairs are intentionally retained. Twelve V1.5 tests cover recorded inputs, synthetic integration, conservative missing behavior, diagnostic isolation and rendered output.

- All 42 ticker/tab combinations return 200 and preserve existing context fields outside the approved EQ diagnostics.
- All 14 legacy report types across 7 tickers (98 report comparisons) match the original golden outputs, including rating/valuation calculations.
- Fixture manifest integrity passes. Providers, baselines, provenance and manifest are unchanged from the delivered V1 ZIP.
- Non-EQ template prefix/suffix hashes and original non-EQ HTML rendering remain unchanged.
- EQ score/component fields, Core Revenue Unavailable, Neutral recommendation naming and distinct price definitions remain covered.
- Independent EQ still passes tests with valuation, DCF and rating calls patched to fail.

## Intentional diagnostic differences, not golden changes

AAPL accrual availability improves with recorded FMP assets. Growth gaps can now be partially available; valid pairs are no longer suppressed by unrelated missing data. Absolute FCF gaps trigger review in either direction. Stale/mismatched SEC events cannot set the current-period sustainability summary. Statement evidence and provenance are additive. No golden snapshot was regenerated to accept these differences.

## Preserved recorded data results

These are the supplied recordings, not a live market verification.

| Ticker | Latest recorded period | Normal growth metrics | OCF/NI | Accrual ratio | Statement / validated SEC items |
|---|---|---|---|---|---|
| AAPL | 2025-09-27 | 6/6 | 0.995286x | 0.1470% | 2 / 0 |
| MSFT | 2026-06-30 | 6/6 | 1.367749x | Unknown (no recorded aligned assets) | 2 / 0 |
| GOOGL | 2025-12-31 | 6/6 | 1.246221x | Unknown (no recorded aligned assets) | 2 / 0 |
| NVDA | 2026-01-25 | 6/6 | 0.855506x | Unknown (no recorded aligned assets) | 2 / 0 |
| AMZN | 2025-12-31 | 6/6 | 1.796241x | Unknown (no recorded aligned assets) | 2 / 0 |
| META | 2025-12-31 | 6/6 | 1.915379x | Unknown (no recorded aligned assets) | 2 / 0 |
| TSLA | 2025-12-31 | 6/6 | 3.886927x | Unknown (no recorded aligned assets) | 2 / 0 |

The original fixture set lacks six FMP balance endpoint recordings. Replay explicitly returns an unavailable HTTP response for those exact six known endpoints, without permitting arbitrary unrecorded requests or fabricating assets. Separate in-memory synthetic balance responses prove the adapter and formula for all seven symbols. Original fixture files remain byte-identical.

## Scenarios exercised

Missing, duplicate, non-adjacent and incompatible periods; ticker/currency/unit mismatches; negative normal growth; zero/negative denominators; loss/profit turnaround and N/M; cash conversion/accrual math; incomplete WC bridges; normal and partial growth comparisons; positive/negative FCF gaps; reconciled/unreconciled statement subtotals; overlap warnings; old SEC evidence isolation; missing SEC evidence; SEC signs/units/annual durations/accessions; duplicates/conflicts; unavailable categories; no false all-clear; repeated cache reuse; actual Flask/Jinja rendering of values and existing sections.

No live SEC precision/recall benchmark or browser visual regression was performed in V1.5. Flask-rendered contract tests and unchanged non-EQ hashes cover the bounded UI changes.

## Commands

```bash
python3 -m pip install -r tests/requirements.txt
PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py
python3 -m flask --app app run --host 127.0.0.1 --port 5000
```

Older `MOAT1_REGRESSION_REPORT.md` records V1 results; this document is the current V1.5 report.
