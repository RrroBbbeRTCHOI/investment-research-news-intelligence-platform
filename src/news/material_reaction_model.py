"""Run the independent, small-sample material market reaction experiment."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import platform

from .ml.features import load_eligible, load_prices, build_dataset, THRESHOLDS, target_column
from .ml.model import coefficients
from .ml.validation import evaluate
from .ml.reporting import write_outputs

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT/'data/news/market_reaction/historical_market_reaction_H01_H120_v4.csv'
DEFAULT_OUTPUT = ROOT/'data/news/ml'


def run(input_path=DEFAULT_INPUT, output_dir=DEFAULT_OUTPUT, min_train=10, refresh=False):
    import numpy, pandas, sklearn, yfinance
    input_path, output_dir = Path(input_path), Path(output_dir)
    original_hash = sha256(input_path.read_bytes()).hexdigest()
    rows = load_eligible(input_path)
    prices, price_meta = load_prices(rows, output_dir/'price_cache', refresh)
    data = build_dataset(rows, prices)
    predictions, metrics = evaluate(data, min_train)
    coef = coefficients(data)
    if sha256(input_path.read_bytes()).hexdigest() != original_hash:
        raise RuntimeError('Source CSV changed during execution')
    manifest = dict(run_at=datetime.now(timezone.utc).isoformat(),
                    input_name=input_path.name, input_sha256=original_hash,
                    n_eligible=len(data), n_events=data.case_id.nunique(), min_train=min_train,
                    thresholds=[dict(threshold=t, positive=int(data[target_column(t)].sum()),
                                     negative=int(len(data)-data[target_column(t)].sum())) for t in THRESHOLDS],
                    versions=dict(python=platform.python_version(), numpy=numpy.__version__,
                                  pandas=pandas.__version__, sklearn=sklearn.__version__, yfinance=yfinance.__version__),
                    model=dict(penalty='l2', C=1.0, solver='liblinear', max_iter=3000, random_state=0),
                    prices=price_meta, missing_numeric_cells=int(data.filter(regex='^pre(?:5|20|60)_').isna().sum().sum()),
                    descriptive_encoded_features=len(coef), source_unchanged=True)
    return write_outputs(output_dir, data, predictions, metrics, coef, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--min-train', type=int, default=10)
    parser.add_argument('--refresh-prices', action='store_true')
    args = parser.parse_args()
    try:
        print(run(args.input, args.output_dir, args.min_train, args.refresh_prices))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f'Material-reaction run failed: {exc}\n')


if __name__ == '__main__':
    main()
