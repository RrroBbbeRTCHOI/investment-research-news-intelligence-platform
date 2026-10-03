# Moat 3 — valuation interpretation and market expectations

## 1. Objective and frozen boundary

Moat 3 asks what constant five-year cash-flow growth would reconcile a stated market valuation with explicit discount-rate and terminal assumptions. It does not forecast earnings, price targets or returns, and it never writes Recommendation, Rating, Research/Fundamental/Earnings Quality scores or legacy valuation results. The original Valuation cards remain visible. Their legacy implied-growth figure is a separate model, not a second presentation of the new result.

## 2. Four different kinds of methodology

| Class | Examples | Treatment |
|---|---|---|
| Standard finance theory | FCFF/WACC/enterprise value, FCFE/cost of equity/equity value, CAPM, Gordon terminal value | Correct cash-flow/discount/claim matching |
| Platform conventions | 5Y constant explicit growth, 3Y median ETR, solver bounds, sensitivity grid, 10 pp cross-check review band | Versioned and documented; not CFA mandates |
| External market/macro assumptions | US implied ERP, Treasury yield reference, longer-run inflation anchor | Source, observation/release date, version, expiry |
| Proxies/fallbacks | Book debt, historical interest/debt, provider EV, beta fallback, component NWC | Visible method, confidence and limitation |

Institutions share broad valuation theory; they do not all use identical proprietary forecasts, risk premia or normalization conventions. This implementation is not endorsed by any referenced institution.

## 3. Reported FCF, FCFF and FCFE

Reported FCF remains the existing provider financial-statement measure, ordinarily operating cash flow minus positive capital expenditure outlay. FMP's signed negative CapEx is displayed separately; it is not subtracted a second time. Reported FCF is never relabelled FCFF.

New FCFF = EBIT × (1 − normalized tax rate) + D&A − positive CapEx outlay − change in operating NWC. New FCFE = net income + D&A − positive CapEx outlay − change in operating NWC + net borrowing. SBC is not silently added as D&A. These calculations do not replace the legacy weighted FCFF model.

FCFF is compared with enterprise value and discounted at WACC. FCFE is compared with common-equity market capitalization and discounted at cost of equity. These pairings and the general free-cash-flow models are standard valuation theory. [CFA Institute: Free Cash Flow Valuation](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/free-cash-flow-valuation).

## 4. Annual data normalization and provenance

Existing FMP income, balance and cash-flow loaders and seven-day atomic caches are reused. Moat 2's canonical field resolver and metadata validation are reused without editing that module. Moat 3 adds interest expense, explicit borrowing/lease fields, preferred/NCI observations, explicitly operating residual balances and financing cash-flow fields to its own normalized view.

Each fact records ticker, source field, source endpoint, fiscal year, date, FY type, currency, units and availability. Cross-line calculations require matching annual metadata; adjacent changes require consecutive fiscal years and 350–380 days between report ends. Duplicate, unsupported, missing or future annual periods cannot become supported inputs. Only USD market/statement combinations are used with the packaged USD assumption set. Missing cash, investments, debt, expenses or residual components are not imputed to zero.

## 5. Operating working capital

Preferred bridge:

Operating NWC = (Current Assets − Cash − Short-Term Investments) − (Current Liabilities − Short-Term Borrowing Debt − Current Lease Debt).

When current lease debt is positive, reported total debt must reconcile to short debt + long debt + total identified lease obligations before the two current debt categories can be excluded together. Otherwise overlap is unresolved. Negative residual operating-current-asset/liability subtotals are rejected.

Component fallback requires all of receivables, inventory, explicitly other operating current assets, payables, accrued operating liabilities, deferred revenue and explicitly other operating current liabilities. Generic other-current balances are not assumed operating. The same reconstruction method and aligned facts must support both years.

Delta NWC = current minus prior NWC. A positive delta is arithmetic cash use and a negative delta arithmetic release. This balance-sheet bridge is a proxy: acquisitions, FX, tax balances, reclassification and other non-operating residuals can intervene. It does not establish cash-flow causality.

## 6. Normalized tax

For the latest three consecutive comparable annual observations, ETR = tax expense / positive pretax income. Rates outside [0%, 60%], missing/alignment failures and validated period-matched unusual Moat 1 tax evidence are excluded. The economic validation interval is a platform safeguard, not a universal tax rule.

Three valid observations use their median. Two use an explicitly labelled median fallback. Fewer than two require a fresh, fully documented statutory/blended reference configured in the assumption file; none is supplied by default. Otherwise normalized tax remains Unknown. A single valid year is not silently promoted to a sustainable rate.

The UI lists rates, periods used, exclusions, reasons, method and confidence. Cached Moat 1 narrative evidence is read, not reclassified or converted into an invented adjusted rate. Without cached narrative evidence, accounting observations can support a median but cannot establish absence of one-time tax items. Historical FCFF uses the same rolling normalization convention at each historical starting date; older windows may be insufficient.

## 7. Net borrowing

Priority 1: separately supplied positive debt issuance minus positive debt repayment, or the provider's signed netDebtIssuance financing-cash-flow amount. No overlapping net and gross components are summed.

Priority 2: change in matched short + long borrowing debt, explicitly labelled BALANCE-SHEET PROXY. Separately identified lease-balance movement is not added. FX, acquisitions and reclassification can make this differ from financing cash flows.

Priority 3: Unknown. FCFE may fail independently while FCFF remains available. Preferred capital without supported common-equity income allocation also prevents the common FCFE cross-check.

## 8. Cost of equity and beta

CAPM: cost of equity = risk-free rate + equity beta × market ERP.

Preferred observed beta is covariance of company and SPY monthly adjusted-price returns divided by SPY return variance, using up to five years and at least 36 observations. The alternative uses up to two years of weekly returns with at least 52 observations. Common sampled endpoints are used; incomplete current month/week endpoints are excluded. SPY is a market proxy. The Yahoo price adjustment convention is inherited from the existing provider.

If those windows are insufficient, Yahoo info.beta is an observed-provider proxy with its undisclosed window/date shown as unknown. If no beta is available, the configuration can permit 1.0, explicitly labelled Fallback Assumption and Low Confidence. V1 does not fabricate peer unlever/relever data. Nonpositive resulting cost of equity is invalid for this model.

## 9. Risk-free rate

The existing Yahoo market-data loader reads ^TNX's US ten-year nominal Treasury yield quote (Close in percent, divided by 100). A dated observation no older than seven calendar days is required. This is a Treasury-yield quote proxy, not a direct Treasury API connection.

If unavailable, a dated configured reference can be used within its stated maximum age. The shipped reference is 4.75%, associated with the September 1, 2026 Damodaran ERP publication, with a 30-day validity window. Its date is the reference release date, not an asserted direct Treasury trading observation. It is visibly Fallback / Low Confidence and marks the current quote unavailable. Once expired, it becomes Unknown rather than a permanent rate.

The risk-free result uses the existing bounded shared service cache (300 seconds). Observation age is separate from cache age. [Damodaran's source publication](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/home.htm).

## 10. ERP

The shipped external assumption is the September 1, 2026 US implied ERP of 4.14%, using Damodaran's trailing twelve-month adjusted-payout convention paired with a nominal Treasury risk-free convention. It is a market-level assumption, not a company-specific premium. The version and source are in data/valuation_assumptions.json; the maximum age is 62 days. No undocumented US default-spread adjustment is applied. A newer Treasury quote combined with this dated ERP remains a mixed-frequency assumption, not a daily recalibration of implied ERP. [External ERP source](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/home.htm).

## 11. Cost of debt and debt definition

A supplied dated observable borrowing yield can take precedence. The current acquisition layer does not fetch proprietary bond yields; it uses the accounting proxy where supported:

Interest Expense / average(current short+long borrowing debt, prior short+long borrowing debt).

The periods must match and the interest amount must be positive for a positive-debt company. A provider zero is not automatically treated as a free borrowing rate. Missing/implausible accounting data remains Unknown. Interest may include lease-related charges while the borrowing denominator excludes separately identified leases; this limitation is visible. Total liabilities are never used as the denominator.

Book borrowing debt is shortTermDebt + longTermDebt. When total debt and total leases are supplied, their reconciliation is checked. No assumption is made that ambiguous totalDebt, debt plus liabilities, or only long-term debt is equivalent. Book value is explicitly a proxy for market debt value.

## 12. WACC

WACC = E/(E+D+P) × Re + D/(E+D+P) × Rd × (1−T) + P/(E+D+P) × Rp.

E is market capitalization, not book equity. D is the disclosed book borrowing-debt proxy. A zero-debt company does not require a debt cost or debt tax shield. Positive debt requires usable debt cost and normalized tax. Positive preferred capital requires a separately supported preferred cost; acquisition cannot currently provide that cost, so the model does not guess. Missing preferred observations produce an explicitly disclosed common-equity/debt-only proxy rather than a claim that preferred capital is proven absent. WACC weighting and claim matching follow standard valuation theory; these data proxies do not. [CFA model framework](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/free-cash-flow-valuation).

## 13. Enterprise value

The acquisition layer reuses Yahoo info.enterpriseValue as a documented provider market-EV proxy. It does not automatically subtract all cash or investments again. The bridge shows market cap, book borrowing debt, cash, short-term investments, preferred book amount, NCI, provider EV and the unclassified residual EV − market cap − borrowing debt.

That residual is NOT excess cash. Provider treatment of leases, cash, investments, preferred/NCI or other non-operating assets is not fully disclosed. This is especially important for cash-rich businesses and limits FCFF interpretation confidence. If the EV observation is absent/nonpositive or currencies are incompatible, FCFF reverse DCF remains unavailable. FCFE does not require EV.

## 14. Terminal value and terminal growth

Terminal value at year five = year-five cash flow × (1 + terminal growth) / (matching discount rate − terminal growth). Terminal growth must be strictly below the relevant discount rate. Invalid cells are rejected rather than clipped.

The packaged base terminal growth is 2.0%, anchored to the June 17, 2026 FOMC longer-run PCE inflation projection. The platform convention assumes no real perpetual business expansion, so this nominal anchor differs from a nominal-GDP-growth forecast. It is not extrapolated company growth and not a universal truth. It is configurable, versioned, sourced and expires after 365 days. Sensitivity varies the anchor. [Federal Reserve, June 2026 projections](https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260617.htm).

## 15. Explicit horizon and reverse solver

Five years is a platform comparability convention. Each explicit cash flow equals starting cash flow × (1 + implied growth)^year. Discounted explicit cash flows plus terminal value are matched to provider EV for FCFF or market cap for FCFE.

A deterministic bisection solver searches the configured growth bracket [−95%, +300%], with at most 160 iterations and value residual tolerance max(1e−8 currency units, target × 1e−10). The bracket is a numerical guard, not an economic forecast band. The positive-starting-cash-flow model is monotonic in growth under valid discount/terminal assumptions. Missing values, nonpositive starting cash flows/targets, invalid rates, no solution inside bounds and convergence failures have separate statuses. No endpoint is forced into a reported solution. Outputs retain target, base, discount/terminal rates, horizon, year-five cash flow, residual, iterations and confidence.

## 16. FCFE reconciliation and sensitivity

FCFE is secondary and never averaged with FCFF. A >=10 pp implied-growth difference produces FCFF / FCFE Reconciliation Required. This is a versioned platform review convention, not an absolute risk score; smaller differences only mean within the configured comparison band, not proven model agreement.

FCFF sensitivity uses WACC offsets −1.0, −0.5, 0, +0.5, +1.0 pp and terminal offsets −0.5, 0, +0.5 pp. FCFE has its own cost-of-equity matrix. Cells contain implied five-year growth, with an identifiable base and explicit invalid status. Min/max use valid displayed cells, not a statistical confidence interval. The sensitivity driver compares one-variable implied-growth ranges at the other base assumption; it is specific to the chosen display envelope.

## 17. Historical context and expectation gaps

Historical P/E reuses the legacy nearest-fiscal-date-price / annual diluted-EPS data. At least three positive observations among up to five are required. The UI identifies the actual count and calls this an annual proxy, not a five-year daily trailing-P/E median. EPS release timing, split adjustment and a quote selected within ten days of fiscal end limit point-in-time comparability. Premium = current trailing P/E / median proxy − 1; it is never an overvaluation percentage.

Reported FCF yield = latest annual reported FCF / current market cap. Price is Yahoo info.currentPrice; the original top cards may retain a different closing-price definition. Sources are not silently interchanged.

CAGRs use the longest recent contiguous positive available annual run, at least three observations, anchored at the current period. Unknown/nonpositive values stop the run; no missing middle year is skipped. The exact used years are displayed. Historical FCFF/FCFE can have shorter coverage because they need prior NWC and tax history. Differences in rolling normalization confidence remain proxy limitations.

Expectation gaps are implied FCFF growth minus the observed CAGR or latest Moat 2 revenue/OI growth. They compare distinct cash-flow and period concepts and carry exact pp differences, not danger thresholds. No Low/Demanding/Very Demanding labels are used.

## 18. Fundamentals, risk wording and upstream evidence

Legacy ROIC, margins and growth are read from the existing company producer. Moat 1 results are read from an existing diagnostics/scoring cache when available. Moat 2's unchanged interpretation producer is reused with already-loaded raw statements if no request-local result exists; no new formulas or duplicate provider acquisition are added to it.

Narratives are deterministic: conditional implied growth, largest numerical comparison gap, displayed sensitivity driver, model reconciliation and input-review limitations. They do not infer stock returns, cash-flow causation, investment quality or management execution. High CapEx is not called productive or poor. No premium alone causes a sell recommendation. Missing upstream narrative evidence is not clean evidence.

## 19. Configuration, caching and operation

Install `python3 -m pip install -r requirements.txt`, add your own local provider .env and run `python3 app.py`. Visit /research?ticker=AAPL&tab=valuation, or substitute another ticker. No new top-level tab is created.

Edit data/valuation_assumptions.json to maintain dated external references, or set MOAT3_ASSUMPTIONS_FILE to another local versioned JSON file. Update source, observation date, method and version along with a value. There are no hidden WACC or terminal-growth constants in the mathematics. Expired references become Unknown. Changing assumptions does not rewrite legacy DCF defaults.

The existing request reuse, raw FMP disk caches, shared risk-free service cache and 300-second page cache are retained. Overview does not invoke Moat 3. Errors in the new service leave traditional valuation available. No live bond-yield, proprietary ERP, peer-beta or preferred-yield feeds are claimed.

## 20. Limitations and validation

Results are conditional on a constant-growth model, positive starting cash flow, compatible annual source data and external assumptions. Accounting proxies do not supply institutional certainty. Source zeros may lack separate disclosure; zero accounting interest on positive debt is conservatively rejected, but no general provider-disclosure classifier is invented. Preferred/NCI, leases, non-operating assets and mixed market/accounting dates can limit comparability.

The full regression suite preserves original golden data and checks all seven legacy report/context and Moat 1/2 fingerprints. New tests cover pure formulas, provenance, normalization, source/cache transport, solver recovery, sensitivity, missing-data isolation and seven route renders. Synthetic transport cases are explicitly distinct from current company observations. See MOAT3_IMPLEMENTATION_REPORT.md for exact results and available-data limitations.
