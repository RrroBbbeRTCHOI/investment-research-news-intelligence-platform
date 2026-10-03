# Moat 1 — Earnings Quality V1

Implemented in the existing copied/refactored project on 2026-09-09. The original project is not used as a write target. This document supersedes earlier architecture notes for the Earnings Quality feature only.

## Architecture

`earnings_quality_service.build_earnings_quality(ticker)` independently produces a reusable result. It imports neither valuation_service nor recommendation/rating orchestration. Its optional peers argument is compatibility-only; quality analysis is peer-independent.

- `get_scoring_bundle`: obtains existing quality components once, retains the full non-core report, builds the unchanged quality summary, and exposes the existing model's raw cash-conversion/accrual/ROIC/margin calculations.
- `rating_service.build_research_components`: consumes `get_scoring_summary`, without feeding new diagnostics into any scores or recommendation decisions.
- `earnings_quality_inputs`: reads existing annual FMP income/cash-flow payloads and Yahoo assets. It preserves field, period, fiscal-year label, ticker, currency, unit, source and availability. FMP payloads retain their original meaning; missing FCF is not silently replaced with FCFF or a new calculation.
- `earnings_quality_evidence`: a separate validation sidecar over SEC annual tables. It never modifies the legacy extractor, materiality report, non-core weights or legacy score.
- `earnings_quality_diagnostics`: pure deterministic analysis of normalized inputs and validated evidence.
- `research_context`: assembles the EQ result plus an independently acquired existing rating report to preserve the UI contract. The page and its screener can still require valuation; standalone EQ does not.

The existing shared cache implementation, its TTL, limits and locking are unchanged. New EQ scoring/diagnostic keys use that cache. Financial histories keep their existing FMP disk cache. New provider work for diagnostic history is explicitly measured, not presented as a universal reduction in page requests.

## Frozen methodology

No weights, score thresholds, quality labels, ROIC/cash-conversion/accrual formulas, non-core weights, rating/recommendation decisions, valuation, DCF or naming were changed. `quality.get_quality_summary` now optionally accepts already calculated components; its ordinary result contract and arithmetic are identical.

The legacy score can disagree with the new evidence assessment. For example, legacy empty SEC extraction can score 100 while the evidence sidecar says Insufficient Evidence. Both are retained and identified, rather than silently repairing the score. Legacy model raw ratios may use different sources/periods from the period-aligned diagnostic ratios; the UI explicitly separates them.

## Result contract

The standalone result includes:

- ticker, score_raw, classification, component scores, effective weights and weighted score contributions;
- legacy_quality_summary, legacy_model_inputs, scoring_error;
- inputs with periods, evidence IDs, raw values, availability and collection errors;
- growth_decomposition: revenue, operating_income, pretax_income, net_income, ocf and fcf growth;
- cash_support: current and historical cash-conversion/accrual observations, interpretation validity and evidence;
- identified_non_core_items: unchanged legacy positive/negative/ignored events plus independently validated/rejected events, duplicate references, amounts, ratios, pretax/source evidence, scope and reconciliation;
- working_capital: reported fields, reconciliation residuals, and changes only if both annual bridges reconcile;
- diagnostics and interpretation.

Every diagnostic contains rule_id, rule_version, type, severity, statement, exact inputs, evidence, availability, confidence status and reason when incomplete. Confidence is categorical evidence status, not a probability.

## Alignment and validity

All six growth series retain their individual validity states. Cross-metric gap conclusions require all six normal growth observations and matched current and previous period metadata. A metric's annual comparison requires consecutive fiscal-year labels, report-end separation of 350–380 days, identical source/currency/unit, and available values. Duplicate, missing and incompatible observations are not substituted with older convenient values. These checks cannot prove absence of restatements or provider mapping errors.

Growth reuses the existing historical `_calculate_growth`: zero/near-zero base -> N/M; negative-to-positive -> turned_profitable; positive-to-negative -> turned_loss_making; both negative -> N/M. EPS is not used as NI. Reported FCF is not modeled FCFF.

Cash conversion uses OCF / NI. Accrual uses (NI - OCF) / ending assets, with exact period/currency alignment. Assets are Yahoo annual balance-sheet values; their fiscal-year label is matched by exact FMP report end and their currency is taken from Yahoo financialCurrency. Missing currency/date matches remain Unknown. Negative NI or non-positive assets cannot establish cash support even where a numerical ratio exists.

## Explicit V1 interpretation rules (not scoring changes)

All rules are version 1.0. These interpretation rules are part of this approved V1 implementation and do not affect ratings.

| Rule | Conditions and output |
|---|---|
| EQ-CASH-01 | Positive NI, positive aligned assets, OCF/NI >= 1 and accrual <= 0 -> Supported cash observation. OCF/NI < 0.8 or accrual > 0.03 -> Concern. Other valid cases -> Mixed. Missing/incompatible/non-positive bases -> Unknown. Numerical ratios can still be displayed separately. Boundaries are drawn from existing score ranges; combining them is new interpretation logic. |
| EQ-GROWTH-01 | NI minus OI, pretax minus OI, or NI minus OCF growth >= 10 percentage points triggers investigation. All six normal aligned growth observations are required. 1e-12 ratio tolerance handles floating-point boundaries. No causal assertion is inferred. |
| EQ-NONCORE-01 | Identified known-weight items independently validated against matched annual SEC pretax and classified Material/Highly Material by the existing materiality function generate a review concern. Positive and negative directions are shown. No validated material event does not establish immateriality without scoped reconciliation. |
| EQ-FCF-01 | FCF minus OI growth >= 10 percentage points prompts caution. Causal arithmetic is described only when complete aligned bridges reconcile for both years. Partial fields produce an explicit incomplete-bridge statement. No structural/timing forecast is inferred. |

Working-capital validation checks: (1) cash-flow NI matches income-statement NI; (2) receivables + inventory + payables + other WC matches reported changeInWorkingCapital; (3) NI + D&A + deferred tax + SBC + other noncash + WC matches OCF; (4) OCF + signed CapEx matches reported FCF, with non-positive CapEx. Tolerance is max(1 currency unit, 1e-6 of compared scale). This is numerical reconciliation tolerance, not an economic materiality threshold. Receivables alone never substitutes for WC.

Sustainability is limited historical evidence assessment:

- Concern: current cash concern, growth-gap concern, or a validated material known-category SEC item.
- Supported: two adjacent Supported cash observations, six normal comparable growth observations without a triggered gap, no validated material item, a reconciled non-operating table scope, and current SEC period/pretax/OI values consistent with the diagnostic history. Supported applies only within that scope; no forecast or clean core-earnings assertion.
- Mixed: current valid cash-support result is Mixed and no stronger concern is present.
- Unknown / Insufficient Evidence: remaining cases. One good cash ratio or zero extracted events is insufficient for Supported.

Repeated event recurrence, structural margin change, tax causality, forecasting and broad core-earnings normalization are not inferred.

## SEC evidence handling

The sidecar requires a matching latest 10-K accession/report end and a positive SEC pretax value covering 350–380 days. It accepts only explicit annual, USD, known-scale tables with unambiguous year columns and exact existing financial-line labels. Parenthesis, ASCII minus and Unicode minus signs are parsed. Ambiguous values, currency/units, period columns and conflicting duplicates are rejected. Exact repeated table observations are deduplicated. Table text, URL, accession, table index, field, period and denominator evidence are retained.

Known topics retain existing weights as metadata; unknown/unweighted topics are not newly scored or reclassified. Full legacy positive/negative/ignored arrays remain accessible. New validated amounts are never fed back into scoring.

A narrow `reconciled_nonoperating_scope` is allowed only when all numeric detail rows are recognized known-weight categories, one other-income subtotal exists, no rejected evidence remains, and details sum to that subtotal and to SEC pretax minus operating income for the same accession and duration. Unusual items inside operating income, tax effects and recurrence remain outside this scope. Otherwise coverage stays incomplete, even when individual events validate.

## UI

The existing Earnings Quality tab retains score/classification, five scores, Core Revenue Unavailable, the legacy weighted contribution, Fundamental Score, Research Score and Research Interpretation. It adds score contribution transparency, analyst interpretation, six growth observations, cash history, SEC evidence, WC bridges and expandable rule/provenance details. Other tab template content, routes, CSS and JavaScript are unchanged.

## Run and test

Use Python 3.13 (the tested interpreter). From the extracted project root:

```bash
python3 -m pip install -r tests/requirements.txt
export FINANCIAL_API_KEY='YOUR_FMP_KEY'
export SEC_USER_AGENT='Your Name your-email@example.com'
python3 -m flask --app app run --host 127.0.0.1 --port 5000
```

Open http://127.0.0.1:5000/research?tab=earnings-quality. Normal application use accesses the existing live providers. No API keys are required for offline tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py
```

Standalone analysis: `from src.services.earnings_quality_service import build_earnings_quality; result = build_earnings_quality('AAPL')`.
