# Moat 1 V2 regression report

Final command: `PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py`

Result: **125 tests passed**, 43.277 seconds. This comprises the existing 100 tests and 25 additional V2 tests. Existing coverage includes all 42 ticker/tab combinations and 98 frozen report comparisons (14 report types across seven tickers). Additional tests cover provenance, period/quarter boundaries, amount ambiguity, grouping, recurrence, bridge reconciliation, FCF drivers, missing data, same-formula ROIC, unchanged scores, service independence, and seven Flask Earnings Quality route renders.

No golden snapshots were regenerated. All original fixture file hashes match. The original Pipeline V1 project file hashes match their pre-copy manifest. No baseline differences were observed in the regression suite. Python source syntax was additionally compiled without writing bytecode before packaging.

## Offline diagnostic observations

| Ticker | State | FCF attribution | Repeated standalone provider calls |
|---|---|---|---:|
| AAPL | Concern | mixed | 0 |
| MSFT | Concern | capex_increase | 8 |
| GOOGL | Concern | not_declining | 8 |
| NVDA | Unknown / Partial Evidence | not_declining | 8 |
| AMZN | Concern | capex_increase | 8 |
| META | Concern | capex_increase | 8 |
| TSLA | Concern | not_declining | 8 |

These are frozen synthetic fixture results, not live investment assessments. The six repeated-call cases inherit missing recorded balance-sheet responses that prevent successful standalone service caching. This release does not claim universal zero provider calls on repeat requests or a measured live-provider reduction. Existing request reuse and cache boundaries remain in place.

Manual browser visual checks remain incomplete for the permission/security reasons documented in MOAT1_V2_LIMITATIONS.md. Automated routes and rendered markup were checked.

## Changed existing files

- `templates/research.html`
- `data/research_keywords.json`
- `src/analysis/earnings_quality_narrative_evidence.py`
- `src/data/earnings_quality_inputs.py`
- `src/services/earnings_quality_service.py`

## Added implementation/test files

- `tests/test_moat2.py`
- `data/earnings_quality_rules.json`
- `src/analysis/earnings_quality_research_evidence.py`
- `src/analysis/earnings_quality_attribution.py`
- `src/analysis/earnings_quality_research.py`

The four MOAT1_V2 documentation files are also included.
