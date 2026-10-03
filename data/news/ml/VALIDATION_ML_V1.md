# ML V1 delivery validation

- Built from the supplied STOCK_SCREENER_NEWS_INTELLIGENCE_BACKEND_V1_2_1.zip; filename notwithstanding, its frozen source includes V1.3.0.
- Every extracted original file remains byte-for-byte unchanged. No changes to Event/Exposure Engine, schema, workbook, historical replay or source market-return CSV.
- Full News + ML suite: 226 tests passed; 24 new ML tests passed. No failed/skipped tests.
- Real historical prices downloaded through yfinance auto_adjust=False / Close for seven tickers and QQQ. No synthetic prices used for model results.
- 23 eligible rows, 14 positive / 9 negative at 2%; zero missing numeric context cells in this run.
- Nine feature concepts expand to 29 encoded columns in descriptive B2: sparse categorical coefficients are unstable.
- Minimum ten mature training rows; same-date/same-event grouping and t3 label-maturity check produce 11 OOS predictions (5 positive / 6 negative at 2%).
- Primary 2% B2 does NOT improve probabilistic losses over B1. A higher AUC is insufficient to declare success.
- 3%: B2 improves loss/Brier over B1 but is mixed versus B0. 4%: B2 improves both losses over B0 and B1 in this tiny sample. No primary-threshold change or tuning was performed.
- Offline repeat verified with yfinance.download disabled: all five result CSVs agree numerically within 1e-12. Machine-level floating-point last digits may vary.
- All source data/feature provenance and dependency versions are in the run manifest; download cookies and transient provider metadata are excluded from the delivered ZIP.
- The supplied labels describe original event-study windows; date-only/intraday cases are not a news-arrival trading backtest. Eligibility is preserved from upstream, not reclassified by ML.

## Added source files
src/news/ml/__init__.py
src/news/ml/features.py
src/news/ml/model.py
src/news/ml/validation.py
src/news/ml/reporting.py
src/news/ml/requirements.txt
src/news/material_reaction_model.py

## Added tests
 tests/news/test_material_reaction_ml.py

## Results
See material_reaction_metrics_v1.csv, material_reaction_predictions_v1.csv,
material_reaction_sensitivity_predictions_v1.csv, material_reaction_coefficients_v1.csv,
material_reaction_dataset_v1.csv, material_reaction_report_v1.txt and README_ML_V1.md.

## Run
python3 -m pip install -r src/news/ml/requirements.txt
python3 -m src.news.material_reaction_model
python3 -m unittest discover -s tests/news -t tests -v
