"""Draw the 12,697-point stratified sample and keep pixel coordinates."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from tilaiya.sampling import build_point_table, stratified_sample


def main():
    print("Reading the baseline predictor stack and annual soil-loss raster...")
    population = build_point_table(config.PREDICTOR_STACK, config.ANNUAL_SOIL_LOSS)
    print(f"Valid pixels: {len(population):,}")

    sampled, train, test, summary = stratified_sample(population)
    summary.to_csv(config.TABLES / "sampling_summary.csv", index=False)
    sampled.to_csv(config.DATASETS / "stratified_12697.csv", index=False)
    train.to_csv(config.DATASETS / "training.csv", index=False)
    test.to_csv(config.DATASETS / "testing.csv", index=False)

    print(summary.to_string(index=False))
    print(f"\nTraining points: {len(train):,}")
    print(f"Testing points:  {len(test):,}")
    print(f"Saved {config.DATASETS / 'stratified_12697.csv'}")


if __name__ == "__main__":
    main()
