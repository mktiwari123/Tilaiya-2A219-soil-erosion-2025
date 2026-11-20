"""SHAP explanation of the XGBoost model inside a fitted stack."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib
import pandas as pd

import config
from tilaiya.constants import SCENARIOS, TARGET
from tilaiya.explain import explain_xgboost


def parse_args():
    parser = argparse.ArgumentParser(description="Run SHAP on the saved XGBoost base model.")
    parser.add_argument("--scenario", default="Reduced_Integrated", choices=tuple(SCENARIOS))
    return parser.parse_args()


def main():
    args = parse_args()
    bundle_path = config.MODELS / args.scenario / "stack.joblib"
    if not bundle_path.exists():
        raise SystemExit(f"Train the stack first. Missing {bundle_path}")

    bundle = joblib.load(bundle_path)
    test = pd.read_csv(config.DATASETS / "testing.csv")
    features = bundle["features"]
    x_test = test[features].to_numpy(dtype=float)
    predictions = bundle["models"]["XGBoost"].predict(x_test)
    destination = config.FIGURES / args.scenario / "shap"
    importance = explain_xgboost(
        bundle["models"]["XGBoost"],
        x_test,
        features,
        destination,
        predictions,
    )
    print(importance.to_string(index=False))
    print(f"\nSHAP outputs: {destination}")
    print(f"Holdout rows explained: {len(test):,}")
    print(f"Target column used by the stack: {TARGET}")


if __name__ == "__main__":
    main()
