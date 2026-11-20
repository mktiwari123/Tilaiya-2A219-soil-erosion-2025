"""Stratified sample of 12,697 points, with coordinates retained.

The class breaks, sample size, and random seed match the baseline
annual study. Coordinates are stored so the five folds can be spatial
blocks and so monthly Earth Engine layers can be joined later at the
same pixels.
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from tilaiya.constants import (
    EROSION_BINS,
    EROSION_LABELS,
    N_SAMPLES,
    RANDOM_STATE,
    SPATIAL_BLOCK_M,
    STACK_BANDS,
    TARGET,
    TRAIN_ROWS,
)
from tilaiya.rasters import cell_centres, read_band


def erosion_class(soil_loss):
    """Classify annual soil loss with the baseline break points."""
    return pd.cut(
        soil_loss,
        bins=list(EROSION_BINS) + [np.inf],
        labels=list(EROSION_LABELS),
        include_lowest=True,
        right=True,
    )


def spatial_block_id(x_coord, y_coord, block_size_m=SPATIAL_BLOCK_M):
    x_block = np.floor(np.asarray(x_coord) / block_size_m).astype(np.int64)
    y_block = np.floor(np.asarray(y_coord) / block_size_m).astype(np.int64)
    return np.array([f"{x}_{y}" for x, y in zip(x_block, y_block)])


def valid_pixel_mask(predictors, soil_loss, stack_nodata=None, target_nodata=None):
    """Reproduce the master-dataset mask from the annual study."""
    mask = np.isfinite(soil_loss) & (soil_loss >= 0)
    if target_nodata is not None:
        mask &= ~np.isclose(soil_loss, target_nodata)
    for band in predictors:
        mask &= np.isfinite(band)
        if stack_nodata is not None:
            mask &= ~np.isclose(band, stack_nodata)
        if target_nodata is not None:
            mask &= ~np.isclose(band, target_nodata)
    return mask


def stratified_sample(frame, n_samples=N_SAMPLES, random_state=RANDOM_STATE):
    """Draw a class-proportional sample and the 8,888 / 3,809 split."""
    labels = list(EROSION_LABELS)
    counts = frame["Class"].value_counts().reindex(labels)
    if counts.isna().any():
        missing = [label for label, count in counts.items() if pd.isna(count) or count == 0]
        raise ValueError(f"No pixels in erosion class: {', '.join(missing)}")

    shares = counts / counts.sum()
    allocated = (shares * n_samples).round().astype(int)
    allocated.iloc[0] += int(n_samples - allocated.sum())

    parts = []
    for label in labels:
        subset = frame.loc[frame["Class"] == label]
        parts.append(subset.sample(n=int(allocated.loc[label]), random_state=random_state))

    sampled = pd.concat(parts, ignore_index=True)
    sampled = sampled.sample(frac=1, random_state=random_state).reset_index(drop=True)
    train, test = train_test_split(
        sampled,
        train_size=TRAIN_ROWS,
        random_state=random_state,
        stratify=sampled["Class"],
    )
    summary = pd.DataFrame(
        {
            "class": labels,
            "pixels": counts.to_numpy(),
            "percent": (shares * 100).to_numpy(),
            "samples": allocated.to_numpy(),
        }
    )
    return sampled.reset_index(drop=True), train.reset_index(drop=True), test.reset_index(drop=True), summary


def build_point_table(stack_path, target_path, band_names=STACK_BANDS):
    """Read the aligned predictor stack and keep row, column, x, and y."""
    import rasterio

    with rasterio.open(stack_path) as stack_source:
        predictors = stack_source.read().astype(np.float32)
        stack_nodata = stack_source.nodata
        transform = stack_source.transform
        if predictors.shape[0] != len(band_names):
            raise ValueError(
                f"Expected {len(band_names)} bands in {stack_path}, found {predictors.shape[0]}."
            )

    soil_loss, _profile = read_band(target_path)
    if predictors.shape[1:] != soil_loss.shape:
        raise ValueError("Predictor stack and soil-loss raster are not on the same grid.")

    mask = valid_pixel_mask(predictors, soil_loss, stack_nodata=stack_nodata, target_nodata=None)
    # read_band already replaced the target NoData with NaN, and the
    # finite-value test removes it. Also drop the stack NoData value.
    rows, cols = np.where(mask)
    x_coord, y_coord = cell_centres(transform, rows, cols)

    frame = pd.DataFrame({name: predictors[index][rows, cols] for index, name in enumerate(band_names)})
    frame[TARGET] = soil_loss[rows, cols]
    frame.insert(0, "col", cols)
    frame.insert(0, "row", rows)
    frame.insert(0, "y", y_coord)
    frame.insert(0, "x", x_coord)
    frame["Class"] = erosion_class(frame[TARGET])
    frame["block_id"] = spatial_block_id(frame["x"], frame["y"])
    frame = frame.dropna(subset=["Class"]).reset_index(drop=True)
    return frame
