"""
Area analysis service — fetch SRTM elevation for a bounding box and run
the full pond-site analysis pipeline.

This bypasses the KML parser entirely. It fetches real SRTM 30m elevation
data from the Open-Elevation API (free, no API key required), builds an
ElevationGrid from the returned grid, then runs the same hydrology +
candidate selection pipeline as the KML-based workflow.

Fallback: If the Open-Elevation API is unreachable, falls back to the
Open-Meteo elevation API (also free, no key). If both fail, raises a
clear error.
"""

from __future__ import annotations

import asyncio
import math
import tempfile
from typing import Optional

import httpx
import numpy as np

from app.geo.terrain_builder import ElevationGrid
from app.geo.terrain_conditioner import compute_slope
from app.geo.hydrology_engine import run_hydrology
from app.geo.pond_candidate_selector import select_top_candidates, DEFAULT_WEIGHTS
from app.geo.catchment_delineator import snap_to_pour_point, delineate_catchment
from app.geo.osm_water_fetcher import fetch_osm_water_mask, OSMWaterResult
from app.geo.terrain_water_detector import detect_terrain_water
from app.geo.utils import BBox, approx_cell_size_m
from app.geo.water_volume import estimate_water_volume


# ── Constants ──────────────────────────────────────────────────────────────────

# Open-Elevation public API (no key needed, SRTM data)
_OPEN_ELEV_URL = "https://api.open-elevation.com/api/v1/lookup"

# Maximum bounding box in degrees (to prevent runaway requests)
_MAX_BBOX_DEGREES = 1.0   # ~100 km × 100 km max

# Grid resolution for area-based analysis
_GRID_ROWS = 80
_GRID_COLS = 80


# ── Public API ─────────────────────────────────────────────────────────────────

async def analyze_area(
    west: float,
    south: float,
    east: float,
    north: float,
    grid_rows: int = _GRID_ROWS,
    grid_cols: int = _GRID_COLS,
    drainage_threshold_pct: float = 2.0,
    drainage_buffer_cells: int = 2,
    snap_radius_cells: int = 5,
    skip_osm: bool = False,
) -> dict:
    """
    Fetch elevation for the given bbox and run the pond-site analysis pipeline.

    Parameters
    ----------
    west, south, east, north : float
        Bounding box in WGS84 degrees.
    grid_rows, grid_cols : int
        Resolution of the elevation grid to build.

    Returns
    -------
    dict  — same structure as analyze_contour result dict
    """
    # Validate bbox
    if east <= west or north <= south:
        raise ValueError("Invalid bounding box: east > west and north > south required.")
    lon_span = east - west
    lat_span = north - south
    if lon_span > _MAX_BBOX_DEGREES or lat_span > _MAX_BBOX_DEGREES:
        raise ValueError(
            f"Selected area is too large ({lon_span:.2f}° × {lat_span:.2f}°). "
            f"Please select an area smaller than {_MAX_BBOX_DEGREES}° × {_MAX_BBOX_DEGREES}° "
            f"(~{int(_MAX_BBOX_DEGREES * 111)} km × {int(_MAX_BBOX_DEGREES * 111)} km)."
        )
    if lon_span < 0.005 or lat_span < 0.005:
        raise ValueError(
            "Selected area is too small. Please draw a larger rectangle "
            "(at least ~500m × 500m)."
        )

    bbox = BBox(west=west, east=east, south=south, north=north)

    # Fetch elevation grid
    elev_data = await _fetch_elevation_grid(bbox, grid_rows, grid_cols)

    with tempfile.TemporaryDirectory(prefix="pond_area_") as tmp_dir:
        return await _run_area_pipeline(
            elev_data=elev_data,
            bbox=bbox,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            drainage_threshold_pct=drainage_threshold_pct,
            drainage_buffer_cells=drainage_buffer_cells,
            snap_radius_cells=snap_radius_cells,
            skip_osm=skip_osm,
            tmp_dir=tmp_dir,
        )


# ── Elevation fetching ─────────────────────────────────────────────────────────

async def _fetch_elevation_grid(
    bbox: BBox,
    rows: int,
    cols: int,
) -> np.ndarray:
    """
    Fetch SRTM elevation for a regular grid of (rows × cols) points covering bbox.

    Returns
    -------
    np.ndarray of shape (rows, cols), dtype float64
        Elevation in metres. Row 0 = northernmost, col 0 = westernmost.
    """
    # Build grid of (lat, lon) sample points — row-major, north to south
    lats = np.linspace(bbox.north, bbox.south, rows)   # north → south
    lons = np.linspace(bbox.west,  bbox.east,  cols)   # west  → east
    grid_lons, grid_lats = np.meshgrid(lons, lats)     # shape (rows, cols)

    flat_lats = grid_lats.ravel().tolist()
    flat_lons = grid_lons.ravel().tolist()

    elevations = await _query_open_elevation(flat_lats, flat_lons)
    return np.array(elevations, dtype=np.float64).reshape(rows, cols)


async def _query_open_elevation(lats: list, lons: list) -> list:
    """
    Query Open-Elevation API in batches of 500 points.
    Falls back to Open-Meteo if unreachable.
    """
    points = [{"latitude": lat, "longitude": lon} for lat, lon in zip(lats, lons)]
    batch_size = 500
    results = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            try:
                resp = await client.post(
                    _OPEN_ELEV_URL,
                    json={"locations": batch},
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                results.extend(r["elevation"] for r in data["results"])
            except Exception as e:
                # Fallback: Open-Meteo elevation endpoint
                try:
                    elev = await _query_open_meteo_batch(
                        client,
                        [p["latitude"] for p in batch],
                        [p["longitude"] for p in batch],
                    )
                    results.extend(elev)
                except Exception as e2:
                    raise RuntimeError(
                        f"Could not fetch elevation data. "
                        f"Open-Elevation error: {e}. "
                        f"Open-Meteo fallback error: {e2}. "
                        f"Please check your network connection and try again, "
                        f"or use the KML upload method instead."
                    )
    return results


async def _query_open_meteo_batch(
    client: httpx.AsyncClient,
    lats: list,
    lons: list,
) -> list:
    """
    Use Open-Meteo elevation API as fallback.
    Handles up to 100 points per request.
    """
    results = []
    chunk = 100
    for i in range(0, len(lats), chunk):
        lat_str = ",".join(f"{v:.6f}" for v in lats[i:i+chunk])
        lon_str = ",".join(f"{v:.6f}" for v in lons[i:i+chunk])
        resp = await client.get(
            "https://api.open-meteo.com/v1/elevation",
            params={"latitude": lat_str, "longitude": lon_str},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["elevation"])
    return results


# ── Pipeline ───────────────────────────────────────────────────────────────────

async def _run_area_pipeline(
    elev_data: np.ndarray,
    bbox: BBox,
    grid_rows: int,
    grid_cols: int,
    drainage_threshold_pct: float,
    drainage_buffer_cells: int,
    snap_radius_cells: int,
    skip_osm: bool,
    tmp_dir: str,
) -> dict:
    """Run the terrain/hydrology pipeline on a pre-built elevation grid."""
    from app.geo.terrain_builder import ElevationGrid

    # Build ElevationGrid from fetched data
    elev_grid_obj = ElevationGrid(
        data=elev_data,
        bbox=bbox,
        rows=grid_rows,
        cols=grid_cols,
        nan_fraction=0.0,
        interpolation_method="srtm_open_elevation",
    )
    elev_grid = elev_grid_obj.data

    # Compute slope
    slope_grid_obj = compute_slope(elev_grid, bbox)
    slope_grid = slope_grid_obj.data

    # Hydrology
    hydro = run_hydrology(
        elev_grid=elev_grid,
        bbox=bbox,
        drainage_threshold_pct=drainage_threshold_pct,
        drainage_buffer_cells=drainage_buffer_cells,
        tmp_dir=tmp_dir,
    )

    # Terrain water detection
    terrain_water = detect_terrain_water(
        elev_grid=elev_grid,
        slope_grid=slope_grid,
        flow_accumulation=hydro.flow_accumulation,
        low_elev_pct=15.0,
        river_acc_pct=98.0,
        river_buffer_cells=8,
        flat_slope_threshold=1.0,
        buffer_cells=3,
        max_coverage_pct=65.0,
    )

    # OSM water exclusion
    osm_result: OSMWaterResult = fetch_osm_water_mask(
        bbox=bbox,
        grid_shape=elev_grid.shape,
        buffer_cells=drainage_buffer_cells,
        skip_osm=skip_osm,
    )

    # Combined exclusion mask
    combined_exclusion_mask = hydro.exclusion_mask.copy()
    combined_exclusion_mask = combined_exclusion_mask | terrain_water.water_mask
    if osm_result.found and osm_result.water_mask is not None:
        combined_exclusion_mask = combined_exclusion_mask | osm_result.water_mask

    # Select candidates
    candidates = select_top_candidates(
        elev_grid=elev_grid,
        slope_grid=slope_grid,
        flow_accumulation=hydro.flow_accumulation,
        drainage_mask=hydro.drainage_mask,
        exclusion_mask=combined_exclusion_mask,
        bbox=bbox,
        weights=DEFAULT_WEIGHTS,
        n_candidates=3,
        min_separation_cells=15,
    )

    # Catchment delineation for each candidate
    candidate_results = []
    for rank, cand in enumerate(candidates):
        try:
            pp = snap_to_pour_point(
                candidate_lon=cand.lon,
                candidate_lat=cand.lat,
                flow_accumulation=hydro.flow_accumulation,
                drainage_mask=hydro.drainage_mask,
                bbox=bbox,
                snap_radius_cells=snap_radius_cells,
            )
            cat = delineate_catchment(
                pysheds_grid=hydro.pysheds_grid,
                flow_direction_arr=hydro.flow_direction,
                pour_point=pp,
                elev_grid=elev_grid,
                bbox=bbox,
                temp_dem_path=hydro.temp_dem_path,
            )
            candidate_results.append((rank, cand, pp, cat))
        except Exception:
            if rank == 0:
                raise
            continue

    _, candidate, pour_point, catchment = candidate_results[0]
    lon_cell_m, lat_cell_m = approx_cell_size_m(bbox, elev_grid_obj.shape)

    # ── Build input_boundary GeoJSON (the drawn bbox as a polygon) ──────────────
    input_boundary_geojson = _bbox_to_polygon(bbox)

    # ── Build all_candidates list ──────────────────────────────────────────────
    all_candidates_full = []
    for rank, cand, pp, cat in candidate_results:
        # cat is a CatchmentResult dataclass — access attributes directly
        all_candidates_full.append({
            "rank":              rank,
            "longitude":         cand.lon,
            "latitude":          cand.lat,
            "elevation_m":       cand.elevation_m,
            "suitability_score": cand.suitability_score,
            "pour_point": {
                "longitude": pp.lon,
                "latitude":  pp.lat,
            },
            "catchment": {
                "area_km2":        cat.area_sq_km,
                "area_m2":         cat.area_sq_m,
                "avg_elevation_m": cat.avg_elevation_m,
                "boundary_geojson": cat.geojson.get("geometry"),
            },
        })

    # Best candidate
    best_c = all_candidates_full[0]

    return {
        "status": "success",
        "input_source": "area",
        "input_boundary": input_boundary_geojson,
        # Rank-1 summary (backward compat)
        "pond_location": {
            "longitude":         best_c["longitude"],
            "latitude":          best_c["latitude"],
            "elevation_m":       best_c["elevation_m"],
            "suitability_score": best_c["suitability_score"],
        },
        "pour_point": {
            "longitude": best_c["pour_point"]["longitude"],
            "latitude":  best_c["pour_point"]["latitude"],
        },
        "catchment": {
            "area_km2":        best_c["catchment"]["area_km2"],
            "area_m2":         best_c["catchment"]["area_m2"],
            "avg_elevation_m": best_c["catchment"]["avg_elevation_m"],
            "boundary_geojson": best_c["catchment"]["boundary_geojson"],
        },
        "all_candidates": all_candidates_full,
        "osm_water_exclusion": {
            "water_bodies_found": osm_result.found,
            "water_body_count":   osm_result.feature_count if osm_result.found else 0,
            "water_body_names":   osm_result.feature_names if osm_result.found else [],
        },
        "water_volume": estimate_water_volume(catchment.area_sq_m),
    }


def _bbox_to_polygon(bbox: BBox) -> dict:
    """Convert a BBox to a GeoJSON Polygon (closed ring)."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [bbox.west,  bbox.south],
            [bbox.east,  bbox.south],
            [bbox.east,  bbox.north],
            [bbox.west,  bbox.north],
            [bbox.west,  bbox.south],   # close ring
        ]],
    }
