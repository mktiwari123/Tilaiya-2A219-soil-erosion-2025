"""Train the two-level stacking ensemble for one predictor scenario."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

import config
from tilaiya.constants import SCENARIOS, TARGET
from tilaiya.stacking import fit_stack


def parse_args():
    parser = argparse.ArgumentParser(description="Train the Ridge stacking ensemble.")
    parser.add_argument(
        "--scenario",
        default="Reduced_Integrated",
        choices=tuple(SCENARIOS),
        help="Predictor set. Reduced_Integrated is the baseline study's best set.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    train = pd.read_csv(config.DATASETS / "training.csv")
    test = pd.read_csv(config.DATASETS / "testing.csv")
    features = list(SCENARIOS[args.scenario])
    missing = [name for name in features if name not in train.columns]
    if missing:
        raise SystemExit(
            f"Scenario {args.scenario} needs columns that are not in the sample yet: "
            + ", ".join(missing)
            + ".\nDynamic_Integrated is available after monthly factors are joined "
            "to the point table."
        )

    result = fit_stack(
        train[features].to_numpy(dtype=float),
        train[TARGET].to_numpy(dtype=float),
        test[features].to_numpy(dtype=float),
        test[TARGET].to_numpy(dtype=float),
        groups=train["block_id"].to_numpy() if "block_id" in train.columns else None,
    )

    scenario_dir = config.MODELS / args.scenario
    scenario_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "models": result["models"],
            "meta": result["meta"],
            "features": features,
            "fold_kind": result["fold_kind"],
        },
        scenario_dir / "stack.joblib",
    )

    rows = []
    for name, scores in result["scores"].items():
        row = {"model": name, "fold_kind": result["fold_kind"]}
        row.update(scores)
        rows.append(row)
    scores = pd.DataFrame(rows)
    scores.to_csv(config.TABLES / f"{args.scenario}_scores.csv", index=False)

    coefficients = pd.DataFrame(
        {
            "base_model": list(result["meta_coefficients"]),
            "ridge_coefficient": list(result["meta_coefficients"].values()),
        }
    )
    coefficients.loc[len(coefficients)] = ["intercept", result["meta_intercept"]]
    coefficients.to_csv(config.TABLES / f"{args.scenario}_ridge_weights.csv", index=False)

    predictions = test[["x", "y", "row", "col", TARGET]].copy() if "x" in test.columns else test[[TARGET]].copy()
    predictions["predicted"] = result["test_prediction"]
    predictions.to_csv(config.TABLES / f"{args.scenario}_holdout_predictions.csv", index=False)

    figure_dir = config.FIGURES / args.scenario
    figure_dir.mkdir(parents=True, exist_ok=True)
    observed = test[TARGET].to_numpy(dtype=float)
    predicted = result["test_prediction"]
    plt.figure(figsize=(6, 6))
    plt.scatter(observed, predicted, s=8, alpha=0.4, color="#1f4e79")
    upper = max(observed.max(), predicted.max())
    plt.plot([0, upper], [0, upper], color="black", linewidth=1)
    plt.xlabel("RUSLE soil loss (t/ha/yr)")
    plt.ylabel("Stacked prediction (t/ha/yr)")
    plt.tight_layout()
    plt.savefig(figure_dir / "observed_vs_predicted.png", dpi=200)
    plt.close()

    print(scores.to_string(index=False))
    print(f"\nFolds: {result['fold_kind']}")
    print(f"Model saved to {scenario_dir / 'stack.joblib'}")


if __name__ == "__main__":
    main()
