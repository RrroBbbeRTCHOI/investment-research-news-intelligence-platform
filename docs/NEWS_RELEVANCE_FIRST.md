# News Intelligence — Relevance First V1

This standalone copy preserves the original system and adds a News-only research data contract. **The existing News page remains a labelled demo; this release does not connect or redesign HTML/CSS/JS.** Research Mode, Event Engine, exposure workbook, historical labels, ML models and old output artifacts are unchanged.

## Run the new backend

From this project folder:

```sh
python3 -m src.news.research_intelligence \
  --input data/news/normalized/tsmc_specificity_test.json \
  --output data/news/research/tsmc_run1.json
```

The CLI uses existing normalized articles and workbook. It performs no provider calls or ML training. `openpyxl` is the only workbook dependency, already listed in `src/news/requirements.txt`. No credentials are needed for this offline News run. Choose a fresh output filename for each run; existing artifacts are not overwritten. The legacy `python3 -m src.news.pipeline` command still works exactly as before.

The output contains an article list and an ordered research queue. Gate-rejected articles have no event/ticker analyses. Accepted events without qualified exposure may contain low-scored mention-only review candidates, or no ticker candidates. Queue order is explicit: evidence-based attention tier, relationship score, publication recency, stable event/ticker IDs.

## Six distinct concepts

| Field | Meaning |
|---|---|
| relevance_score | Relationship-only sum of existing weights: mention .15 + qualified edge .30 + country gate .15 + channel gate .15; quality/severity/ML excluded |
| legacy_relevance_score | Exact original matcher score, preserved for comparison; not a probability |
| evidence_strength | Existing curator verified/partial relationship status, separate article confirmation/source quality and independent-verification flag |
| economic_channels | Channels of qualified matched edges; candidate hypotheses remain a separate article field |
| materiality | Unknown/unquantified without event-specific financial scale; existing severity and exposure factors visible, not converted to an impact score |
| research_priority | High=qualified curator-verified edge; Medium=qualified partial edge; Review=mention only. Analyst attention, not financial magnitude |
| historical_reaction | Optional retrospective OOS context; never qualifies, scores or prioritizes a stock |
| direction | Always `Analyst judgment required` |

The maximum new relationship-only score is .75 by construction. It is not rescaled to a probability-like 1.0. Country/channel terms are correlated eligibility components, not separate statistical estimates. A lower score than the original mixed relevance metric is expected, not a regression. `relevance_level` describes qualification rather than applying optimized numeric thresholds.

`direct_exposure_match` means a named company also has qualified exposure records; it does not prove direct causal impact. `indirect_exposure_match` means a qualified unmentioned company. A company mention without exposure is never promoted to High. Synthetic tests and actual TSMC QA both cover the distinction.

## Optional historical context

Existing experiments remain available under `data/news/ml/`. To explicitly bind known articles to existing historical cases:

```json
{
  "article_to_case": {
    "historical_H31": "H31",
    "historical_H57": "H57"
  }
}
```

Then run:

```sh
python3 -m src.news.research_intelligence \
  --input data/news/normalized/historical_validation_H31_H60.json \
  --historical-map docs/relevance_first_examples/historical_case_map.json \
  --output data/news/research/historical_run1.json
```

`--historical-dir` can select a different existing ML artifact directory. No H-ID inference, event-type-only similarity matching, fabricated probability or new fitting occurs. The adapter requires matching source hash, explicit case/ticker identity, event classification/date, existing target values, mature training labels and all original threshold/model probabilities. Invalid/missing optional context stays unavailable without suppressing economic relevance.

Probabilities appear as **retrospective OOS diagnostics**, with model, 2/3/4% threshold, 3-trading-day horizon, training size, fold and run provenance. The top-level `probability` stays null because no single model/threshold is selected or averaged. Later-generated historical backfill is not represented as a live event-time forecast. The historical prediction artifact is not independently rerun by this adapter; this limitation is explicit. No stable incremental B2b signal has been established.

H31 and H57 examples intentionally remain mention-only Review candidates even when their historical diagnostics are available. A material price reaction does not create a qualified exposure.

## Output examples and limitations

- `relevance_first_examples/tsmc_research.json`: actual supplied 3-article TSMC QA; accepted fabrication maps AAPL Edge 6 and NVDA Edge 1; packaging maps NVDA Edge 2; training initiative rejected.
- `relevance_first_examples/historical_H31_H60_research.json`: actual supplied 30-case QA with optional explicit H31/H57 historical bindings.
- `relevance_first_examples/INPUT_COVERAGE.json`: new adapter results across all 11 supplied normalized inputs.
- `relevance_first_examples/FROZEN_BEHAVIOR_CHECK.json`: frozen gate/event/channel/matcher output digests unchanged across 146 article occurrences.

Workbook `verified` is a curator label. Some composite source locators include later publications than their record's known_at. The adapter preserves these records and explicitly distinguishes metadata eligibility from independently verified per-fact availability. It does not certify sources or silently change the workbook. Broad URL references, absent exposure quantities and unresolved company effects remain questions for the analyst.

Cross-provider semantic event clustering, new legal/pricing/acquisition exposure families, live ML inference and News page integration are not implemented. Existing frozen conservative no-match behavior is preserved. Do not treat these remaining limitations as permission to modify the frozen engine using historical QA performance.

## Tests

```sh
python3 tests/run.py
```

This is the repository's offline test runner. Do not use root-level discovery, which would import the legacy live `test_ui_data.py`. For News only:

```sh
python3 -m unittest discover -s tests/news -t tests
```

## Files added

Only `src/news/research_intelligence.py`, `src/news/historical_context.py`, two new News test modules and these News-specific docs/examples/verification artifacts. No existing product source, fixture, ML output, template or data cache changed. See the regression report and input hash verification.
