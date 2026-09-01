"""
Catchment delineator.

Algorithm
---------
1. Snap the pond candidate location to the nearest high-accumulation cell
   within a search radius (pour-point determination).
   This ensures the hydrological pour point is on a defined flow path
   rather than on the arbitrary candidate cell, which may be slightly
   off-channel.

2. Use pysheds grid.catchment() to trace all upstream cells that drain
   to the pour point.

3. Vectorise the catchment raster mask to a GeoJSON Polygon using
   rasterio.features.shapes.

4. Compute the catchment area using pyproj UTM projection.
   Area MUST NOT be computed in degree-squared units.

5. Compute catchment statistics (average elevation, cell count, centroid).

Design note
-----------
The distinction between pond candidate (selected by suitability scoring)
and pour point (snapped to drainage) is maintained here.
The pond is not necessarily placed directly on the drainage channel —
it is the candidate location. The pour point is a nearby drainage cell
used as the hydrological input to delineation.

This module receives a pysheds Grid already constructed by hydrology_engine.
It does NOT re-read the DEM file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import rasterio
from rasterio.features import shapes
from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union

# ── NumPy 2.x compatibility for pysheds ──────────────────────────────────────
if not hasattr(np, "in1d"):
    def _in1d_compat(ar1, ar2, **kw):
        import numpy as _n
        return _n.isin(ar1, ar2, **kw).ravel()
    np.in1d = _in1d_compat
# ─────────────────────────────────────────────────────────────────────────────


from app.geo.utils import BBox, coords_to_grid_index, grid_index_to_coords, haversine_m, utm_epsg_for_bbox

try:
    from pyproj import CRS, Transformer
    _PYPROJ_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYPROJ_AVAILABLE = False



# ── Output ────────────────────────────────────────────────────────────────────

@dataclass
class PourPointResult:
    lon: float
    lat: float
    row: int
    col: int
    snap_distance_m: float
    flow_accumulation: float


@dataclass
class CatchmentResult:
    geojson: dict                   # GeoJSON Feature (Polygon)
    area_sq_m: float
    area_sq_km: float
    avg_elevation_m: float
    cell_count: int
    centroid_lon: float
    centroid_lat: float
    projection_epsg: int
    pour_point: PourPointResult


# ── Public API ────────────────────────────────────────────────────────────────

def snap_to_pour_point(
    candidate_lon: float,
    candidate_lat: float,
    flow_accumulation: np.ndarray,
    drainage_mask: np.ndarray,
    bbox: BBox,
    snap_radius_cells: int = 5,
) -> PourPointResult:
    """
    Snap a pond candidate location to the nearest high-flow drainage cell.

    Rationale
    ---------
    pysheds delineation works best when the pour point sits on a
    well-defined flow path (high accumulation cell). Placing the pour
    point slightly off-channel can cause the catchment to be tiny
    (only a few cells) or miss the main drainage network.

    Algorithm
    ----------
    - Convert candidate (lon, lat) to grid (row, col).
    - Search within snap_radius_cells for the cell with the highest
      flow accumulation.
    - Return that cell's coordinates as the pour point.
    - Record the snap distance in metres.

    Parameters
    ----------
    candidate_lon, candidate_lat : float
    flow_accumulation : np.ndarray (rows, cols)
    drainage_mask : np.ndarray (bool)
        True = drainage channel cells. Pour point preferentially snaps here.
    bbox : BBox
    snap_radius_cells : int

    Returns
    -------
    PourPointResult
    """
    rows, cols = flow_accumulation.shape
    cand_row, cand_col = coords_to_grid_index(candidate_lon, candidate_lat, bbox, (rows, cols))

    # Search window
    r_lo = max(0, cand_row - snap_radius_cells)
    r_hi = min(rows - 1, cand_row + snap_radius_cells)
    c_lo = max(0, cand_col - snap_radius_cells)
    c_hi = min(cols - 1, cand_col + snap_radius_cells)

    window_acc = flow_accumulation[r_lo:r_hi+1, c_lo:c_hi+1].copy()

    # Prefer drainage cells within window; if none, use all cells
    window_drain = drainage_mask[r_lo:r_hi+1, c_lo:c_hi+1]
    if window_drain.any():
        # Zero-out non-drainage cells to prefer drainage
        search_acc = window_acc * window_drain.astype(float)
    else:
        search_acc = window_acc

    flat_idx = int(np.argmax(search_acc))
    win_row, win_col = np.unravel_index(flat_idx, search_acc.shape)
    snap_row = r_lo + win_row
    snap_col = c_lo + win_col

    snap_lon, snap_lat = grid_index_to_coords(snap_row, snap_col, bbox, (rows, cols))
    snap_dist_m = haversine_m(candidate_lon, candidate_lat, snap_lon, snap_lat)

    return PourPointResult(
        lon=snap_lon,
        lat=snap_lat,
        row=int(snap_row),
        col=int(snap_col),
        snap_distance_m=snap_dist_m,
        flow_accumulation=float(flow_accumulation[snap_row, snap_col]),
    )


def delineate_catchment(
    pysheds_grid,          # pysheds.grid.Grid (not mutated — kept for API compat)
    flow_direction_arr: np.ndarray,
    pour_point: PourPointResult,
    elev_grid: np.ndarray,
    bbox: BBox,
    temp_dem_path: str,
) -> CatchmentResult:
    """
    Delineate the catchment area upstream of the pour point.

    Each call runs in an isolated subprocess so pysheds C-heap state is
    reset between candidates. This prevents malloc corruption
    (malloc: mismatching next->prev_size) that occurs when pysheds
    fill_pits/resolve_flats/flowdir/catchment are called > once in-process.

    Parameters
    ----------
    pysheds_grid : pysheds.grid.Grid
        Accepted for API compatibility but NOT used; subprocess creates its own.
    flow_direction_arr : np.ndarray
        D8 flow direction grid (unused here; kept for signature compat).
    pour_point : PourPointResult
    elev_grid : np.ndarray (rows, cols)
        Original elevation grid (for average elevation in catchment).
    bbox : BBox
    temp_dem_path : str
        Path to the temporary GeoTIFF (needed to read rasterio transform).

    Returns
    -------
    CatchmentResult
    """
    # ── Subprocess isolation ──────────────────────────────────────────────────
    # pysheds (<=0.5) corrupts the C heap when fill_pits/fill_depressions/
    # resolve_flats/flowdir/catchment are called more than once in the same
    # process (malloc: mismatching next->prev_size). Running each delineation
    # in a fresh subprocess gives it a clean heap. No shared state possible.
    import json as _json
    import subprocess
    import sys as _sys
    import pathlib as _pathlib

    utm_epsg = utm_epsg_for_bbox(bbox)

    payload = _json.dumps({
        "temp_dem_path": temp_dem_path,
        "pour_lon":      pour_point.lon,
        "pour_lat":      pour_point.lat,
        "elev_grid":     elev_grid.tolist(),
        "utm_epsg":      utm_epsg,
        # Pass pre-computed flow direction so the worker skips the
        # expensive fill_pits/fill_depressions/resolve_flats/flowdir steps.
        "fdir_arr":      flow_direction_arr.tolist(),
    })

    worker_path = str(_pathlib.Path(__file__).with_name("_delineate_worker.py"))

    proc = subprocess.run(
        [_sys.executable, worker_path],
        input=payload,
        capture_output=True,
        text=True,
        timeout=300,  # 5 min — generous for slow lab machines
    )

    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(
            f"Delineation worker crashed (exit {proc.returncode}). "
            f"stderr: {proc.stderr[:500]}"
        )

    try:
        result = _json.loads(proc.stdout.strip())
    except Exception as exc:
        raise RuntimeError(
            f"Delineation worker returned invalid JSON. "
            f"stdout: {proc.stdout[:300]} stderr: {proc.stderr[:300]}"
        ) from exc

    if not result.get("ok"):
        raise ValueError(result.get("error", "Delineation worker failed."))

    catchment_geojson = {
        "type": "Feature",
        "geometry": result["polygon"],
        "properties": {
            "area_sq_km":      round(result["area_sq_km"], 4),
            "area_sq_m":       round(result["area_sq_m"], 1),
            "avg_elevation_m": round(result["avg_elev"], 2),
            "cell_count":      result["cell_count"],
            "projection_used": f"EPSG:{utm_epsg}",
        },
    }

    return CatchmentResult(
        geojson=catchment_geojson,
        area_sq_m=result["area_sq_m"],
        area_sq_km=result["area_sq_km"],
        avg_elevation_m=result["avg_elev"],
        cell_count=result["cell_count"],
        centroid_lon=result["centroid_lon"],
        centroid_lat=result["centroid_lat"],
        projection_epsg=utm_epsg,
        pour_point=pour_point,
    )
