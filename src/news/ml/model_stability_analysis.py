"""Cumulative development metrics; isolated runs, no source mutation or tuning."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASETS = [
    ('H01-H60', 'data/news/market_reaction/historical_market_reaction_H01_H60_v2.csv'),
    ('H01-H90', 'data/news/market_reaction/historical_market_reaction_H01_H90_v3.csv'),
    ('H01-H120', 'data/news/market_reaction/historical_market_reaction_H01_H120_v4.csv'),
]


def read_result(label, output):
    """Read full-precision values; undefined AUC is a valid result."""
    data = pd.read_csv(output / 'material_reaction_dataset_v1.csv')
    metrics = pd.read_csv(output / 'material_reaction_metrics_v1.csv')
    metrics = metrics.loc[np.isclose(metrics.threshold, .03)].set_index('model')
    if not metrics.index.is_unique or not {'B1', 'B2b'}.issubset(metrics.index):
        raise ValueError('Missing or duplicate B1/B2b metrics')
    b1, b2b = metrics.loc['B1'], metrics.loc['B2b']
    if int(b1.n_predictions) != int(b2b.n_predictions):
        raise ValueError('B1 and B2b must score the same observations')
    return dict(sample=label, total=len(data), positive=int(data.label_material_3d_3pct.sum()),
                negative=int(len(data)-data.label_material_3d_3pct.sum()),
                oos_predictions=int(b1.n_predictions),
                b1_log_loss=b1.log_loss, b2b_log_loss=b2b.log_loss,
                delta_log_loss_b2b_minus_b1=b2b.log_loss-b1.log_loss,
                b1_brier=b1.brier_score, b2b_brier=b2b.brier_score,
                delta_brier_b2b_minus_b1=b2b.brier_score-b1.brier_score,
                b1_auc=b1.roc_auc, b2b_auc=b2b.roc_auc,
                delta_auc_b2b_minus_b1=b2b.roc_auc-b1.roc_auc)


def seed_price_cache(source, output):
    """Reuse archived prices so the diagnostic needs no new provider snapshot."""
    from .features import load_eligible
    rows = load_eligible(source)
    start = (rows.t0_session.min()-pd.Timedelta(days=160)).date().isoformat()
    end = rows.t0_session.max().date().isoformat()
    needed = [PROJECT_ROOT/'data/news/ml/price_cache'/f'{ticker}_{start}_{end}_close{ext}'
              for ticker in sorted(set(rows.ticker)|{'QQQ'}) for ext in ('.csv', '.json')]
    for path in needed:
        if not path.is_file():
            raise FileNotFoundError(f'Frozen price cache required: {path}')
    dest = output/'price_cache'
    dest.mkdir()
    for path in needed:
        shutil.copy2(path, dest/path.name)


def run_model_for_dataset(label, dataset_path, output_dir):
    source = (PROJECT_ROOT / dataset_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output = Path(output_dir).resolve() / label
    # Never silently replace an earlier prediction archive.
    output.mkdir(parents=True, exist_ok=False)
    seed_price_cache(source, output)
    subprocess.run([
        sys.executable, '-m', 'src.news.material_reaction_model',
        '--input', str(source), '--output-dir', str(output),
    ], cwd=PROJECT_ROOT, check=True)
    result = read_result(label, output)
    result['dataset_path'] = dataset_path
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        default=PROJECT_ROOT/'data/news/ml/stability_audit')
    args = parser.parse_args()
    paths = [PROJECT_ROOT/path for _, path in DATASETS]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    # Check every destination before starting any model run.
    for label, _ in DATASETS:
        if (args.output_dir/label).exists():
            raise FileExistsError(f'Use a fresh --output-dir; exists: {args.output_dir/label}')
    results = [run_model_for_dataset(label, path, args.output_dir) for label, path in DATASETS]
    frame = pd.DataFrame(results)
    frame.to_csv(args.output_dir/'model_stability_3pct.csv', index=False)
    print(frame.to_string(index=False, na_rep='N/A', float_format=lambda x: f'{x:.6f}'))
    print('Cumulative development snapshots: training histories and OOS populations differ.')
    print('For paired comparison, join saved predictions by case_id, ticker and threshold.')
    print('Undefined or small-sample AUC is not evidence of a stable predictive signal.')


if __name__ == '__main__':
    main()
