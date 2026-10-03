from __future__ import annotations

import argparse
from pathlib import Path
from sklearn.metrics import roc_auc_score
import numpy as np
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

INPUT = Path("data/news/ml/material_reaction_sensitivity_predictions_v1.csv")
OUTPUT = Path("data/news/ml/chronological_cohort_error_analysis_3pct.csv")

TARGET_THRESHOLD = 0.03



# ============================================================
# HELPERS
# ============================================================

def select_cohort(df, start_date, end_date=None):
    """Fixed date bounds: start inclusive, end exclusive; never use H IDs."""
    dates = pd.to_datetime(df['effective_event_date'], errors='raise')
    if dates.isna().any():
        raise ValueError('Missing effective_event_date')
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) if end_date is not None else None
    if pd.isna(start) or (end is not None and (pd.isna(end) or end <= start)):
        raise ValueError('Invalid chronological bounds')
    selected = np.isclose(pd.to_numeric(df['threshold'], errors='raise'), TARGET_THRESHOLD)
    selected &= dates >= start
    if end is not None:
        selected &= dates < end
    return df.loc[selected].copy()


def binary_log_loss_contribution(y: int, p: float) -> float:
    p = float(np.clip(p, 1e-15, 1 - 1e-15))
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier_contribution(y: int, p: float) -> float:
    return float((float(p) - int(y)) ** 2)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description='Diagnostic by explicit event dates, not collection IDs.')
    parser.add_argument('--input', type=Path, default=INPUT)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--start-date', required=True, help='Inclusive YYYY-MM-DD; choose without viewing errors')
    parser.add_argument('--end-date', help='Exclusive YYYY-MM-DD')
    args = parser.parse_args()
    input_path, output_path = args.input, args.output
    if output_path.exists():
        raise FileExistsError(f'Use a fresh --output; refusing to overwrite {output_path}')
    if not input_path.exists():
        raise FileNotFoundError(
            f"Missing {input_path}\n"
            "Run: python3 -m src.news.material_reaction_model"
        )

    df = pd.read_csv(input_path)

    required = {
        "case_id",
        "effective_event_date",
        "ticker",
        "event_type",
        "event_subtype",
        "threshold",
        "target",
        "p_b1",
        "p_b2b",
    }

    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(
            "Prediction file is missing required columns: "
            + ", ".join(sorted(missing))
        )

    late = select_cohort(df, args.start_date, args.end_date)
    if late.empty:
        raise RuntimeError('No 3% OOS predictions in the requested date interval.')

    late["target"] = pd.to_numeric(late["target"], errors="raise").astype(int)
    late["p_b1"] = pd.to_numeric(late["p_b1"], errors="raise")
    late["p_b2b"] = pd.to_numeric(late["p_b2b"], errors="raise")

    late["b1_log_loss"] = [
        binary_log_loss_contribution(y, p)
        for y, p in zip(late["target"], late["p_b1"])
    ]
    late["b2b_log_loss"] = [
        binary_log_loss_contribution(y, p)
        for y, p in zip(late["target"], late["p_b2b"])
    ]

    late["delta_log_loss_b2b_minus_b1"] = (
        late["b2b_log_loss"] - late["b1_log_loss"]
    )

    late["b1_brier"] = [
        brier_contribution(y, p)
        for y, p in zip(late["target"], late["p_b1"])
    ]
    late["b2b_brier"] = [
        brier_contribution(y, p)
        for y, p in zip(late["target"], late["p_b2b"])
    ]

    late["delta_brier_b2b_minus_b1"] = (
        late["b2b_brier"] - late["b1_brier"]
    )

    late["b1_pred"] = (late["p_b1"] >= 0.5).astype(int)
    late["b2b_pred"] = (late["p_b2b"] >= 0.5).astype(int)

    late["b1_abs_probability_error"] = abs(late["p_b1"] - late["target"])
    late["b2b_abs_probability_error"] = abs(late["p_b2b"] - late["target"])

    late["b2b_vs_b1"] = np.where(
        late["delta_log_loss_b2b_minus_b1"] < 0,
        "B2b better",
        np.where(
            late["delta_log_loss_b2b_minus_b1"] > 0,
            "B2b worse",
            "equal",
        ),
    )

    keep = [
        "case_id",
        "ticker",
        "effective_event_date",
        "event_type",
        "event_subtype",
        "relationship_type",
        "target",
        "p_b1",
        "p_b2b",
        "b1_pred",
        "b2b_pred",
        "b1_log_loss",
        "b2b_log_loss",
        "delta_log_loss_b2b_minus_b1",
        "b1_brier",
        "b2b_brier",
        "delta_brier_b2b_minus_b1",
        "b1_abs_probability_error",
        "b2b_abs_probability_error",
        "b2b_vs_b1",
        "fold",
        "n_train",
    ]

    keep = [c for c in keep if c in late.columns]
    late = late[keep].sort_values(
        "delta_log_loss_b2b_minus_b1",
        ascending=False,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    late.to_csv(output_path, index=False)

    print("=" * 118)
    print("CHRONOLOGICAL COHORT ERROR ANALYSIS — 3% TARGET")
    print(f"Effective event dates: [{args.start_date}, {args.end_date or 'unbounded'})")
    print("=" * 118)
    print(f"Rows analysed: {len(late)}")
    print("Positive labels:", int(late["target"].sum()))
    print("Negative labels:", int(len(late) - late["target"].sum()))
    print()

    print("COHORT-LEVEL PROBABILISTIC ERROR")
    print("-" * 60)
    print(f"B1 mean log loss : {late['b1_log_loss'].mean():.4f}")
    print(f"B2b mean log loss: {late['b2b_log_loss'].mean():.4f}")
    print(
        "Delta LL (B2b-B1): "
        f"{late['delta_log_loss_b2b_minus_b1'].mean():+.4f}"
    )
    print()
    print(f"B1 mean Brier    : {late['b1_brier'].mean():.4f}")
    print(f"B2b mean Brier   : {late['b2b_brier'].mean():.4f}")
    print(
        "Delta Brier      : "
        f"{late['delta_brier_b2b_minus_b1'].mean():+.4f}"
    )

    print("\nPER-CASE ERRORS — worst B2b deterioration first")
    print("-" * 118)

    for _, r in late.iterrows():
        print(
            f"{r['case_id']:>4} | "
            f"{r['ticker']:<5} | "
            f"{str(r['event_type']):<22} | "
            f"{str(r['event_subtype']):<24} | "
            f"y={int(r['target'])} | "
            f"B1={r['p_b1']:.3f} | "
            f"B2b={r['p_b2b']:.3f} | "
            f"ΔLL={r['delta_log_loss_b2b_minus_b1']:+.3f} | "
            f"{r['b2b_vs_b1']}"
        )

    for model in ('b1', 'b2b'):
        auc = roc_auc_score(late.target, late[f'p_{model}']) if late.target.nunique() == 2 else None
        print(f"{model} AUC: {auc if auc is not None else 'undefined (one class)'}")
    print('Small selected cohort: AUC is exploratory and may be unreliable; no significance claim.')
    print("\nLargest B2b relative loss difference (may be negative if all improved):")
    worst = late.iloc[0]
    print(
        f"{worst['case_id']} {worst['ticker']} "
        f"{worst['event_type']}/{worst['event_subtype']} — "
        f"target={int(worst['target'])}, "
        f"B1={worst['p_b1']:.3f}, "
        f"B2b={worst['p_b2b']:.3f}, "
        f"ΔLL={worst['delta_log_loss_b2b_minus_b1']:+.3f}"
    )

    print("\nSaved:")
    print(output_path)

    print("\nInterpretation:")
    print("- Positive ΔLL / ΔBrier means B2b was worse than B1 on that case.")
    print("- Negative ΔLL / ΔBrier means B2b improved on B1.")
    print("- This is error diagnosis only; it does not change or tune the model.")


if __name__ == "__main__":
    main()
