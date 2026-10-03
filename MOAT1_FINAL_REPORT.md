# Moat 1 V1.5 — Evidence integration completion

Continues the exact copied project delivered in `Stock-Screener-Moat1-V1.zip`. No architecture redesign. This report supersedes V1 descriptions of input selection and diagnostic completeness; V1 documents remain as historical records.

## Completed features

- Six annual growth metrics use existing FMP income and cash-flow history: revenue, operating income, pretax income, net income, operating cash flow, and reported free cash flow. Existing growth arithmetic and negative-base/turnaround/N/M semantics remain unchanged.
- Accrual assets now use the existing FMP annual balance-sheet loader, matching income/cash fiscal dates, year, currency and units. Yahoo is used only for entirely absent asset periods with validated metadata. Malformed/conflicting FMP periods remain unknown rather than being overwritten.
- OCF/NI and (NI−OCF)/end-period total assets expose current/history values, source, source field, source endpoint, fiscal date, and availability. Combined support requires positive NI and assets. A displayed ratio alone does not establish earnings quality.
- Growth comparisons validate each pair independently. A missing FCF value no longer hides a valid NI-versus-operating-income divergence. Each pair retains an evidence list and missing reason.
- Existing 10 percentage point investigation boundary is retained. FCF differences now trigger in either direction (absolute gap >=10 pp), including substantial FCF lag. No working-capital causality is suggested without a reconciling bridge.
- Existing SEC validation remains independent of frozen scoring. Rows expose exact item name/category, source, amount/sign, period, confidence, accession/table/quote, and denominator evidence. A filing-period materiality result only influences the current summary if its pretax period, currency and amount match the current statement. Historical evidence remains visible with an explicit limitation.
- Existing FMP income statements also expose reported other-income/expense and interest-income observations without further fetching. The net other-income subtotal receives a signed pretax comparison only when it reconciles to pretax minus operating income, with a positive aligned denominator. Interest income stays a reported field, without earnings-share attribution. These rows are not SEC-classified events, are never aggregated with SEC items, and never affect scores.
- `non_core_evidence` is an additive alias for the existing `identified_non_core_items` result. All existing frontend keys and sections remain. Sources/availability and evidence rows were added within the existing Earnings Quality sections; no CSS, JS, routes or other tabs changed.

## Frozen behavior

Rating, valuation, DCF, recommendations, Research Score, Fundamental Score, financial scoring formulas, EQ weights and classifications are unchanged from V1. Neutral naming, current-price distinctions, Core Revenue Unavailable and original N/A behavior remain. Diagnostic version is 1.5; frozen scoring is not re-versioned. No golden snapshots or provider recordings were regenerated.

## Architecture and reuse

Changes remain in the existing input adapter, diagnostic/evidence modules and EQ service. No new production module or provider. The existing historical provider API, disk cache, request reuse and service-cache implementation/TTL are untouched. The diagnostic cache namespace advances to `eq-diagnostics-v1.5` to distinguish the updated result schema; scoring cache is unchanged. `research_context.py` requires no modification because its existing adapter preserves additive fields.

AAPL offline provider-boundary measurements: independent EQ cold 10, repeat 0; full EQ company context cold 23; Overview to EQ 7; repeat page 0. Compared with V1's recorded 10/22/8/0 respective cold/context/switch/repeat measurements, not every path is cheaper. FMP assets add a useful dataset while avoiding the diagnostic Yahoo-info lookup when complete. Preloading all three historical endpoints causes zero additional FMP requests in EQ. Counts are replay boundary calls, not live latency or yfinance internal HTTP counts.

## Evidence limits and acceptance scope

Production wiring is complete for the existing sources; data availability is conditional on provider responses and validated metadata. The seven preserved FMP income/cash recordings provide all six growth metrics and OCF/NI. Only AAPL has a recorded FMP balance sheet, so its real recorded accrual ratio is available; the six other recorded cases intentionally remain Unknown for accruals. Separate explicitly synthetic balance-provider scenarios test successful alignment/calculation for all seven symbols; these are not claimed to be actual company assets.

The frozen SEC recordings still yield zero strictly validated annual table events. Existing synthetic SEC scenarios validate signs, units, denominators, duplicates, materiality, incomplete evidence and scoped reconciliation. This delivery does not claim live seven-company filing coverage, current financial accuracy, or universal 10-K extraction. Existing narrow exact-label annual USD table validation remains; unsupported layouts/categories/units stay Insufficient Evidence. Statement observations improve transparency even when strict SEC extraction is unavailable.

No complete core/non-core split, recurring-earnings inference, tax attribution, normalized earnings estimate, manipulation accusation or forecast is created. Reported FCF is not modeled FCFF. The legacy scoring layer can still show a strong score while new evidence is incomplete; this discrepancy is intentionally preserved. Acquisitions/restatements/accounting-scope changes still require analyst review.

## Verification and running

See `REGRESSION_REPORT.md` for results and `LIST_OF_CHANGED_FILES.md` for the exact file inventory relative to the delivered V1 ZIP.

From the extracted `Stock Screener` directory:

```bash
python3 -m pip install -r tests/requirements.txt
PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py
python3 -m flask --app app run --host 127.0.0.1 --port 5000
```

Open `http://127.0.0.1:5000/research?ticker=AAPL&tab=earnings-quality`.
The normal app needs the existing FINANCIAL_API_KEY and SEC_USER_AGENT settings, network access and provider entitlement. Tests are offline and need no live credentials. No credentials are included in the archive.
