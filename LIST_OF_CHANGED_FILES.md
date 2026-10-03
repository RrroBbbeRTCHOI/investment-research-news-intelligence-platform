# V1.5 changed files

Compared byte-for-byte with the delivered `Stock-Screener-Moat1-V1.zip`.

## Modified

- `REGRESSION_REPORT.md`
- `src/analysis/earnings_quality_diagnostics.py`
- `src/analysis/earnings_quality_evidence.py`
- `src/data/earnings_quality_inputs.py`
- `src/services/earnings_quality_service.py`
- `templates/research.html`
- `tests/support.py`
- `tests/test_moat1.py`

## Added

- `LIST_OF_CHANGED_FILES.md`
- `MOAT1_FINAL_REPORT.md`
- `tests/test_moat15.py`

## Unchanged / boundaries

No files removed. All original fixture/provider/golden files, rating/valuation/quality scoring modules, routes, stock universe, cache implementation, research context adapter and non-EQ frontend code are unchanged. Only the Earnings Quality template branch has product HTML amendments. `tests/support.py` documents six explicitly unavailable balance recordings; `tests/test_moat1.py` updates one pair-specific partial-data assertion. The new tests are in `tests/test_moat15.py`.

Original user project and original uploaded ZIP were not modified. Work was performed only in the previously delivered copied project.
