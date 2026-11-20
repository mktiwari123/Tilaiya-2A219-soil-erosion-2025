"""Monthly rainfall erosivity from an IMD daily or monthly table."""

from pathlib import Path

import numpy as np
import pandas as pd

from tilaiya.factors import monthly_erosivity


def _read_table(path):
    table = pd.read_csv(path)
    table.columns = [column.strip().lower() for column in table.columns]
    return table


def monthly_precipitation_mm(path, year):
    """Return 12 monthly totals (mm) and the annual total for one year.

    Accepted tables:
    - date, precip_mm
    - year, month, precip_mm
    - month, precip_mm  (already one year)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Rainfall table not found: {path}\n"
            "Save IMD daily rainfall as data/rainfall/imd_daily.csv "
            "with columns date and precip_mm."
        )

    table = _read_table(path)
    precip_column = next(
        (name for name in ("precip_mm", "rainfall_mm", "rain_mm", "rain") if name in table.columns),
        None,
    )
    if precip_column is None:
        raise ValueError("The rainfall table needs a precip_mm column.")

    if "date" in table.columns:
        dates = pd.to_datetime(table["date"])
        selected = table.loc[dates.dt.year == int(year)].copy()
        if selected.empty:
            raise ValueError(f"No rainfall rows for {year} in {path}.")
        selected["month"] = dates.loc[selected.index].dt.month.to_numpy()
        monthly = selected.groupby("month")[precip_column].sum()
    elif "month" in table.columns:
        selected = table
        if "year" in table.columns:
            selected = table.loc[table["year"].astype(int) == int(year)]
            if selected.empty:
                raise ValueError(f"No rainfall rows for {year} in {path}.")
        monthly = selected.groupby(selected["month"].astype(int))[precip_column].sum()
    else:
        raise ValueError("The rainfall table needs a date column or a month column.")

    monthly = monthly.reindex(range(1, 13), fill_value=0.0).astype(float)
    values = monthly.to_numpy(dtype=np.float64)
    return values, float(values.sum())


def monthly_erosivity_table(path, year):
    """Build the 12-value Rm series used by monthly RUSLE."""
    monthly_mm, annual_mm = monthly_precipitation_mm(path, year)
    erosivity = monthly_erosivity(monthly_mm, annual_mm)
    frame = pd.DataFrame(
        {
            "year": int(year),
            "month": np.arange(1, 13),
            "precip_mm": monthly_mm,
            "Rm": erosivity,
        }
    )
    return frame
