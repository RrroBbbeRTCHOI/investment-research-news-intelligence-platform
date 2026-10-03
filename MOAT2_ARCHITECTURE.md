# Moat 2 architecture

This standalone copy continues from STOCK_SCREENER_MOAT1_V2_FINAL. Original application files, required data and previous documentation remain available. This document and the three other MOAT2 documents describe the additive Financials upgrade.

## Data flow

Existing FMP annual cache/loaders -> financial_statement_bridges.normalize -> pure metrics and arithmetic bridges -> financial_statement_diagnostics.interpret -> financial_interpretation_service -> financials_service -> research_context -> Financials template include.

The three new Python modules have distinct responsibilities: validated facts and arithmetic; deterministic interpretation; existing data/cache orchestration and failure isolation. No new provider, scoring engine, SEC classifier, accrual engine, valuation dependency or ticker branch was introduced.

## Service and UI contract

build_financial_interpretation(ticker, moat1=None) returns ticker, period, income_statement, balance_sheet, cash_flow, trend_context, investigation_priorities, analyst_interpretation, evidence_references and limitations. Facts carry source field, fiscal year, report date, currency, unit, availability and evidence identity. Derived rows expose current/prior values, comparable change, growth status and evidence references. JSON contains no nonfinite numbers.

The existing Financials pipeline adds financial_interpretation; research_context passes this additive field through. The original eight Financials cards and all other tab markup remain intact. A separate Jinja include renders the new research sections using existing card classes, typography and theme. No route, CSS or JS is changed. The actual route remains /research?ticker=AAPL&tab=financials, with the other universe tickers substituted.

## Moat 1 integration and performance

The service can accept an existing Moat 1 result and can read a fresh Moat 1 result from the existing persistent service cache. It does not initiate EQ or SEC analysis merely to show Financials. It consumes current-period validated evidence and existing cash_support without mutating them. Cold Financials therefore may show no Moat 1 narrative references until an upstream result is available. This is intentional and visible in limitations; arithmetic diagnostics operate independently.

Existing request-scoped reuse memoizes the complete interpretation, including a partial dataset, for the request. Existing annual file caches avoid repeat successful statement calls. Existing whole-page caching handles repeat Financials visits. No cache TTL or storage architecture was changed. Failures return an Unknown interpretation while leaving the legacy cards usable.

## Run

From this folder: `python3 -m pip install -r tests/requirements.txt`, then `python3 app.py`. Existing live-provider configuration is required for current data; no credentials are included. The original app uses http://127.0.0.1:5000. Verify offline with `PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py`.

The source has no separate static directory: its existing inline/external assets remain in the templates. No empty asset directory is fabricated.

## V1.1 balance-coverage audit

The balance loader was already wired into the same _load_history loop as income and cash. No missing call, ticker filter, alternative provider or new cache mechanism was found. The asymmetry was the supplied cache contents plus missing FMP configuration in the inspected standalone environment. The service previously reduced specific loader failures to RuntimeError, hiding the actionable cause. V1.1 preserves the original loader and adds credential-safe failure explanations in the existing limitations output. HTTP status, missing credentials, request failures and unusable responses are distinguished without emitting API keys or request URLs.

A valid annual cache is still used without credentials by the existing adapter. A cache miss delegates to get_historical_balance_sheet, which calls _fmp_get and the existing atomic writer. Credentials, HTTP access, annual metadata and period matches remain required. No scoring, source definitions, cache TTLs, unknown safeguards, template or top-card changes were necessary.

For real-data completion, set FINANCIAL_API_KEY in your local environment or project .env (never commit/share it), restart the application so configuration is reloaded, then open the ordinary Financials tab for each company. The request populates missing balance history automatically when FMP returns a valid response. Check the existing Coverage & limitations section if a provider request fails. Existing page-cache TTL remains 300 seconds; restarting also clears old in-memory page results. An API response with absent fields or mismatched periods legitimately retains Unknown. A credential alone does not guarantee provider plan access or coverage.

## V1.2 ticker-agnostic canonical balance schema

The existing FMP -> raw annual cache -> Moat 2 normalization flow now resolves explicitly equivalent balance field aliases for all twelve canonical fields. The resolver is inside the existing financial_statement_bridges module; there is no new service/provider/cache layer. Each of the current and prior annual rows is resolved independently with the same mapping for any ticker. Tests include every universe company and an arbitrary ACME ticker. Existing scoring, cards, UI, Moat 1, provider definitions and cache TTLs are unchanged. Fresh cache misses still require locally configured FMP access; normalization does not fabricate absent source data.
