"""
Catchment delineator.

Algorithm
---------
1. Snap the pond candidate location to the nearest high-accumulation cell
   within a search radius (pour-point determination).

2. Trace all upstream cells using a pure-numpy D8 BFS (breadth-first
   search). Each cell is checked: does it point (via its D8 direction
   code) into a cell already in the catchment? If yes, it is added.
   This replaces the previous subprocess-based pysheds grid.catchment()
   call which timed out on Python 3.14 / conda lab machines.

3. Build a GeoJSON Polygon by unioning the bounding boxes of all
   catchment cells using Shapely.

4. Compute catchment area using pyproj UTM projection.

5. Compute catchment statistics (average elevation, cell count, centroid).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np
from shapely.geometry import box as shapely_box, mapping
from shapely.ops import transform, unary_union

from app.geo.utils import BBox, coords_to_grid_index, grid_index_to_coords, haversine_m, utm_epsg_for_bbox

try:
    from pyproj import CRS, Transformer
    _PYPROJ_AVAILABLE = True
except ImportError:
    _PYPROJ_AVAILABLE = False


# D8 direction code → (Δrow, Δcol) of the cell it flows INTO
# pysheds encoding: E=1, SE=2, S=4, SW=8, W=16, NW=32, N=64, NE=128
_D8_OFFSETS: dict[int, tuple[int, int]] = {
    1:   ( 0, +1),   # East
    2:   (+1, +1),   # South-East
    4:   (+1,  0),   # South
    8:   (+1, -1),   # South-West
    16:  ( 0, -1),   # West
    32:  (-1, -1),   # North-West
    64:  (-1,  0),   # North
    128: (-1, +1),   # North-East
}


# ── Output dataclasses ────────────────────────────────────────────────────────

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

    Parameters
    ----------
    candidate_lon, candidate_lat : float
    flow_accumulation : np.ndarray (rows, cols)
    drainage_mask : np.ndarray (bool)
    bbox : BBox
    snap_radius_cells : int

    Returns
    -------
    PourPointResult
    """
    rows, cols = flow_accumulation.shape
    cand_row, cand_col = coords_to_grid_index(candidate_lon, candidate_lat, bbox, (rows, cols))

    r_lo = max(0, cand_row - snap_radius_cells)
    r_hi = min(rows - 1, cand_row + snap_radius_cells)
    c_lo = max(0, cand_col - snap_radius_cells)
    c_hi = min(cols - 1, cand_col + snap_radius_cells)

    window_acc   = flow_accumulation[r_lo:r_hi+1, c_lo:c_hi+1].copy()
    window_drain = drainage_mask[r_lo:r_hi+1, c_lo:c_hi+1]

    search_acc = window_acc * window_drain.astype(float) if window_drain.any() else window_acc

    flat_idx         = int(np.argmax(search_acc))
    win_row, win_col = np.unravel_index(flat_idx, search_acc.shape)
    snap_row         = r_lo + win_row
    snap_col         = c_lo + win_col

    snap_lon, snap_lat = grid_index_to_coords(snap_row, snap_col, bbox, (rows, cols))
    snap_dist_m        = haversine_m(candidate_lon, candidate_lat, snap_lon, snap_lat)

    return PourPointResult(
        lon=snap_lon,
        lat=snap_lat,
        row=int(snap_row),
        col=int(snap_col),
        snap_distance_m=snap_dist_m,
        flow_accumulation=float(flow_accumulation[snap_row, snap_col]),
    )


def delineate_catchment(
    pysheds_grid,              # kept for API compatibility — NOT used
    flow_direction_arr: np.ndarray,
    pour_point: PourPointResult,
    elev_grid: np.ndarray,
    bbox: BBox,
    temp_dem_path: str,        # kept for API compatibility — NOT used
) -> CatchmentResult:
    """
    Delineate the catchment upstream of the pour point using a
    pure-numpy D8 breadth-first search.

    This replaces the former subprocess-based pysheds grid.catchment()
    call. That approach timed out on Python 3.14 / conda environments
    because pysheds re-ran the full fill/flowdir pipeline inside the
    child process. The BFS here completes in milliseconds for a 100×100
    grid and requires no subprocesses.

    Parameters
    ----------
    pysheds_grid : ignored (kept for call-site compatibility)
    flow_direction_arr : np.ndarray
        D8 flow direction grid (pysheds int encoding).
    pour_point : PourPointResult
    elev_grid : np.ndarray (rows, cols)
    bbox : BBox
    temp_dem_path : ignored

    Returns
    -------
    CatchmentResult
    """
    rows, cols = flow_direction_arr.shape
    pr, pc     = pour_point.row, pour_point.col

    # ── BFS upstream trace ────────────────────────────────────────────────────
    # For each visited cell (r, c), look at all 8 neighbours.
    # Neighbour at (r - dr, c - dc) with direction code d flows INTO (r, c).
    catch_mask = np.zeros((rows, cols), dtype=bool)
    if 0 <= pr < rows and 0 <= pc < cols:
        catch_mask[pr, pc] = True

    queue = deque([(pr, pc)])
    while queue:
        r, c = queue.popleft()
        for d, (dr, dc) in _D8_OFFSETS.items():
            nr, nc = r - dr, c - dc          # neighbour that would flow INTO (r,c)
            if (0 <= nr < rows and 0 <= nc < cols
                    and not catch_mask[nr, nc]
                    and flow_direction_arr[nr, nc] == d):
                catch_mask[nr, nc] = True
                queue.append((nr, nc))

    cell_count = int(catch_mask.sum())

    # ── Build polygon from cell bounding boxes ────────────────────────────────
    lon_cell = (bbox.east  - bbox.west)  / cols
    lat_cell = (bbox.north - bbox.south) / rows

    rs, cs = np.where(catch_mask)
    polys = [
        shapely_box(
            bbox.west  + c_i * lon_cell,           # minx
            bbox.north - (r_i + 1) * lat_cell,     # miny
            bbox.west  + (c_i + 1) * lon_cell,     # maxx
            bbox.north - r_i * lat_cell,            # maxy
        )
        for r_i, c_i in zip(rs, cs)
    ]

    if polys:
        merged = unary_union(polys)
    else:
        # Degenerate: single-cell catchment at pour point
        merged = shapely_box(
            bbox.west  + pc * lon_cell,
            bbox.north - (pr + 1) * lat_cell,
            bbox.west  + (pc + 1) * lon_cell,
            bbox.north - pr * lat_cell,
        )

    # ── Area in m² via UTM projection ─────────────────────────────────────────
    utm_epsg = utm_epsg_for_bbox(bbox)
    if _PYPROJ_AVAILABLE:
        wgs84 = CRS.from_epsg(4326)
        utm   = CRS.from_epsg(utm_epsg)
        tf    = Transformer.from_crs(wgs84, utm, always_xy=True)
        projected = transform(tf.transform, merged)
        area_sq_m = projected.area
    else:
        # Fallback: approximate from cell count × cell area
        mid_lat   = (bbox.north + bbox.south) / 2.0
        lon_m     = lon_cell * 111_320.0 * np.cos(np.radians(mid_lat))
        lat_m     = lat_cell * 110_574.0
        area_sq_m = cell_count * lon_m * lat_m

    area_sq_km = area_sq_m / 1_000_000.0

    # ── Elevation stats ───────────────────────────────────────────────────────
    catch_elevs = elev_grid[catch_mask]
    avg_elev    = float(np.mean(catch_elevs)) if len(catch_elevs) > 0 else 0.0
    centroid    = merged.centroid

    catchment_geojson = {
        "type": "Feature",
        "geometry": mapping(merged),
        "properties": {
            "area_sq_km":      round(area_sq_km, 4),
            "area_sq_m":       round(area_sq_m, 1),
            "avg_elevation_m": round(avg_elev, 2),
            "cell_count":      cell_count,
            "projection_used": f"EPSG:{utm_epsg}",
        },
    }

    return CatchmentResult(
        geojson=catchment_geojson,
        area_sq_m=area_sq_m,
        area_sq_km=area_sq_km,
        avg_elevation_m=avg_elev,
        cell_count=cell_count,
        centroid_lon=float(centroid.x),
        centroid_lat=float(centroid.y),
        projection_epsg=utm_epsg,
        pour_point=pour_point,
    )



