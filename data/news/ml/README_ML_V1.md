# Material Market Reaction Model V1

This is an experimental portfolio model built on a small historical event sample.
It should not be interpreted as a production forecasting system.

## Objective and target
Given a previously eligible event-company pair, estimate a material three-session QQQ-relative move.
MR = cumulative stock Close return minus cumulative QQQ Close return over the source CSV window.
y = 1 if abs(MR) > 0.02, otherwise 0. The 3% and 4% evaluations are sensitivity checks,
using identical features, folds, C=1 and logistic settings; no tuning or model search.
This is descriptive QQQ-relative return, NOT causal abnormal return, relevance, direction or a recommendation.
Relevance != Impact != Rating Change. ML never changes the frozen relevance engine or exposure relationships.

## Inputs and features
Input eligibility is taken from ml_eligible, not re-estimated by ML. Rejected/boundary eligible rows raise an error.
Sample size is dynamic; H31-H60 can be appended to the same schema or supplied with --input.
B1 uses six numeric concepts: pre20_vol, pre60_vol, pre5_stock_return, pre5_qqq_relative, pre20_stock_return, pre20_qqq_relative.
B2 adds event_type, event_subtype, relationship_type (nine feature concepts total).
One-hot encoding creates more than nine numerical columns; the descriptive B2 fit has 37 columns.
No ticker, case ID, future outcome, price target, research rating or fundamental feature enters X.
The source CSV is immutable. Outcomes in the exported dataset are explicitly prefixed label_, apart from target.

Prices: yfinance download(auto_adjust=False, back_adjust=False, repair=False), Close, regular daily bars.
Each feature calculation slices dates strictly less than t0_session. Momentum uses n+1 closes for n returns;
volatility uses n daily returns, sample standard deviation (ddof=1), annualized by sqrt(252).
QQQ sessions align stock and benchmark. Missing prices are NOT forward-filled. Missing windows remain NaN.
Entire download failure stops the run; it is never silently replaced with all-missing features.
Numeric missing values use TRAIN-FOLD medians; entirely missing training columns use zero via keep_empty_features.
StandardScaler is fitted only on training data. Categorical missing values become Unknown;
unseen categories are ignored by the train-fitted encoder. The full-sample model is for coefficient inspection only.

## Models and validation
B0 = training-only positive frequency. B1/B2 = L2 LogisticRegression, C=1, liblinear, max_iter=3000, random_state=0.
Sort by effective_event_date/case_id/ticker. Same-date predictions are simultaneous and same-case rows grouped.
Require >= 10 earlier training rows AND their t3_session < next prediction group's earliest t0_session.
This prevents unresolved prior three-day labels and same-day outcomes entering training. Consequently there may
be fewer predictions than a naive N-minus-10 rolling split. Grouped split records include train_case_ids and label cutoffs.
Single-class training folds use the B0 constant as a clearly flagged fallback, not a fictitious fitted logistic model.
Too few rows produce header-only predictions/coefficients as applicable and N/A metrics, not a crash.
Metrics are pooled out-of-sample, not averages of meaningless single-observation AUCs.
Classification uses fixed p>=0.5. AUC and balanced accuracy are N/A if only one outcome class is observed.
Log loss clips only for numerical evaluation. No thresholds or hyperparameters are chosen on held-out outcomes.

## Results
| Threshold | Model | OOS n | Positive | Negative | Accuracy | Balanced accuracy | Log loss | Brier | AUC |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2% | B0 | 41 | 23 | 18 | 0.5610 | 0.5000 | 0.7356 | 0.2675 | 0.4251 |
| 2% | B1 | 41 | 23 | 18 | 0.5366 | 0.5145 | 0.7456 | 0.2690 | 0.5580 |
| 2% | B2 | 41 | 23 | 18 | 0.5610 | 0.5302 | 0.7725 | 0.2711 | 0.5362 |
| 3% | B0 | 41 | 12 | 29 | 0.5854 | 0.4382 | 0.6488 | 0.2281 | 0.4152 |
| 3% | B1 | 41 | 12 | 29 | 0.7561 | 0.7299 | 0.5329 | 0.1762 | 0.7385 |
| 3% | B2 | 41 | 12 | 29 | 0.7805 | 0.7471 | 0.5166 | 0.1714 | 0.7529 |
| 4% | B0 | 41 | 9 | 32 | 0.7805 | 0.5000 | 0.5513 | 0.1809 | 0.2830 |
| 4% | B1 | 41 | 9 | 32 | 0.8293 | 0.7309 | 0.5030 | 0.1432 | 0.7778 |
| 4% | B2 | 41 | 9 | 32 | 0.8049 | 0.6753 | 0.5453 | 0.1573 | 0.7431 |

B2 vs B0: higher loss on both measures; delta log loss=+0.0368, delta Brier=+0.0036. B2 vs B1: higher loss on both measures; delta log loss=+0.0268, delta Brier=+0.0021. Tiny-sample comparison only; not proof of predictive signal.

## Coefficients
The coefficient CSV is from B2 fit on all eligible observations after evaluation.
Numeric coefficients are per training-standardized unit; categorical coefficients are encoded indicator associations.
Coefficients are descriptive associations in a tiny sample, NOT causal effects. Rare categories may have only one or
two observations. Full-sample coefficients and apparent fit are not out-of-sample evidence.

## Limitations
- Only 51 eligible observations; selected historical cases, correlated event windows, and concentrated company exposure.
- The original CSV eligibility and event-time snapshots are accepted as upstream inputs, not independently revalidated here.
- Preserve the original event-study price windows. Intraday/date-only cases can include movement before article availability;
  therefore this is pseudo-out-of-sample classification of supplied event-window outcomes, NOT a tradable news-arrival backtest.
- Close is not Adj Close and is not dividend-total-return data. Yahoo may split-adjust or revise historical prices even with
  auto_adjust=False; cached retrieval timestamps do not prove historical data vintage. No synthetic data is used for reported metrics.
- Training-fold maturity protection does not make nearby events independent or establish causality.
- Benchmark subtraction does not beta-adjust stocks. QQQ contains MAG7 exposure.
- Encoded sparse categories can overfit; no calibrated probability or production-readiness claim is justified.
- The output is a portfolio experiment; no ML/live UI, deployment, rating integration or exposure override is added.

## Reproduce
From the project root:

    python3 -m pip install -r src/news/ml/requirements.txt
    python3 -m src.news.material_reaction_model
    python3 -m unittest discover -s tests/news -t tests -p 'test_material_reaction_ml.py' -v

The included Close CSV cache is reused without a network request. --refresh-prices explicitly downloads a new vintage.
The manifest records input SHA-256, price sources/hashes, dependency versions, class counts and preprocessing choices.
To append new cases, retain the input schema/eligibility discipline, or use --input PATH; no row-count hardcoding is used.
Next steps: add independently selected cases, re-run the same frozen baseline comparison, inspect stability before complexity.

Documentation: [yfinance download](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html),
[scikit-learn LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html).
