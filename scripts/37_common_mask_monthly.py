"""Monthly means of the reported Arnoldus maps on one twelve-month mask.

Other cover formulations and the Copernicus terrain results are annual
grids, so this script does not assign them a July share.
"""

from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus"
OUT = ROOT / "output" / "tables" / "arnoldus_common_mask_monthly.csv"
NODATA = -9999.0


def main():
    paths = [FOLDER / f"SoilLoss_{month:02d}.tif" for month in range(1, 13)]
    with rasterio.open(paths[0]) as source:
        height, width = source.height, source.width
        windows = list(source.block_windows(1))
    total = np.zeros(12, dtype=np.float64)
    count = 0
    for _, window in windows:
        layers = []
        for path in paths:
            with rasterio.open(path) as source:
                values = source.read(1, window=window).astype(np.float32)
            values[np.isclose(values, NODATA)] = np.nan
            layers.append(values)
        stack = np.stack(layers, axis=0)
        valid = np.isfinite(stack).all(axis=0)
        count += int(valid.sum())
        for month in range(12):
            total[month] += float(np.nansum(stack[month][valid]))
    means = total / count
    annual = float(means.sum())
    lines = ["month,mean_t_ha,share_of_annual_sum"]
    for month, mean in enumerate(means, start=1):
        lines.append(f"{month},{mean:.6f},{mean / annual:.6f}")
    lines.append(f"annual_sum,{annual:.6f},1")
    lines.append(f"pixels,{count},")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"pixels {count}")
    print(f"annual sum of means {annual:.4f}")
    print(f"July mean {means[6]:.4f} share {means[6] / annual:.4f}")
    print(OUT)


if __name__ == "__main__":
    main()
