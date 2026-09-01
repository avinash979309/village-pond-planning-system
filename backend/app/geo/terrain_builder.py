"""
Terrain builder: contour lines → regular elevation grid.

Algorithm
---------
1. Sample points uniformly along each contour polyline (configurable density).
   This converts vector contour lines into an irregular point cloud
   (lon, lat, elevation).

2. Define a regular grid covering the bounding box of all contours.

3. Interpolate elevation at every grid cell using scipy.griddata:
   - Primary pass:  method='linear'
     Performs Delaunay triangulation; honours exact contour values; smooth
     interpolation inside the triangulated convex hull.
   - Gap-fill pass: method='nearest'
     Fills NaN cells near the boundary where linear extrapolation is
     undefined (outside the convex hull of sample points).

4. Return the grid alongside its georeferencing metadata.

Why linear interpolation?
--------------------------
At 1 m contour interval, adjacent contour lines are very close.
'linear' produces smooth, geologically reasonable surfaces without
the risk of Gibbs-like oscillations that 'cubic' can introduce
between tightly spaced, nearly parallel contours.
'nearest' would create a staircase surface, which is unacceptable
for slope or flow-direction analysis.

Limitations
-----------
- Accuracy is bounded by the contour interval (≥ interval/2 error).
- Assumes a linear slope between contours; actual terrain may curve.
- NaN areas at convex-hull boundary are filled by nearest-neighbour
  (coarser approximation) and flagged in the returned metadata.

Design note
-----------
This module is purely data-transformation. It does NOT read KML directly;
it consumes a list of ContourLine objects. Future DEM input will skip this
module and produce an ElevationGrid directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy.interpolate import griddata

from app.geo.kml_parser import ContourLine
from app.geo.utils import BBox


# ── Output dataclass ──────────────────────────────────────────────────────────

@dataclass
class ElevationGrid:
    """
    A regular elevation grid derived from contour interpolation.

    Attributes
    ----------
    data : np.ndarray, shape (rows, cols), dtype float64
        Elevation in metres at each grid cell.
        Row 0 = northernmost row, col 0 = westernmost column.
    bbox : BBox
        Geographical extent in WGS84.
    rows, cols : int
        Grid dimensions.
    nan_fraction : float
        Fraction of cells that could not be interpolated (edge regions,
        filled by nearest-neighbour as fallback).
    interpolation_method : str
        Always "linear+nearest_fill" for contour input.
    """
    data: np.ndarray
    bbox: BBox
    rows: int
    cols: int
    nan_fraction: float
    interpolation_method: str = "linear+nearest_fill"

    @property
    def shape(self) -> Tuple[int, int]:
        return self.rows, self.cols

    def elevation_stats(self) -> dict:
        valid = self.data[~np.isnan(self.data)]
        if len(valid) == 0:
            return {"min": None, "max": None, "mean": None, "std": None}
        return {
            "min": float(np.min(valid)),
            "max": float(np.max(valid)),
            "mean": float(np.mean(valid)),
            "std": float(np.std(valid)),
        }


# ── Public API ────────────────────────────────────────────────────────────────

def build_elevation_grid(
    contour_lines: List[ContourLine],
    bbox: BBox,
    grid_resolution: int = 200,
    max_points_per_contour: int = 50,
) -> ElevationGrid:
    """
    Build a regular elevation grid from a list of contour lines.

    Parameters
    ----------
    contour_lines : list of ContourLine
        Parsed contour features (elevation_m + coordinates).
    bbox : BBox
        Bounding box of the data. Grid covers exactly this extent.
    grid_resolution : int
        Number of grid cells along each axis (rows = cols = grid_resolution).
        Higher values → finer grid → slower interpolation.
    max_points_per_contour : int
        Maximum number of sample points per contour polyline.
        Caps the total point cloud size for performance.
        Minimum: 2 (endpoints only).

    Returns
    -------
    ElevationGrid

    Raises
    ------
    ValueError
        If fewer than 3 unique sample points are available (cannot triangulate).
    """
    # ── 1. Sample points from contour polylines ───────────────────────────────
    points_xy: List[Tuple[float, float]] = []
    elevations: List[float] = []

    for cl in contour_lines:
        sampled = _sample_polyline(cl.coordinates, max_points_per_contour)
        for lon, lat in sampled:
            points_xy.append((lon, lat))
            elevations.append(cl.elevation_m)

    if len(points_xy) < 3:
        raise ValueError(
            f"Only {len(points_xy)} sample points extracted from contours. "
            "Need at least 3 for interpolation. Check that contour lines have coordinates."
        )

    pts = np.array(points_xy)       # shape (N, 2)
    vals = np.array(elevations)     # shape (N,)

    # ── 2. Define regular grid ────────────────────────────────────────────────
    rows = cols = grid_resolution
    lon_grid = np.linspace(bbox.west, bbox.east, cols)
    lat_grid = np.linspace(bbox.north, bbox.south, rows)  # north→south = row 0 = top
    grid_lon, grid_lat = np.meshgrid(lon_grid, lat_grid)
    grid_xy = np.column_stack([grid_lon.ravel(), grid_lat.ravel()])

    # ── 3a. Linear interpolation (inside convex hull) ─────────────────────────
    elev_linear = griddata(pts, vals, grid_xy, method="linear")

    # ── 3b. Nearest-neighbour fill for NaN boundary cells ─────────────────────
    elev_nearest = griddata(pts, vals, grid_xy, method="nearest")

    nan_mask = np.isnan(elev_linear)
    nan_fraction = float(nan_mask.sum()) / float(nan_mask.size)

    elev_combined = elev_linear.copy()
    elev_combined[nan_mask] = elev_nearest[nan_mask]

    grid_data = elev_combined.reshape(rows, cols)

    return ElevationGrid(
        data=grid_data,
        bbox=bbox,
        rows=rows,
        cols=cols,
        nan_fraction=nan_fraction,
        interpolation_method="linear+nearest_fill",
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _sample_polyline(
    coords: List[Tuple[float, float]],
    n_points: int,
) -> List[Tuple[float, float]]:
    """
    Sample up to n_points uniformly distributed along a polyline.

    Uses arc-length parameterisation to place sample points at equal
    intervals along the polyline (not equal intervals in lon/lat space).

    Algorithm
    ----------
    1. Compute cumulative Euclidean distance along the polyline.
    2. Create n_points equally spaced distance values from 0 to total_length.
    3. For each target distance, find the segment it falls in and
       linearly interpolate between the two endpoints of that segment.

    Parameters
    ----------
    coords : list of (lon, lat)
    n_points : int
        Maximum number of sample points. Clamped to at least 2 and
        at most len(coords).

    Returns
    -------
    list of (lon, lat) sample points
    """
    if len(coords) < 2:
        return coords

    pts = np.array(coords, dtype=np.float64)  # (K, 2)
    n_points = max(2, min(n_points, len(pts)))

    # Cumulative Euclidean distance (in degree units — acceptable for sampling)
    diffs = np.diff(pts, axis=0)
    seg_lens = np.sqrt((diffs ** 2).sum(axis=1))
    cum_dist = np.concatenate([[0.0], np.cumsum(seg_lens)])
    total_dist = cum_dist[-1]

    if total_dist == 0.0:
        # Degenerate line (all points coincident)
        return [tuple(pts[0])]

    target_dists = np.linspace(0.0, total_dist, n_points)
    sampled: List[Tuple[float, float]] = []

    for d in target_dists:
        idx = int(np.searchsorted(cum_dist, d, side="right")) - 1
        idx = max(0, min(idx, len(pts) - 2))
        seg_len = seg_lens[idx]
        if seg_len > 0:
            t = (d - cum_dist[idx]) / seg_len
        else:
            t = 0.0
        pt = pts[idx] + t * (pts[idx + 1] - pts[idx])
        sampled.append((float(pt[0]), float(pt[1])))

    return sampled
