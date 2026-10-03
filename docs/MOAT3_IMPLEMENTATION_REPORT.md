# Moat 3 V1 implementation and validation report

Project: `STOCK_SCREENER_MOAT3_V1_VALUATION_EXPECTATIONS`

## Delivery and architecture

A standalone copy adds valuation interpretation inside the existing Valuation tab. Acquisition and normalization live in `src/data/valuation_inputs.py`; pure cash-flow, cost-of-capital, reverse-DCF and interpretation modules live in `src/analysis/`; the new service coordinates them. The existing valuation service invokes this producer only for Valuation, not Overview. One template include presents results and collapsed methodology. Existing provider loaders, request reuse and caches are reused.

## Files created

- `data/valuation_assumptions.json`
- `docs/MOAT3_IMPLEMENTATION_REPORT.md`
- `docs/MOAT3_METHODOLOGY.md`
- `requirements.txt`
- `src/analysis/cost_of_capital.py`
- `src/analysis/reverse_dcf.py`
- `src/analysis/valuation_cash_flows.py`
- `src/analysis/valuation_interpretation.py`
- `src/data/valuation_inputs.py`
- `src/services/valuation_interpretation_service.py`
- `templates/valuation_interpretation.html`
- `tests/moat3_legacy_reference.json`
- `tests/moat3_market_fixture.json`
- `tests/test_moat3.py`

## Files modified

- `src/services/valuation_service.py`
- `src/ui/research_context.py`
- `templates/research.html`
- `tests/support.py`
- `tests/test_refactor.py`
- `tests/test_regression.py`

## Exact methodology and boundaries

- Reported FCF retains its existing definition. FCFF = EBIT × (1 − normalized tax) + D&A − positive CapEx outlay − Δoperating NWC. FCFE = net income + D&A − positive CapEx outlay − Δoperating NWC + net borrowing. They are not interchangeable.
- Preferred operating NWC = (current assets − cash − short-term investments) − (current liabilities − borrowing short-term debt − identified current lease debt), with reconciliation guards. Complete explicitly operating components are the fallback. Missing inputs and incompatible periods stay Unknown.
- Tax uses the median of three valid recent annual ETRs; two valid observations are an explicit fallback. Nonpositive pretax income, implausible rates and relevant existing tax evidence exclude observations. A dated configured statutory fallback is supported but not supplied by default.
- Net borrowing prefers cash-flow issuance less repayment, or a signed provider net issuance amount. Matched book borrowing-debt movement is a labelled fallback excluding identified lease movement. Otherwise Unknown.
- Re = dated Rf + beta × versioned ERP. WACC uses market-cap equity weights and book borrowing debt as an explicit market-debt proxy: E/(E+D) × Re + D/(E+D) × Rd × (1−T). Preferred capital requires supported inputs. Rd accepts a dated supplied market yield; otherwise positive interest / average borrowing debt is an accounting proxy. No usable Rd on positive debt means Unknown WACC.
- Rf uses existing Yahoo ^TNX historical quotes, with a dated NYU reference fallback. Beta uses observed company/SPY returns (5Y monthly, then alternative observed frequency/window), provider beta, or explicitly low-confidence beta=1 if permitted. No peer-beta engine is invented.
- Shipped ERP is versioned NYU September 2026 4.14%. Terminal growth is 2.0%, anchored to the Fed longer-run inflation reference with a zero-real-expansion mature-business platform convention. Both have source/date/expiry metadata; they are not universal truths or company forecasts.
- Market EV is a Yahoo provider proxy, not an invented excess-cash bridge. Book debt, cash, investments, preferred/NCI and an unclassified residual are exposed; cash is not subtracted twice and all cash is not classified as excess.
- Primary FCFF solves against EV at WACC; secondary FCFE solves against market cap at Re. Five years is a platform convention. Bisection is deterministic on [−95%, 300%], with explicit invalid/no-solution states and Gordon terminal growth strictly below the discount rate.
- Sensitivity uses discount-rate offsets −1, −0.5, 0, +0.5, +1 percentage points and terminal offsets −0.5, 0, +0.5 points. It reports valid-cell ranges and one-axis drivers. Model differences above a documented 10-point comparison band trigger reconciliation; models are never averaged.
- Historical PE reuses the existing annual fiscal-date proxy with timing limitations. Historical growth uses valid contiguous annual periods. Numerical gaps and conditional prose do not become ratings, forecasts or causal accounting claims.

Detailed input hierarchies, formulas, confidence, dates, expiry and external references: [MOAT3_METHODOLOGY.md](MOAT3_METHODOLOGY.md).

## Regression results

`python3 tests/run.py`: **211 tests passed in 70.881 seconds** (171 existing and 40 new test methods). The existing suite covers 42 ticker/tab combinations. New checks cover seven complete Valuation renders, all seven legacy valuation-context fingerprints, 14 report outputs per ticker, and complete Moat 1/Moat 2 output fingerprints. Existing ratings, recommendations, Fundamental/Research/Earnings Quality scores and legacy valuation outputs matched. No golden snapshots were regenerated.

The original project’s 126 file hashes match the pre-implementation manifest. Original frozen fixture files and all model files are byte-identical in the copy. Only the six existing files listed above differ. New `moat3_legacy_reference.json` was captured before product changes; it supplements rather than replaces Phase 1.

Test integration adjustments are explicit: `support.py` merges a separate synthetic ^TNX recording in memory, without altering original recordings or allowing network access. The regression comparator removes only the approved additive Moat 3 context/include when checking legacy contracts. Two legacy provider-budget tests isolate the new producer so their original legacy dependency assertions remain valid; actual new provider transport, combined legacy-output fingerprints and repeat-cache behavior are tested separately without that isolation. The expanded Valuation page has semantic/render tests rather than an unchanged whole-page golden HTML claim.

Validation used Flask test-client renders and HTML assertions, not a manual browser visual review. No live provider latency benchmark or current investment conclusion is claimed.

## Seven-ticker complete-input transport test

**TEST-ONLY SYNTHETIC INPUTS — not current company valuations.** Each name uses complete synthetic annual FMP rows, market cap 5,000, EV 5,100, test ERP 5%, terminal 2%, and frozen Yahoo price histories. Thus the negative implied growth below is a solver/transport result, not a financial recommendation. All use accounting Rd proxy 5.2381%, normalized tax 20% (3Y median), provider EV proxy, and explicitly dated test RF. The test configuration is separate from shipped production assumptions.

| Ticker | FCFF / FCFE | WACC | Re | Implied FCFF | Implied FCFE | FCFF sensitivity range | Consistency |
|---|---|---:|---:|---:|---:|---|---|
| AAPL | Available / Available | 3.95% | 3.94% | -13.09% | -13.87% | -34.94% to -2.51% | Within configured comparison band |
| MSFT | Available / Available | 4.46% | 4.47% | -8.89% | -9.44% | -24.49% to 0.37% | Within configured comparison band |
| GOOGL | Available / Available | 3.90% | 3.88% | -13.57% | -14.38% | -36.51% to -2.83% | Within configured comparison band |
| NVDA | Available / Available | 4.13% | 4.13% | -11.49% | -12.18% | -30.43% to -1.44% | Within configured comparison band |
| AMZN | Available / Available | 4.33% | 4.34% | -9.87% | -10.47% | -26.60% to -0.33% | Within configured comparison band |
| META | Available / Available | 4.88% | 4.92% | -5.81% | -6.22% | -18.71% to 2.60% | Within configured comparison band |
| TSLA | Available / Available | 4.15% | 4.15% | -11.35% | -12.03% | -30.09% to -1.35% | Within configured comparison band |

Both models converged for all seven on the same generic path. Remaining test-input limitations include provider-market field timestamps, book-debt/EV proxies and unsupported detailed non-operating asset classification; these are not silently promoted to observed facts.

## Packaged annual-cache inspection (not live market validation)

This read-only inspection uses the supplied FMP cache rows without independently verifying them against filings. No new live price, EV or beta was fetched. The source copy contains AAPL balance history but lacks the other six balance histories. The generic existing FMP cache-miss loader is retained and exercised by tests; this delivery does not manufacture or backfill missing provider observations.

| Ticker | Starting FCFF, USD | Starting FCFE, USD | Normalized tax | Debt cost / WACC | Reason |
|---|---:|---:|---:|---|---|
| AAPL | 95,123,891,892.50 | 86,370,000,000.00 | 15.61% | Unknown | Positive usable interest / average borrowing debt unavailable; zero interest is not a free-debt assumption. |
| MSFT | Unknown | Unknown | 18.23% | Unknown | Annual balance history absent: operating NWC change and borrowing-debt inputs cannot be supported. |
| GOOGL | Unknown | Unknown | 16.44% | Unknown | Annual balance history absent: operating NWC change and borrowing-debt inputs cannot be supported. |
| NVDA | Unknown | Unknown | 13.26% | Unknown | Annual balance history absent: operating NWC change and borrowing-debt inputs cannot be supported. |
| AMZN | Unknown | Unknown | 18.96% | Unknown | Annual balance history absent: operating NWC change and borrowing-debt inputs cannot be supported. |
| META | Unknown | Unknown | 17.56% | Unknown | Annual balance history absent: operating NWC change and borrowing-debt inputs cannot be supported. |
| TSLA | Unknown | Unknown | 23.70% | Unknown | Annual balance history absent: operating NWC change and borrowing-debt inputs cannot be supported. |

For every ticker in this cache-only inspection, current Re, market-implied growth, model consistency and sensitivity are **not live-validated** because market inputs were not fetched. AAPL has reconstructable starting cash flows but no usable accounting Rd, so positive-debt WACC/primary expectations remain unavailable without supported debt-cost evidence. FCFE can operate independently when equity-market inputs are available. For the other six, missing balance observations prevent both reconstructed cash flows. Genuine absent preferred/NCI, lease or working-capital fields may still limit results after fetching. Source fields are never replaced with zero.

## Provider reuse and performance

| Ticker | Cold offline seconds | Cold provider calls | FMP statement calls | Same-scope repeat calls |
|---|---:|---:|---:|---:|
| AAPL | 0.107 | 13 | 3 | 0 |
| MSFT | 0.099 | 13 | 3 | 0 |
| GOOGL | 0.103 | 13 | 3 | 0 |
| NVDA | 0.128 | 13 | 3 | 0 |
| AMZN | 0.098 | 13 | 3 | 0 |
| META | 0.088 | 13 | 3 | 0 |
| TSLA | 0.085 | 13 | 3 | 0 |

Each cold generic transport test fetches income, balance and cash-flow statements once each, writes through existing caches and normalizes them. Repeat service access makes zero provider calls; page-repeat tests likewise check cache reuse. Calls also include beta/market history and existing historical PE inputs. These offline timings cannot establish live wall-clock performance or a reduction versus a pre-Moat-3 page, which did not compute these features. No cache architecture was replaced.

## Remaining limitations and operation

The constant five-year growth model, positive starting cash-flow requirement, bounded solver, retrospective PE proxy, mixed market/accounting dates, lease/EV reconciliation and historical debt-cost proxy are visible limitations. There is no automatic corporate-bond yield feed, peer-beta unlever/relever system, preferred yield feed or live ERP downloader. External assumptions must be maintained; expired values intentionally become Unknown. Missing Moat 1 detailed SEC context is not clean evidence. None of these limitations changes legacy scores or ratings.

Existing root milestone reports are retained as historical documentation; this report and the Moat 3 methodology describe the new milestone. No separate static assets were needed: the source project uses its existing template styling, and no empty static architecture was added.

Setup (Python 3.13 baseline):

```sh
python3 -m pip install -r requirements.txt
# Add your own .env/provider credentials locally.
python3 tests/run.py
python3 app.py
```

The deliverable ZIP includes the complete project and required supplied cache/test data, excluding secrets, environment files, virtual environments, generated test results and bytecode. ZIP name: `STOCK_SCREENER_MOAT3_V1_VALUATION_EXPECTATIONS.zip`.
