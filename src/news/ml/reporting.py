"""Research reporting: probabilistic baselines, not stock recommendations."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .features import (
    THRESHOLDS,
    target_column,
)
from .validation import METRICS, MODEL_LEVELS


def number(value):
    return 'N/A' if pd.isna(value) else f'{value:.4f}'


def _pair_comparison(rows, left, right):
    ll = rows.loc[right, 'log_loss'] - rows.loc[left, 'log_loss']
    bs = rows.loc[right, 'brier_score'] - rows.loc[left, 'brier_score']

    verdict = (
        'lower loss on both measures'
        if ll < 0 and bs < 0
        else 'higher loss on both measures'
        if ll > 0 and bs > 0
        else 'mixed or equal loss results'
    )

    return (
        f'{right} vs {left}: {verdict}; '
        f'delta log loss={ll:+.4f}, '
        f'delta Brier={bs:+.4f}.'
    )


def interpretation(metrics, threshold=0.02):
    rows = metrics.loc[
        np.isclose(metrics.threshold, threshold)
    ].set_index('model')

    if rows.empty or rows.n_predictions.max() == 0:
        return (
            'Insufficient mature training observations: '
            'no out-of-sample evaluation.'
        )

    required = set(MODEL_LEVELS)
    if not required.issubset(rows.index):
        return 'Incomplete model comparison rows.'

    parts = [
        _pair_comparison(rows, 'B0', 'B1'),
        _pair_comparison(rows, 'B1', 'B2a'),
        _pair_comparison(rows, 'B1', 'B2b'),
        _pair_comparison(rows, 'B2b', 'B2'),
        _pair_comparison(rows, 'B1', 'B2'),
    ]

    return (
        ' '.join(parts)
        + ' Small-sample diagnostic only; not proof of predictive signal.'
    )


def terminal_report(data, metrics):
    lines = [
        '=' * 92,
        'MATERIAL MARKET REACTION MODEL — B2b RARE-SUBTYPE DIAGNOSTIC',
        '=' * 92,
        'Primary target: |3D stock return minus 3D QQQ return| > 2%',
        'B2b diagnostic: market context + event_type + fold-local grouped subtype',
        f'ML-eligible rows: {len(data)}',
        f'Positive: {int(data.target.sum())}',
        f'Negative: {int(len(data) - data.target.sum())}',
        'Validation: chronological expanding window; grouped dates/events;',
        'training labels must mature strictly before prediction t0.',
        '',
        'OUT-OF-SAMPLE METRICS (2%)',
    ]

    rows = metrics.loc[
        np.isclose(metrics.threshold, 0.02)
    ].set_index('model')

    lines.append(
        f"{'Metric':24}"
        f"{'B0':>12}"
        f"{'B1':>12}"
        f"{'B2a':>12}"
        f"{'B2b':>12}"
        f"{'B2':>12}"
    )

    for key in ['n_predictions', *METRICS]:
        values = []

        for model in MODEL_LEVELS:
            value = rows.loc[model, key]
            values.append(
                str(int(value))
                if key == 'n_predictions'
                else number(value)
            )

        lines.append(
            f'{key:24}'
            + ''.join(f'{v:>12}' for v in values)
        )

    lines += ['', 'THRESHOLD SENSITIVITY']

    for t in THRESHOLDS:
        positives = int(data[target_column(t)].sum())

        lines.append(
            f'{t:.0%}: total={len(data)}, '
            f'positive={positives}, '
            f'negative={len(data) - positives}'
        )

        for model in MODEL_LEVELS:
            r = metrics.loc[
                np.isclose(metrics.threshold, t)
                & metrics.model.eq(model)
            ].iloc[0]

            lines.append(
                f'  {model}: '
                f'OOS={int(r.n_predictions)}, '
                f'log loss={number(r.log_loss)}, '
                f'Brier={number(r.brier_score)}, '
                f'AUC={number(r.roc_auc)}'
            )

        lines.append(interpretation(metrics, t))

    lines += [
        '',
        'DIAGNOSTIC INTERPRETATION',
        interpretation(metrics),
        '',
        'Model definitions:',
        'B0  = training-fold base rate only',
        'B1  = six pre-event numeric market-context features',
        'B2a = B1 + event_type only',
        'B2b = B1 + event_type + event_subtype grouped within each training fold',
        'B2  = B1 + raw event_type + raw event_subtype + relationship_type',
        '',
        'B2b grouping rule:',
        'A subtype is kept only when it appears at least 3 times in that training fold.',
        'Otherwise it becomes OTHER_RARE. The mapping is learned on train only and',
        'then applied to that fold\'s test rows to avoid future-information leakage.',
        '',
        'Experimental portfolio prototype; small, selected historical sample.',
        'Not a production forecast, causal impact, direction, rating or recommendation.',
        '=' * 92,
    ]

    return '\n'.join(lines)


def write_outputs(output, data, predictions, metrics, coef, manifest):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)

    data.to_csv(
        output / 'material_reaction_dataset_v1.csv',
        index=False,
    )

    predictions.loc[
        np.isclose(predictions.threshold, 0.02)
    ].to_csv(
        output / 'material_reaction_predictions_v1.csv',
        index=False,
    )

    predictions.to_csv(
        output / 'material_reaction_sensitivity_predictions_v1.csv',
        index=False,
    )

    metrics.to_csv(
        output / 'material_reaction_metrics_v1.csv',
        index=False,
    )

    coef.to_csv(
        output / 'material_reaction_coefficients_v1.csv',
        index=False,
    )

    (
        output / 'material_reaction_run_manifest_v1.json'
    ).write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + '\n'
    )

    text = terminal_report(data, metrics)

    (
        output / 'material_reaction_report_v1.txt'
    ).write_text(text + '\n')

    return text
