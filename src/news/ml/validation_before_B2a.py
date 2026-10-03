"""Expanding chronological evaluation with event grouping and mature labels."""
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, log_loss, brier_score_loss, roc_auc_score
from .features import THRESHOLDS, target_column
from .model import fit_model, predict

METRICS = ['accuracy', 'balanced_accuracy', 'log_loss', 'brier_score', 'roc_auc']
PREDICTION_COLUMNS = ['case_id', 'ticker', 'effective_event_date', 'event_type', 'event_subtype',
                      'relationship_type', 'threshold', 'target', 'fold', 'n_train',
                      'train_case_ids', 'train_label_end_max', 'prediction_t0',
                      'p_b0', 'p_b1', 'p_b2', 'pred_b0', 'pred_b1', 'pred_b2', 'fit_status']


def expanding_splits(data, min_train=10):
    if min_train < 1:
        raise ValueError('min_train must be >= 1')
    # All observations of an event share a prediction block (its earliest date).
    event_start = data.groupby('case_id').effective_event_date.transform('min')
    label_end = data.groupby('case_id').t3_session.transform('max')
    event_anchor = data.groupby('case_id').t0_session.transform('max')
    for when in sorted(event_start.unique()):
        test = data.index[event_start == when]
        cutoff = data.loc[test, 't0_session'].min()
        train = data.index[(event_start < when) & (label_end < cutoff) & (event_anchor < cutoff)]
        if len(train) >= min_train:
            yield train, test


def score_predictions(predictions, threshold, level):
    p = predictions[f'p_{level.lower()}'].to_numpy(dtype=float)
    y = predictions.target.to_numpy(dtype=int)
    result = dict(threshold=threshold, model=level, n_predictions=len(y),
                  positive_count=int(y.sum()), negative_count=int(len(y)-y.sum()))
    result.update({m: np.nan for m in METRICS})
    if len(y):
        binary = p >= 0.5
        two_classes = len(np.unique(y)) == 2
        result.update(accuracy=accuracy_score(y, binary),
                      balanced_accuracy=balanced_accuracy_score(y, binary) if two_classes else np.nan,
                      log_loss=log_loss(y, np.clip(p, 1e-15, 1 - 1e-15), labels=[0, 1]),
                      brier_score=brier_score_loss(y, p),
                      roc_auc=roc_auc_score(y, p) if two_classes else np.nan)
    return result


def evaluate(data, min_train=10):
    records, metric_rows = [], []
    for threshold in THRESHOLDS:
        label = target_column(threshold)
        threshold_records = []
        for fold, (train_idx, test_idx) in enumerate(expanding_splits(data, min_train), 1):
            train, test = data.loc[train_idx], data.loc[test_idx]
            y = train[label].to_numpy(dtype=int)
            base = float(y.mean())
            b1, b2 = fit_model(train, y, 'B1'), fit_model(train, y, 'B2')
            p1, p2 = predict(b1, test, 'B1', base), predict(b2, test, 'B2', base)
            for position, (_, row) in enumerate(test.iterrows()):
                record = {c: row[c] for c in PREDICTION_COLUMNS[:6]}
                record.update(threshold=threshold, target=int(row[label]), fold=fold,
                              n_train=len(train), train_case_ids='|'.join(sorted(set(train.case_id))),
                              train_label_end_max=train.t3_session.max(), prediction_t0=test.t0_session.min(),
                              p_b0=base, p_b1=float(p1[position]), p_b2=float(p2[position]),
                              fit_status='logistic' if b1 is not None else 'single_class_base_rate_fallback')
                for level in ('b0', 'b1', 'b2'):
                    record[f'pred_{level}'] = int(record[f'p_{level}'] >= 0.5)
                threshold_records.append(record)
        frame = pd.DataFrame(threshold_records, columns=PREDICTION_COLUMNS)
        metric_rows.extend(score_predictions(frame, threshold, level) for level in ('B0', 'B1', 'B2'))
        records.extend(threshold_records)
    return pd.DataFrame(records, columns=PREDICTION_COLUMNS), pd.DataFrame(metric_rows)
