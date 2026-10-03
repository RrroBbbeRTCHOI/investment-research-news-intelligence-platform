# Moat 1 V1 — Regression and delivery report

Validated 2026-09-09 using Python 3.13 and the existing offline Replay framework.

## Acceptance result

**66 tests passed in 36.866 seconds.** This includes all 39 existing test methods, adjusted only for the approved EQ service/data/UI boundary, and 27 new Moat 1 scenario/integration tests.

- All 42 ticker/tab combinations passed: AAPL, MSFT, GOOGL, NVDA, AMZN, META, TSLA across all six existing tabs.
- All 14 existing analysis report types per ticker remain exactly equal to the frozen golden reports (98 report comparisons).
- Research Score, Fundamental Score, recommendation/conviction, quality score/classification, valuation fields and Neutral naming are unchanged.
- Golden files, fixture provider payloads and fixture manifest hashes are unchanged. No golden snapshots were regenerated.
- Legacy company context comparisons retain the previously approved rating-display amendments and exclude only the separately checked EQ diagnostic payload. No other fields are excluded.
- Rendering the original context through every non-EQ tab still matches its original HTML hash. Template content before and after the EQ branch is hash-pinned and unchanged.
- All Python source files compile.
- The in-app browser was used to visually inspect a locally served, frozen-data Flask-rendered Earnings Quality page, including interpretation and growth sections. This is a UI check, not live-market or production SEC coverage validation.

## New scenarios

Six-way growth and provenance; missing/duplicate/wrong periods; unknown year; wrong ticker; currency/unit mismatch; nonadjacent periods; zero/negative denominator; turnaround; positive/negative assets; OCF/NI and accrual cases; complete and partial WC bridges; receivables-only insufficiency; CapEx sign and reconciliation mismatch; ASCII/Unicode/parenthesis signs; unknown SEC evidence; no events and zero events; partial extraction; positive/negative events; unknown categories; exact/conflicting duplicate tables; wrong year/accession; short SEC duration; scoped subtotal reconciliation; deterministic rule schema; growth-gap boundaries; four rule families; Supported requiring scoped evidence and matching source values; FCF/WC caution; independent EQ with valuation/rating entry points patched to fail; seven-ticker golden quality/non-core reports; scoring computed once for rating and EQ; FMP failure returns unavailable diagnostics without destroying the legacy score.

## Expected differences, not baseline changes

The EQ service is now independent and returns an expanded result. The UI separately assembles its original rating report. The EQ tab gains diagnostic content and therefore has an intentionally different HTML result. Existing service-mocking tests now target score exposure rather than valuation. New historical/evidence retrieval means first EQ navigation can have provider calls; warm-repeat reuse is still asserted.

No unexplained differences in legacy financial/rating outputs were observed.

## Provider-boundary measurements

Counts below use AAPL offline replay. Each cold scenario starts with a fresh Replay and empty temporary FMP cache. These count provider-boundary accesses, not production HTTP latency or provider-internal network requests.

| Scenario | Calls |
|---|---:|
| Independent EQ analysis, cold | 10 |
| Existing valuation/rating company context, cold | 20 |
| EQ company context retaining rating, cold | 22 |
| Overview to first EQ route, FMP history not yet loaded | 8 |
| Repeat EQ route | 0 |

Independent EQ avoids valuation, peer/momentum/volatility history and DCF. The retained full UI adds two FMP history calls compared with the previous score-only company context. First cross-tab evidence inspection also retrieves current SEC and asset provenance. No claim is made that every full page is cheaper. The full seven-company screener remains an independent page cost.

Detailed measured counts:

```json
{
  "standalone_eq": {
    "total": 10,
    "by_kind": {
      "sec_cik": 1,
      "sec_submissions": 1,
      "sec_html": 1,
      "sec_facts": 1,
      "cashflow": 1,
      "financials": 1,
      "balance_sheet": 1,
      "fmp": 2,
      "info": 1
    }
  },
  "valuation_page_context": {
    "total": 20,
    "by_kind": {
      "info": 5,
      "history": 8,
      "financials": 1,
      "balance_sheet": 1,
      "cashflow": 1,
      "sec_cik": 1,
      "sec_submissions": 1,
      "sec_html": 1,
      "sec_facts": 1
    }
  },
  "eq_page_context": {
    "total": 22,
    "by_kind": {
      "sec_cik": 1,
      "sec_submissions": 1,
      "sec_html": 1,
      "sec_facts": 1,
      "cashflow": 1,
      "financials": 1,
      "balance_sheet": 1,
      "fmp": 2,
      "info": 5,
      "history": 8
    }
  },
  "overview_to_first_eq": {
    "total": 8,
    "by_kind": {
      "fmp": 2,
      "balance_sheet": 1,
      "info": 1,
      "sec_cik": 1,
      "sec_submissions": 1,
      "sec_html": 1,
      "sec_facts": 1
    }
  },
  "repeat_eq": {
    "total": 0
  }
}
```

## Remaining Unknown areas

The frozen seven-ticker replay has six normal growth observations per ticker, but no strict validated SEC table coverage and no usable aligned asset provenance for the new combined cash interpretation. Numerical OCF/NI observations are still exposed. Synthetic scenario tests separately exercise valid accrual inputs, positive/negative material evidence, reconciliation and Supported/Mixed/Concern/Unknown outputs. These fixtures are not live financial recommendations.

See MOAT1_KNOWN_LIMITATIONS.md for extraction coverage, frozen model weaknesses, unsupported recurring/tax/structural attribution and separately approvable methodology changes.

## Exact commands

From this copied project:

```bash
cd "/Users/choisiuhang/Documents/ChatGPT/stock screener/review/Stock Screener"
PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py
python3 -m flask --app app run --host 127.0.0.1 --port 5000
```

After ZIP extraction, run those same test/server commands from its `Stock Screener` directory. Runtime dependencies are in tests/requirements.txt; normal provider operation needs the existing FINANCIAL_API_KEY and SEC_USER_AGENT configuration. Offline tests require no live credentials.

## Files changed

Added:

- `MOAT1_EARNINGS_QUALITY.md`
- `MOAT1_KNOWN_LIMITATIONS.md`
- `MOAT1_REGRESSION_REPORT.md`
- `src/analysis/earnings_quality_diagnostics.py`
- `src/analysis/earnings_quality_evidence.py`
- `src/data/earnings_quality_inputs.py`
- `tests/test_moat1.py`

Modified:

- `src/analysis/quality.py`
- `src/services/earnings_quality_service.py`
- `src/services/rating_service.py`
- `src/ui/research_context.py`
- `templates/research.html`
- `tests/support.py`
- `tests/test_refactor.py`
- `tests/test_regression.py`

No original project files were modified. The archive contains the complete copied project, including unchanged data, golden fixtures, legacy modules and earlier reports. No credentials were added.
