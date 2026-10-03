"""Research reporting: probabilistic baselines, not stock recommendations."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .features import THRESHOLDS, target_column, NUMERIC_FEATURES, CATEGORICAL_FEATURES
from .validation import METRICS


def interpretation(metrics, threshold=0.02):
    rows = metrics.loc[np.isclose(metrics.threshold, threshold)].set_index('model')
    if rows.empty or rows.n_predictions.max() == 0:
        return 'Insufficient mature training observations: no out-of-sample evaluation.'
    parts = []
    for other in ('B0', 'B1'):
        ll = rows.loc['B2', 'log_loss'] - rows.loc[other, 'log_loss']
        bs = rows.loc['B2', 'brier_score'] - rows.loc[other, 'brier_score']
        verdict = 'lower loss on both measures' if ll < 0 and bs < 0 else (
            'higher loss on both measures' if ll > 0 and bs > 0 else 'mixed or equal loss results')
        parts.append(f'B2 vs {other}: {verdict}; delta log loss={ll:+.4f}, delta Brier={bs:+.4f}.')
    return ' '.join(parts) + ' Tiny-sample comparison only; not proof of predictive signal.'


def number(value):
    return 'N/A' if pd.isna(value) else f'{value:.4f}'


def terminal_report(data, metrics):
    lines = ['=' * 64, 'MATERIAL MARKET REACTION MODEL V1', '=' * 64,
             'Target: |3D stock return minus 3D QQQ return| > 2%',
             f'ML-eligible rows: {len(data)}', f'Positive: {int(data.target.sum())}',
             f'Negative: {int(len(data)-data.target.sum())}',
             'Validation: chronological expanding window; grouped dates/events;',
             'training labels must mature strictly before prediction t0.', '',
             'OUT-OF-SAMPLE METRICS (2%)']
    rows = metrics.loc[np.isclose(metrics.threshold, .02)].set_index('model')
    lines.append(f"{'Metric':24}{'B0':>12}{'B1':>12}{'B2':>12}")
    for key in ['n_predictions', *METRICS]:
        values = [str(int(rows.loc[m,key])) if key == 'n_predictions' else number(rows.loc[m,key]) for m in ('B0','B1','B2')]
        lines.append(f'{key:24}' + ''.join(f'{v:>12}' for v in values))
    lines += ['', 'THRESHOLD SENSITIVITY']
    for t in THRESHOLDS:
        positives = int(data[target_column(t)].sum())
        lines.append(f'{t:.0%}: total={len(data)}, positive={positives}, negative={len(data)-positives}')
        for r in metrics.loc[np.isclose(metrics.threshold,t)].itertuples():
            lines.append(f'  {r.model}: OOS={r.n_predictions}, log loss={number(r.log_loss)}, Brier={number(r.brier_score)}, AUC={number(r.roc_auc)}')
        lines.append(interpretation(metrics,t))
    lines += ['', 'INTERPRETATION', interpretation(metrics),
              'Experimental portfolio prototype; very small, selected historical sample.',
              'Not a production forecast, causal impact, direction, rating or recommendation.', '=' * 64]
    return '\n'.join(lines)


def write_outputs(output, data, predictions, metrics, coef, manifest):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data.to_csv(output/'material_reaction_dataset_v1.csv', index=False)
    # Primary file is only the requested 2% task; sensitivity predictions separate.
    predictions.loc[np.isclose(predictions.threshold,.02)].to_csv(output/'material_reaction_predictions_v1.csv', index=False)
    predictions.to_csv(output/'material_reaction_sensitivity_predictions_v1.csv', index=False)
    metrics.to_csv(output/'material_reaction_metrics_v1.csv', index=False)
    coef.to_csv(output/'material_reaction_coefficients_v1.csv', index=False)
    (output/'material_reaction_run_manifest_v1.json').write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    text = terminal_report(data, metrics)
    (output/'material_reaction_report_v1.txt').write_text(text+'\n')
    rows = ['| Threshold | Model | OOS n | Positive | Negative | Accuracy | Balanced accuracy | Log loss | Brier | AUC |',
            '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in metrics.itertuples():
        rows.append(f'| {r.threshold:.0%} | {r.model} | {r.n_predictions} | {r.positive_count} | {r.negative_count} | ' + ' | '.join(number(getattr(r,k)) for k in METRICS) + ' |')
    document = f'''# Material Market Reaction Model V1

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
B1 uses six numeric concepts: {', '.join(NUMERIC_FEATURES)}.
B2 adds {', '.join(CATEGORICAL_FEATURES)} (nine feature concepts total).
One-hot encoding creates more than nine numerical columns; the descriptive B2 fit has {len(coef)} columns.
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
Require >= {manifest['min_train']} earlier training rows AND their t3_session < next prediction group's earliest t0_session.
This prevents unresolved prior three-day labels and same-day outcomes entering training. Consequently there may
be fewer predictions than a naive N-minus-10 rolling split. Grouped split records include train_case_ids and label cutoffs.
Single-class training folds use the B0 constant as a clearly flagged fallback, not a fictitious fitted logistic model.
Too few rows produce header-only predictions/coefficients as applicable and N/A metrics, not a crash.
Metrics are pooled out-of-sample, not averages of meaningless single-observation AUCs.
Classification uses fixed p>=0.5. AUC and balanced accuracy are N/A if only one outcome class is observed.
Log loss clips only for numerical evaluation. No thresholds or hyperparameters are chosen on held-out outcomes.

## Results
{chr(10).join(rows)}

{interpretation(metrics)}

## Coefficients
The coefficient CSV is from B2 fit on all eligible observations after evaluation.
Numeric coefficients are per training-standardized unit; categorical coefficients are encoded indicator associations.
Coefficients are descriptive associations in a tiny sample, NOT causal effects. Rare categories may have only one or
two observations. Full-sample coefficients and apparent fit are not out-of-sample evidence.

## Limitations
- Only {len(data)} eligible observations; selected historical cases, correlated event windows, and concentrated company exposure.
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
'''
    (output/'README_ML_V1.md').write_text(document)
    return text
