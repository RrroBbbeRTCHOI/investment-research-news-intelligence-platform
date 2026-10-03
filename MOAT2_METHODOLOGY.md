# Moat 2 methodology

All new rules interpret statements; none change EQ, Fundamental, Research, rating, valuation or DCF calculations.

## Periods and facts

Use at most five available annual income/cash report ends. The latest observation anchors the comparison even when incomplete; missing recent data does not silently switch the analysis to older years. Annual facts require ticker, fiscal-year label, FY type, currency and supported unit. A supplied start date must indicate 350–380 days. Adjacent comparisons require consecutive fiscal-year labels, report ends 350–380 days apart, identical source/currency/type/unit. Same-period ratios and cross-line bridges require matching metadata. Duplicate dates for a field become unknown. No TTM, quarterly or implicit-zero substitution is used. Different fiscal ends are not merged by calendar year.

Growth uses the existing historical growth function: valid positive bases retain signed growth; zero bases, negative bases and profit/loss transitions preserve N/M semantics. Absolute changes remain available for comparable periods even when growth is N/M. Opposite revenue/operating-income absolute movements still generate investigation priorities across a loss transition. CapEx growth is explicitly the growth in positive outlay magnitude when both provider amounts are nonpositive and prior outlay is positive; the displayed raw amounts retain the negative cash-outflow sign.

## Income and margins

Income lines are Revenue -> Gross Profit -> Operating Income -> Pretax Income -> Net Income. Adjacent growth gap equals right growth minus left growth, in percentage points. The direct Revenue -> Operating Income comparison is also retained when gross profit is absent. Margins equal the named profit divided by positive revenue. Margin directions use a 1 pp stability band.

Operating leverage: missing meaningful growth is unknown; both declining is separate; opposite signs are mixed; an absolute OI/revenue growth gap below 5 pp is roughly proportional; otherwise positive/negative operating leverage follows the gap sign. It does not assess management quality.

Below operating: pretax minus operating income is an investigation difference, never labeled total non-core earnings. An available other-income subtotal supports arithmetic only if it exactly reconciles both comparable years. Tax: effective tax rate = reported tax expense / positive pretax income. A >=10 pp pretax/NI growth gap is a large below-tax gap unless both years reconcile pretax minus tax expense to NI and tax-rate change of >=1 pp supports a headwind/tailwind label. Reconciliation tolerance reuses max(1 currency unit, 1e-6 relative scale). Matching narrative references are partial evidence and are never summed into a purported residual. A zero unresolved portion means subtotal arithmetic reconciles, not that the economic cause is established.

Cost rows independently show growth and revenue shares. SG&A, G&A, sales/marketing, SBC and D&A may overlap; no cost aggregation or efficiency judgment is made.

## Balance sheet and working capital

Available balance lines show amounts and comparable absolute/percentage movements. Current ratio = current assets / positive current liabilities. Quick ratio = (cash + short-term investments + receivables) / positive current liabilities, requiring every component. Cash/debt and debt/equity require positive denominators; net cash is cash minus debt. Changes of less than 0.1x in current ratio or debt/equity are structurally stable; otherwise direction is strengthening/weakening or leverage increasing/decreasing. These are not credit assessments.

Receivables/inventory/payables/contract liabilities are compared against revenue growth only when periods match. A >=10 pp excess with positive line growth marks a build; >=10 pp lag with falling receivables/inventory marks a possible working-capital release location. Payable support and working-capital release are structural investigation labels, not proven cash-flow contributions. Acquisitions, FX and reclassifications can explain stock changes.

## Cash flow and trend context

NI -> OCF -> signed CapEx -> FCF displays raw facts. OCF/NI is strong at >=1.0x, moderate at >=0.8x and weak below 0.8x for positive earnings. Negative earnings are explicitly separate; zero/missing earnings remain unknown. This is an explanatory ratio, not a new quality score or accrual model.

FCF = OCF + signed negative CapEx must reconcile for both years. FCF change is then OCF change plus signed CapEx change. Same-direction nonzero components are both; opposing/zero components are classified by the larger absolute contribution as OCF-driven or CapEx-driven; equal effects are offsetting; no FCF change is unchanged. The label describes arithmetic in either direction. CapEx/revenue and CapEx/positive OCF use positive outlay magnitude and reject unexpected positive provider CapEx signs. No growth-investment or return-on-investment claim is made.

Three or more comparable annual observations support compact signed-growth trends. Opposite latest growth directions are reversal; multiple historical sign reversals are unusually volatile; latest growth changes within 5 pp (margin changes within 1 pp) are consistent with trend; otherwise signed acceleration/deceleration. Missing intermediate periods preserve unknown. These labels are not forecasts.

## Significance and priorities

Absolute percentage-change bands: <5% minor, 5–<15% moderate, 15–<30% material, >=30% major. Absolute pp-change bands: <1 pp minor, 1–<3 pp moderate, 3–<5 pp material, >=5 pp major. Labels describe relative movement, not accounting materiality to total company earnings. Priority triggers are deliberately less sensitive than these descriptive bands.

High priority: opposite revenue/OI movements, >=30 pp bridge or receivable/inventory divergence, >=5 pp margin compression, or debt growth >=30% while cash falls. Medium: >=10 pp below-operating/below-tax/FCF divergence, OCF lags NI by >=10 pp, >=10 pp receivable/inventory build, >=3 pp margin compression, weak cash conversion, or current-period amount-linked unusual Moat 1 evidence. An amount alone is not called material; the priority asks the analyst to examine materiality. No trigger produces an Informational coverage note. Ranking is deterministic by level then rule identity; no generic LLM prose or directional stock recommendation is generated.

## V1.2 canonical balance field resolution

All tickers use the same annual balance request, raw-cache format and canonical schema. No company-specific mapping exists. The original FMP field remains authoritative when finite and usable (zero is valid). If absent/nonfinite/non-numeric, the normalizer examines an explicit list of equivalent spelling variants. Usable fallback aliases must agree; conflicting aliases remain Unknown. Each fallback preserves the actual source_field/evidence_id and adds canonical_field and normalized_from. No date, currency, source, unit or annual-alignment validation is bypassed. Raw provider rows stay unchanged in the existing cache; resolution occurs after loading, for each annual row independently.

Aliases are an explicit accepted input contract, not a claim that a different provider was fetched. The only configured transport remains the existing FMP loader. Broader totals and narrower components are intentionally excluded: cash plus investments is not cash; total equity including minority interests is not stockholders equity; total payables is not accounts payable; gross/trade receivables are not automatically the existing net receivables total; long-term debt alone is not total debt; noncurrent deferred revenue alone is not the current deferred-revenue line.

Accepted fallback spellings are listed in BALANCE_ALIASES in src/analysis/financial_statement_bridges.py. No fuzzy string matching or inferred arithmetic decomposition is used. Missing data still requires a real provider response; aliases cannot populate an absent annual statement.
