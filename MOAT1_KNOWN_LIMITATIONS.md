# Moat 1 V1 — Known limitations and separately approvable methodology

## Evidence coverage

- SEC validation is deliberately narrow: explicit annual USD tables with existing exact row patterns, clear scale and year columns. General narrative statements, many company-specific table layouts, inline XBRL-only formatting and foreign currencies remain insufficient evidence.
- The scoring keyword library and extractor still have incomplete category coverage. Investment gains and derivatives have weights but missing legacy extraction patterns; debt-security gains lack a legacy keyword topic. Asset-sale gains, restructuring, impairment and tax effects do not have complete scoring coverage. V1 does not silently add weights or change this legacy scoring behavior.
- The validation sidecar can recognize existing line patterns independently of the legacy keyword gate. These evidence-only observations do not affect scores. A recognized interest/other-income line is not automatically classified as non-core.
- Scoped subtotal reconciliation is not a complete core/non-core decomposition. It excludes unusual operating items and does not establish whether income will recur. The validated positive amount is a gross subset, not 100% minus core earnings and not a full non-operating share.
- Empty extraction, zero observed amounts and partial coverage do not yield an immaterial/all-clear diagnosis. The unchanged legacy score may nevertheless be high. The UI intentionally retains and labels this discrepancy.
- SEC Company Facts fallback tags retain their existing semantics. Strict end/start/accession checks reject many mismatches but do not prove every tag has an identical accounting scope.

## Data and comparisons

- FMP annual income/cash-flow data are used for six-way growth. Yahoo assets supply accrual denominators only when dates, year mapping and financial currency match. Missing assets/currency remain Unknown; V1 does not invent a denominator or use a receivables-only WC fallback.
- Exact fiscal dates and adjacent year labels are checked; annual durations in FMP remain provider annual metadata, not independently validated XBRL durations. Restatements, acquisitions, changes in consolidation and provider remappings may require analyst review.
- Diagnostic FMP ratios and frozen Yahoo scoring ratios can differ. Their sources and validity are exposed separately. Legacy ratios retain latest-available behavior rather than retroactively changing scoring methodology.
- Negative/zero-base growth states are N/M or turnaround rather than ordinary comparable growth. This can intentionally make the combined gap diagnosis Unknown even if some individual metrics are present.
- WC attribution requires a complete, sign-consistent reconciliation; available fields alone are insufficient. Arithmetic contributions do not prove temporary timing or structural improvement.

## Interpretation

- 10 pp investigation triggers and the combination of existing cash/accrual boundaries are explicit new interpretation rules, not changes to financial scores. They are heuristic research rules, not accounting standards.
- A current-period material item cannot by itself explain year-over-year growth. V1 explicitly avoids that causal conclusion.
- Supported sustainability is a limited historical/scoped assessment. It is unavailable without repeated cash support and scoped SEC reconciliation. Mixed or Concern describes observed evidence, not a forecast. No probabilities are produced.
- No multi-year recurrence inference, structural margin attribution, tax-benefit attribution, normalized/core earnings estimate or general forecasting is implemented. These remain unsupported rather than generated prose.

## Frozen weaknesses requiring separate approval

The legacy empty-events score of 100, inclusion of mismatched-year legacy events, incomplete category weights, and legacy sign/parser behavior are unchanged in scoring. Sign/period issues are rejected or corrected only in the independent validation sidecar. Altering their impact on scores requires explicit approval and explained baseline changes.

Other separately approvable changes include changing ROIC to NOPAT/average invested capital, using average assets in accruals, changing loss-company score interpretation, redefining recurring/core earnings, altering positive/negative netting, adding tax adjustments, changing weights/thresholds, or feeding diagnostics into rating/recommendation/DCF.

## Operational / validation scope

- Independent EQ does not require valuation, but the existing full research page still assembles ratings and the seven-company screener. New FMP histories and evidence validation can add first-visit calls. There is no claim that every route is cheaper.
- Existing TTL/cache architecture is retained. FMP history has its existing seven-day disk cache; source as-of/filing metadata does not imply real-time freshness.
- Regression uses synthetic Yahoo/SEC fixtures and supplied FMP histories. These are software validation data, not current investment conclusions. The seven frozen fixtures have insufficient strict SEC table coverage and lack usable aligned asset provenance for the new combined cash diagnosis; they intentionally remain Unknown in those areas.
- Tests and the browser check do not establish production-wide SEC precision/recall or validate every real 10-K layout. No live-provider benchmark or paid-provider calls were used for acceptance.
