"""
Terrain conditioner: slope analysis from an elevation grid.

Responsibilities
----------------
- Compute slope (in degrees) from a regular elevation grid using
  central-difference gradient estimation (numpy.gradient).
- Compute basic terrain statistics for the response payload.

Algorithm — slope from gradient
--------------------------------
Given an elevation grid Z[row, col]:

    dZ/dy = np.gradient(Z, cell_size_lat_m, axis=0)  # N-S gradient
    dZ/dx = np.gradient(Z, cell_size_lon_m, axis=1)  # E-W gradient
    slope_rad = arctan(sqrt((dZ/dx)² + (dZ/dy)²))
    slope_deg = degrees(slope_rad)

np.gradient uses central differences for interior points and
one-sided differences at edges — no special edge treatment needed.

Cell sizes are computed in metres using the approximate conversion:
    lat_cell_m = (lat_range_deg / rows) * 110_540
    lon_cell_m = (lon_range_deg / cols) * 111_320 * cos(lat_centre)

This module is generic — it receives a numpy array and spatial metadata,
not a KML file. It is reusable for DEM-derived grids in later phases.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.geo.utils import BBox, approx_cell_size_m


# ── Output ────────────────────────────────────────────────────────────────────

@dataclass
class SlopeGrid:
    """
    Slope values for every grid cell.

    Attributes
    ----------
    data : np.ndarray, shape (rows, cols)
        Slope in degrees. Range [0, 90).
    stats : dict
        min, max, mean, std slope in degrees for the entire grid.
    cell_size_lon_m, cell_size_lat_m : float
        Approximate cell dimensions in metres used during computation.
    """
    data: np.ndarray
    stats: dict
    cell_size_lon_m: float
    cell_size_lat_m: float


# ── Public API ────────────────────────────────────────────────────────────────

def compute_slope(elev_grid: np.ndarray, bbox: BBox) -> SlopeGrid:
    """
    Compute slope in degrees from an elevation grid.

    Parameters
    ----------
    elev_grid : np.ndarray, shape (rows, cols)
        Elevation values in metres. Row 0 = northernmost row.
    bbox : BBox
        Spatial extent of the grid (WGS84).

    Returns
    -------
    SlopeGrid
    """
    rows, cols = elev_grid.shape

    # Cell sizes in metres
    lon_cell_m, lat_cell_m = approx_cell_size_m(bbox, (rows, cols))

    # Gradients: dZ/dy (row direction = N-S), dZ/dx (col direction = E-W)
    # np.gradient(arr, spacing, axis) — spacing in metres
    dz_dy = np.gradient(elev_grid, lat_cell_m, axis=0)
    dz_dx = np.gradient(elev_grid, lon_cell_m, axis=1)

    slope_rad = np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))
    slope_deg = np.degrees(slope_rad)

    # Clip to valid range (floating-point noise can produce tiny negatives)
    slope_deg = np.clip(slope_deg, 0.0, 90.0)

    stats = {
        "min": float(np.nanmin(slope_deg)),
        "max": float(np.nanmax(slope_deg)),
        "mean": float(np.nanmean(slope_deg)),
        "std": float(np.nanstd(slope_deg)),
    }

    return SlopeGrid(
        data=slope_deg,
        stats=stats,
        cell_size_lon_m=lon_cell_m,
        cell_size_lat_m=lat_cell_m,
    )
