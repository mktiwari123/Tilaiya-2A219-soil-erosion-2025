"""Borselli index of connectivity on a D8 drainage grid.

IC = log10(D_up / D_down)
D_up = C_bar * S_bar * sqrt(A_up)
D_down = sum of d_i / (C_i * S_i) along the flow path

The weighting factor C is the RUSLE cover factor (or monthly Cm):
a larger cover factor increases upslope contribution and decreases
downslope impedance, which is the Borselli direction of the index.
Integer-metre flats are not filled with a microscopic gradient. They
are routed toward cells that already have a real downslope.
"""

import heapq

import numpy as np

from tilaiya.constants import SLOPE_MIN, WEIGHT_MIN

# D8 neighbour order: N, NE, E, SE, S, SW, W, NW.
NEIGHBOUR_ROW = np.array([-1, -1, 0, 1, 1, 1, 0, -1], dtype=np.int32)
NEIGHBOUR_COL = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int32)
NEIGHBOUR_DISTANCE = np.array(
    [1.0, np.sqrt(2.0), 1.0, np.sqrt(2.0), 1.0, np.sqrt(2.0), 1.0, np.sqrt(2.0)],
    dtype=np.float64,
)


def priority_flood(elevation, valid):
    """Fill depressions so every cell can drain to the grid boundary.

    Boundary cells of the valid watershed are the spill outlets. This is
    the priority-flood method: an interior cell below its spill elevation
    is raised to just above that elevation.
    """
    filled = np.array(elevation, dtype=np.float64, copy=True)
    valid = np.asarray(valid, dtype=bool)
    filled[~valid] = np.nan
    nrows, ncols = filled.shape
    visited = np.zeros((nrows, ncols), dtype=bool)
    queue = []

    for row in range(nrows):
        for col in range(ncols):
            on_edge = row == 0 or col == 0 or row == nrows - 1 or col == ncols - 1
            if on_edge and valid[row, col] and np.isfinite(filled[row, col]):
                heapq.heappush(queue, (float(filled[row, col]), row, col))
                visited[row, col] = True

    while queue:
        elevation_at_cell, row, col = heapq.heappop(queue)
        for neighbour in range(8):
            next_row = row + int(NEIGHBOUR_ROW[neighbour])
            next_col = col + int(NEIGHBOUR_COL[neighbour])
            if next_row < 0 or next_col < 0 or next_row >= nrows or next_col >= ncols:
                continue
            if visited[next_row, next_col] or not valid[next_row, next_col]:
                continue
            if not np.isfinite(filled[next_row, next_col]):
                continue
            visited[next_row, next_col] = True
            if filled[next_row, next_col] <= elevation_at_cell:
                filled[next_row, next_col] = np.nextafter(elevation_at_cell, np.inf)
            heapq.heappush(
                queue,
                (float(filled[next_row, next_col]), next_row, next_col),
            )

    return filled, visited


def d8_flow(filled, valid, cell_size, slope_min=SLOPE_MIN):
    """Steepest-descent flow direction and slope (m/m).

    Direction is -1 where the cell is a sink or has no lower neighbour.
    Equal elevations are not a descent: integer DEM flats stay unresolved
    here and are routed by resolve_flats.
    """
    filled = np.asarray(filled, dtype=np.float64)
    valid = np.asarray(valid, dtype=bool) & np.isfinite(filled)
    nrows, ncols = filled.shape
    best_drop = np.zeros((nrows, ncols), dtype=np.float64)
    best_direction = np.full((nrows, ncols), -1, dtype=np.int16)
    padded = np.pad(filled, 1, mode="constant", constant_values=np.nan)
    valid_pad = np.pad(valid, 1, mode="constant", constant_values=False)
    for neighbour in range(8):
        row_shift = int(NEIGHBOUR_ROW[neighbour])
        col_shift = int(NEIGHBOUR_COL[neighbour])
        neighbour_elevation = padded[1 + row_shift : 1 + row_shift + nrows, 1 + col_shift : 1 + col_shift + ncols]
        neighbour_valid = valid_pad[1 + row_shift : 1 + row_shift + nrows, 1 + col_shift : 1 + col_shift + ncols]
        drop = (filled - neighbour_elevation) / (cell_size * NEIGHBOUR_DISTANCE[neighbour])
        better = valid & neighbour_valid & np.isfinite(drop) & (drop > best_drop)
        best_drop = np.where(better, drop, best_drop)
        best_direction = np.where(better, neighbour, best_direction)
    slope = np.where(best_drop > 0, best_drop, slope_min)
    direction = np.where(valid, best_direction, -1).astype(np.int16)
    return direction, slope


def _valid_boundary(valid):
    """Cells with a neighbour outside the watershed, or on the grid edge."""
    padded = np.pad(valid, 1, mode="constant", constant_values=False)
    nrows, ncols = valid.shape
    exposed = np.zeros((nrows, ncols), dtype=bool)
    for neighbour in range(8):
        row_shift = int(NEIGHBOUR_ROW[neighbour])
        col_shift = int(NEIGHBOUR_COL[neighbour])
        neighbour_valid = padded[1 + row_shift : 1 + row_shift + nrows, 1 + col_shift : 1 + col_shift + ncols]
        exposed |= ~neighbour_valid
    return exposed & valid


def _box_mean(elevation, valid, radius):
    """Mean elevation in a square window, ignoring cells outside the watershed."""
    values = np.where(valid, elevation, 0.0)
    weights = valid.astype(np.float64)
    integral_values = np.pad(np.cumsum(np.cumsum(values, axis=0), axis=1), ((1, 0), (1, 0)))
    integral_weights = np.pad(np.cumsum(np.cumsum(weights, axis=0), axis=1), ((1, 0), (1, 0)))
    nrows, ncols = elevation.shape
    row_start = np.clip(np.arange(nrows) - radius, 0, nrows)[:, None]
    row_end = np.clip(np.arange(nrows) + radius + 1, 0, nrows)[:, None]
    col_start = np.clip(np.arange(ncols) - radius, 0, ncols)[None, :]
    col_end = np.clip(np.arange(ncols) + radius + 1, 0, ncols)[None, :]
    total = (
        integral_values[row_end, col_end]
        - integral_values[row_start, col_end]
        - integral_values[row_end, col_start]
        + integral_values[row_start, col_start]
    )
    count = (
        integral_weights[row_end, col_end]
        - integral_weights[row_start, col_end]
        - integral_weights[row_end, col_start]
        + integral_weights[row_start, col_start]
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = total / count
    mean[count == 0] = np.nan
    return mean


def resolve_flats(elevation, direction, slope, valid, cell_size, slope_min=SLOPE_MIN):
    """Route integer-DEM flats toward cells that already drain.

    A new link is allowed only onto a cell that already has a path, and
    only if that cell is at the same elevation or lower. That cannot
    create a loop. Among those exits, the smoother elevation picks the
    direction, so a plateau drains toward its real downward side.
    """
    del cell_size  # The raw D8 slope already used cell size. Flats use the floor.
    direction = np.array(direction, dtype=np.int16, copy=True)
    slope = np.array(slope, dtype=np.float64, copy=True)
    valid = np.asarray(valid, dtype=bool)
    elevation = np.asarray(elevation, dtype=np.float64)
    boundary = _valid_boundary(valid)
    resolved = valid & ((direction >= 0) | boundary)
    smoothed = _box_mean(elevation, valid, 11)
    smoothed = np.where(np.isfinite(smoothed), smoothed, elevation)
    nrows, ncols = valid.shape

    for _pass in range(max(nrows, ncols)):
        unresolved = valid & ~resolved
        if not unresolved.any():
            break
        best_score = np.full((nrows, ncols), np.inf, dtype=np.float64)
        best_direction = np.full((nrows, ncols), -1, dtype=np.int16)
        padded_resolved = np.pad(resolved, 1, mode="constant", constant_values=False)
        padded_elevation = np.pad(elevation, 1, mode="constant", constant_values=np.inf)
        padded_smoothed = np.pad(smoothed, 1, mode="constant", constant_values=np.inf)
        for neighbour in range(8):
            row_shift = int(NEIGHBOUR_ROW[neighbour])
            col_shift = int(NEIGHBOUR_COL[neighbour])
            neighbour_resolved = padded_resolved[
                1 + row_shift : 1 + row_shift + nrows, 1 + col_shift : 1 + col_shift + ncols
            ]
            neighbour_elevation = padded_elevation[
                1 + row_shift : 1 + row_shift + nrows, 1 + col_shift : 1 + col_shift + ncols
            ]
            neighbour_smoothed = padded_smoothed[
                1 + row_shift : 1 + row_shift + nrows, 1 + col_shift : 1 + col_shift + ncols
            ]
            eligible = unresolved & neighbour_resolved & (neighbour_elevation <= elevation)
            better = eligible & (neighbour_smoothed < best_score)
            best_score = np.where(better, neighbour_smoothed, best_score)
            best_direction = np.where(better, neighbour, best_direction)
        take = best_direction >= 0
        if not take.any():
            break
        direction = np.where(take, best_direction, direction)
        slope = np.where(take, slope_min, slope)
        resolved |= take

    return direction, slope


def _downstream_index(direction, valid):
    nrows, ncols = direction.shape
    count = nrows * ncols
    downstream = np.full(count, -1, dtype=np.int32)
    valid_flat = valid.ravel()
    direction_flat = direction.ravel()
    for index in range(count):
        neighbour = int(direction_flat[index])
        if neighbour < 0 or not valid_flat[index]:
            continue
        row, col = divmod(index, ncols)
        next_row = row + int(NEIGHBOUR_ROW[neighbour])
        next_col = col + int(NEIGHBOUR_COL[neighbour])
        if next_row < 0 or next_col < 0 or next_row >= nrows or next_col >= ncols:
            continue
        next_index = next_row * ncols + next_col
        if valid_flat[next_index]:
            downstream[index] = next_index
    return downstream


def flow_accumulation(direction, valid, weight, slope):
    """Accumulate cell count, cover weight, and slope downstream."""
    valid = np.asarray(valid, dtype=bool)
    weight = np.where(valid, np.maximum(weight, WEIGHT_MIN), 0.0)
    slope = np.where(valid, np.maximum(slope, SLOPE_MIN), 0.0)
    nrows, ncols = direction.shape
    count = nrows * ncols
    downstream = _downstream_index(direction, valid)

    accumulated_count = np.zeros(count, dtype=np.float64)
    accumulated_weight = np.zeros(count, dtype=np.float64)
    accumulated_slope = np.zeros(count, dtype=np.float64)
    valid_flat = valid.ravel()
    accumulated_count[valid_flat] = 1.0
    accumulated_weight[valid_flat] = weight.ravel()[valid_flat]
    accumulated_slope[valid_flat] = slope.ravel()[valid_flat]

    indegree = np.zeros(count, dtype=np.int32)
    for index, next_index in enumerate(downstream):
        if next_index >= 0:
            indegree[next_index] += 1

    queue = [index for index in range(count) if valid_flat[index] and indegree[index] == 0]
    head = 0
    processed = 0
    while head < len(queue):
        index = queue[head]
        head += 1
        processed += 1
        next_index = downstream[index]
        if next_index < 0:
            continue
        accumulated_count[next_index] += accumulated_count[index]
        accumulated_weight[next_index] += accumulated_weight[index]
        accumulated_slope[next_index] += accumulated_slope[index]
        indegree[next_index] -= 1
        if indegree[next_index] == 0:
            queue.append(next_index)

    shape = direction.shape
    return {
        "count": accumulated_count.reshape(shape),
        "weight": accumulated_weight.reshape(shape),
        "slope": accumulated_slope.reshape(shape),
        "downstream": downstream.reshape(shape),
        "processed_cells": processed,
        "valid_cells": int(valid.sum()),
    }


def downslope_impedance(direction, valid, weight, slope, downstream, cell_size, reservoir=None):
    """Path impedance from each cell to the outlet or the reservoir."""
    valid = np.asarray(valid, dtype=bool)
    if reservoir is None:
        reservoir = np.zeros(valid.shape, dtype=bool)
    else:
        reservoir = np.asarray(reservoir, dtype=bool) & valid

    weight = np.where(valid, np.maximum(np.asarray(weight, dtype=np.float64), WEIGHT_MIN), np.nan)
    slope = np.where(valid, np.maximum(np.asarray(slope, dtype=np.float64), SLOPE_MIN), np.nan)
    nrows, ncols = direction.shape
    count = nrows * ncols
    downstream_flat = downstream.ravel()
    donors = [[] for _ in range(count)]
    for index, next_index in enumerate(downstream_flat):
        if next_index >= 0:
            donors[next_index].append(index)

    impedance = np.full(count, np.nan, dtype=np.float64)
    weight_flat = weight.ravel()
    slope_flat = slope.ravel()
    reservoir_flat = reservoir.ravel()
    valid_flat = valid.ravel()
    direction_flat = direction.ravel()
    stack = []

    for index in range(count):
        if not valid_flat[index]:
            continue
        if reservoir_flat[index]:
            impedance[index] = 0.0
            stack.append(index)
        elif downstream_flat[index] < 0:
            impedance[index] = (0.5 * cell_size) / (weight_flat[index] * slope_flat[index])
            stack.append(index)

    head = 0
    while head < len(stack):
        next_index = stack[head]
        head += 1
        for index in donors[next_index]:
            neighbour = int(direction_flat[index])
            step = cell_size * NEIGHBOUR_DISTANCE[neighbour]
            impedance[index] = (step / (weight_flat[index] * slope_flat[index])) + impedance[next_index]
            stack.append(index)

    return impedance.reshape((nrows, ncols))


def connectivity_index(
    elevation,
    weight,
    cell_size,
    valid=None,
    reservoir=None,
    fill_depressions=True,
):
    """Compute Borselli IC and the D8 slope used to build it.

    weight is the RUSLE C factor or Cm. reservoir marks target water
    cells that receive sediment and are not treated as erosion sources.
    """
    elevation = np.asarray(elevation, dtype=np.float64)
    weight = np.asarray(weight, dtype=np.float64)
    if valid is None:
        valid = np.isfinite(elevation) & np.isfinite(weight)
    else:
        valid = np.asarray(valid, dtype=bool) & np.isfinite(elevation) & np.isfinite(weight)

    if fill_depressions:
        direction, slope = d8_flow(elevation, valid, cell_size)
        direction, slope = resolve_flats(elevation, direction, slope, valid, cell_size)
    else:
        direction, slope = d8_flow(elevation, valid, cell_size)
    accumulated = flow_accumulation(direction, valid, weight, slope)
    impedance = downslope_impedance(
        direction,
        valid,
        weight,
        slope,
        accumulated["downstream"],
        cell_size,
        reservoir=reservoir,
    )

    count = accumulated["count"]
    with np.errstate(divide="ignore", invalid="ignore"):
        mean_weight = np.where(count > 0, accumulated["weight"] / count, np.nan)
        mean_slope = np.where(count > 0, accumulated["slope"] / count, np.nan)
        area_m2 = count * (cell_size ** 2)
        upslope = mean_weight * mean_slope * np.sqrt(area_m2)
        ic = np.log10(upslope / impedance)

    if reservoir is not None:
        ic = np.where(np.asarray(reservoir, dtype=bool), np.nan, ic)
    ic = np.where(valid, ic, np.nan)

    return {
        "ic": ic,
        "slope": slope,
        "direction": direction,
        "upslope_cells": count,
        "d_up": upslope,
        "d_down": impedance,
        "processed_cells": accumulated["processed_cells"],
        "valid_cells": accumulated["valid_cells"],
    }
