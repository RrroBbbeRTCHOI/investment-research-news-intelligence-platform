# Phase 1: frozen-input behavior baseline

This directory contains the preserved Phase 1 fixtures and golden baseline.
The current production copy has completed Phases 2–7; see the four reports in
the project root. Golden fixture files remain unchanged. Test setup now also
clears the service cache and observes dependencies in their new locations.
`test_refactor.py` adds cache/reuse/isolation checks without replacing baseline assertions.

## Run

From the project directory, run `python3 tests/run.py`. The runner resolves paths
relative to itself, so it also works when launched by absolute path elsewhere.
It uses standard-library unittest, not pytest. Do not use root-level discovery:
the existing root `test_ui_data.py` executes live research at import time.

The baseline uses Python 3.13.0; the recorded version inventory is in
`fixtures/manifest.json`.
`requirements.txt` pins the direct dependencies used in that runtime; it is not
a complete transitive lockfile. If setting up a separate environment, install
those dependencies there with `python -m pip install -r tests/requirements.txt`.
Installation may need network access; the tests themselves never do.

## What is frozen (and what it means)

- `fixtures/providers.json`: deterministic synthetic Yahoo-style statements,
  company info and five years of daily prices for seven supported companies,
  their configured peers, SPY and QQQ. SEC ticker metadata, submissions, Facts
  and filing HTML are also synthetic. **These are not actual company financials
  and were not downloaded from Yahoo or SEC.**
- The FMP section copies the `data` arrays of all 15 supplied historical cache
  files. Provenance and source hashes are in `fixtures/provenance.json`.
  These supplied cache observations have not been independently verified.
  FMP and synthetic Yahoo financials intentionally remain separate providers.
- `fixtures/baseline/{ticker}.json`: golden results produced by the unchanged
  production code, not manually fabricated final recommendations. Each contains
  six real Flask route results (full rendered context and HTML SHA-256), plus
  14 complete backend outputs: recommendation, research/quality summaries,
  valuation, DCF summary/scenarios, expectations, FCFF, fundamentals,
  materiality, non-core earnings, SEC summary/classification and financial trends.
- `fixtures/baseline/failures.json`: current behavior under injected failures.
  An exception is preserved when that is what production currently does.
- `fixtures/manifest.json`: Python/package versions, original source hashes,
  and fixture/snapshot checksums. Source hashes are provenance, not a rule that
  all production Python must stay unchanged during future approved refactors.
  The visual-source test does explicitly protect the unchanged templates/design.

Synthetic inputs provide repeatable regression protection for supported ticker
routing and real calculations. They do not certify live API compatibility,
financial correctness, actual market valuations, or real ticker latency.
The same synthetic filing is used for 10-K/10-Q discovery tests; it does not
model each company's actual accounting disclosures.

## Isolation

Replay replaces only external provider boundaries (`yfinance.Ticker` and HTTP),
suppresses dotenv loading, uses dummy credentials, and redirects FMP cache I/O
to a disposable temporary directory. It never reads `.env` or sends messages.
The test clock is controlled; file mtimes are synchronized to that clock after
the real cache writer runs. In-memory application caches are reset between cases.

Unknown provider properties, symbols, periods or URLs fail closed. Requests,
curl_cffi Session calls, socket connections and DNS resolution are blocked. The guard raises
a BaseException subclass so production's broad `except Exception` cannot turn
an accidental network attempt into a silently passing N/A result.

All domain functions, scoring, DCF, SEC parsing, adapters, routes and templates
remain real. No final context/recommendation is stubbed in the golden tests.
Expected output files are read-only during test runs; missing files fail.

## Preserved quirks

- Screener ratings/research scores remain N/A with raw scores None.
- Financials, Historical Trends and SEC Filing retain empty rating fields.
- Overview, Valuation and Earnings Quality run the existing full rating graph.
- Neutral remains Neutral, never renamed Hold.
- SEC tab and financial trend chart placeholders remain as supplied.
- Existing failure propagation/fallback behavior is characterized, not improved.
- The UI/company and valuation info prices are deliberately different fixture
  values, protecting the existing distinction between closing and info prices.
- Existing in-memory and disk TTL boundaries differ; tests preserve both.

## Review and recording policy

`build_fixtures.py` creates initial provider fixtures without network and refuses
to overwrite an existing provider file. `record_baseline.py
--record-initial-baseline` explicitly executes the original pipeline and refuses
to overwrite an existing baseline directory. These are initialization tools,
not commands to run after making a refactor. Ordinary tests never call either.

Do not regenerate snapshots to make a failing refactor pass. Compare the first
differing JSON path and fix the refactor. Changing approved behavior requires a
separate review, preservation of the old baseline and deliberate fixture review.
Snapshot hashes protect accidental edits, not malicious replacement of both
snapshots and manifest. No golden output is evidence of independent correctness.

## Coverage and limits

Coverage includes 42 ticker/tab combinations, full report snapshots, frontend
HTML hashes, route/search/navigation behavior, key recommendation boundaries,
known N/A states, warm/expired caches, FMP force refresh and corrupt-cache
fallbacks, provider failures, SEC extraction, and tab dependency boundaries.

Exact output comparison includes numeric values (no rounding/tolerance added),
key/type preservation, explicit serialization of nonfinite values and pandas
objects. Use the recorded runtime to investigate platform/library differences.

This suite does not launch a browser or execute Chart.js; HTML and chart payload
regressions are covered, actual chart rendering/theme interactions are not.
It does not test multiprocess cache behavior, actual network timeouts/rate limits,
live service contracts, or every financial edge case. Future phases must add
focused fixtures for any newly touched boundary; this is a baseline, not proof
that every original feature is correct.
