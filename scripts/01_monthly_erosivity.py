"""Compute the 12 monthly erosivity values from the IMD rainfall table."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from tilaiya.rainfall import monthly_erosivity_table


def main():
    table = monthly_erosivity_table(config.DAILY_RAINFALL_CSV, config.ANALYSIS_YEAR)
    destination = config.TABLES / f"Rm_{config.ANALYSIS_YEAR}.csv"
    table.to_csv(destination, index=False)
    print(table.to_string(index=False))
    print(f"\nSaved {destination}")


if __name__ == "__main__":
    main()
