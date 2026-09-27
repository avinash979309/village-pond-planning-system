"""
Area analysis service — read local SRTM HGT tile for a bounding box and run
the full pond-site analysis pipeline.

Elevation source: SRTM 1-arcsec HGT tiles bundled in backend/app/data/srtm/.
No internet required. Tile coverage matches the lab area (IIT Bhilai,
Chhattisgarh, India).

HGT format: raw big-endian int16, 3601x3601 samples for 1x1 degree tile,
row-major, north to south, west to east.
"""

from __future__ import annotations

import os
import struct
import tempfile
from pathlib import Path

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

# Directory containing .hgt files
_SRTM_DIR = Path(__file__).parent.parent / "data" / "srtm"

# Grid resolution — 50x50 keeps memory well under 512MB cgroup limit
# (80x80 was triggering OOM kills on the lab server)
_GRID_ROWS = 50
_GRID_COLS = 50

# Max bbox size in degrees (~100 km per side)
_MAX_BBOX_DEG = 1.0


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
    Fetch SRTM elevation for the given bbox from local HGT tiles and run
    the full pond-site analysis pipeline.
    """
    # Validate
    if east <= west or north <= south:
        raise ValueError("Invalid bbox: east > west and north > south required.")
    lon_span = east - west
    lat_span = north - south
    if lon_span > _MAX_BBOX_DEG or lat_span > _MAX_BBOX_DEG:
        raise ValueError(
            f"Area too large ({lon_span:.2f}° × {lat_span:.2f}°). "
            f"Select area smaller than {_MAX_BBOX_DEG}° × {_MAX_BBOX_DEG}° "
            f"(~{int(_MAX_BBOX_DEG * 111)} km per side)."
        )
    if lon_span < 0.005 or lat_span < 0.005:
        raise ValueError(
            "Area too small. Draw a larger rectangle (at least ~500 m × 500 m)."
        )

    bbox = BBox(west=west, east=east, south=south, north=north)
    elev_data = _extract_elevation_grid(bbox, grid_rows, grid_cols)

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


# ── SRTM HGT reader ───────────────────────────────────────────────────────────

def _hgt_tile_name(lat_floor: int, lon_floor: int) -> str:
    """Return HGT filename for integer tile origin, e.g. N21E081.hgt"""
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"{ns}{abs(lat_floor):02d}{ew}{abs(lon_floor):03d}.hgt"


def _load_hgt_tile(lat_floor: int, lon_floor: int) -> np.ndarray:
    """
    Load SRTM HGT tile as int16 array (3601, 3601).
    Kept as int16 in cache (25MB) not float32 (52MB) to stay under 512MB cgroup.
    """
    name = _hgt_tile_name(lat_floor, lon_floor)
    path = _SRTM_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"SRTM tile {name} not found. "
            f"Available: {[f.name for f in _SRTM_DIR.glob('*.hgt')]}. "
            f"Select an area near IIT Bhilai / Chhattisgarh."
        )
    raw = np.frombuffer(path.read_bytes(), dtype=">i2")
    return raw.reshape(3601, 3601)  # int16, no float conversion yet


# Module-level tile cache — 25MB int16 per tile, not 52MB float32
_tile_cache: dict = {}

def _load_hgt_tile_cached(lat_floor: int, lon_floor: int) -> np.ndarray:
    key = (lat_floor, lon_floor)
    if key not in _tile_cache:
        _tile_cache[key] = _load_hgt_tile(lat_floor, lon_floor)
    return _tile_cache[key]



def _extract_elevation_grid(bbox: BBox, rows: int, cols: int) -> np.ndarray:
    """
    Vectorized SRTM extraction — no Python loops over grid points.
    Samples a (rows × cols) grid from HGT tiles using numpy bilinear interp.
    """
    lat_min_tile = int(np.floor(bbox.south))
    lat_max_tile = int(np.floor(bbox.north))
    lon_min_tile = int(np.floor(bbox.west))
    lon_max_tile = int(np.floor(bbox.east))

    # Sample grid coords (north→south rows, west→east cols)
    sample_lats = np.linspace(bbox.north, bbox.south, rows)
    sample_lons = np.linspace(bbox.west,  bbox.east,  cols)

    # 2D meshgrid of all sample points
    lon_grid, lat_grid = np.meshgrid(sample_lons, sample_lats)  # (rows, cols) each

    result = np.full((rows, cols), np.nan, dtype=np.float32)

    for lat_tile in range(lat_min_tile, lat_max_tile + 1):
        for lon_tile in range(lon_min_tile, lon_max_tile + 1):
            tile = _load_hgt_tile_cached(lat_tile, lon_tile)

            tile_north = float(lat_tile + 1)
            tile_south = float(lat_tile)
            tile_west  = float(lon_tile)

            # Boolean mask — which grid points fall in this tile
            in_tile = (
                (lat_grid >= tile_south) & (lat_grid <= tile_north) &
                (lon_grid >= tile_west)  & (lon_grid <= tile_west + 1.0)
            )
            if not in_tile.any():
                continue

            pr = (tile_north - lat_grid[in_tile]) * 3600.0
            pc = (lon_grid[in_tile] - tile_west) * 3600.0

            pr0 = np.clip(np.floor(pr).astype(np.int32), 0, 3599)
            pr1 = np.minimum(pr0 + 1, 3600)
            pc0 = np.clip(np.floor(pc).astype(np.int32), 0, 3599)
            pc1 = np.minimum(pc0 + 1, 3600)

            wr1 = (pr - pr0).astype(np.float32)
            wr0 = np.float32(1.0) - wr1
            wc1 = (pc - pc0).astype(np.float32)
            wc0 = np.float32(1.0) - wc1

            # Convert only the 4 corner values to float32 (not the whole tile)
            v00 = tile[pr0, pc0].astype(np.float32)
            v01 = tile[pr0, pc1].astype(np.float32)
            v10 = tile[pr1, pc0].astype(np.float32)
            v11 = tile[pr1, pc1].astype(np.float32)

            # Mask SRTM void value (-32768)
            void = (v00 == -32768) | (v01 == -32768) | (v10 == -32768) | (v11 == -32768)
            vals = wr0 * wc0 * v00 + wr0 * wc1 * v01 + wr1 * wc0 * v10 + wr1 * wc1 * v11
            vals[void] = np.nan

            result[in_tile] = vals

    nan_mask = np.isnan(result)
    if nan_mask.any() and not nan_mask.all():
        from scipy.ndimage import distance_transform_edt
        idx = distance_transform_edt(nan_mask, return_distances=False, return_indices=True)
        result[nan_mask] = result[tuple(idx[:, nan_mask])]

    return result



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
    """Run terrain/hydrology pipeline on pre-built elevation grid."""
    elev_grid_obj = ElevationGrid(
        data=elev_data,
        bbox=bbox,
        rows=grid_rows,
        cols=grid_cols,
        nan_fraction=0.0,
        interpolation_method="srtm_hgt_local",
    )
    elev_grid = elev_grid_obj.data

    slope_grid_obj = compute_slope(elev_grid, bbox)
    slope_grid = slope_grid_obj.data

    hydro = run_hydrology(
        elev_grid=elev_grid,
        bbox=bbox,
        drainage_threshold_pct=drainage_threshold_pct,
        drainage_buffer_cells=drainage_buffer_cells,
        tmp_dir=tmp_dir,
    )

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

    osm_result: OSMWaterResult = fetch_osm_water_mask(
        bbox=bbox,
        grid_shape=elev_grid.shape,
        buffer_cells=drainage_buffer_cells,
        skip_osm=skip_osm,
    )

    combined_exclusion_mask = hydro.exclusion_mask.copy()
    combined_exclusion_mask |= terrain_water.water_mask
    if osm_result.found and osm_result.water_mask is not None:
        combined_exclusion_mask |= osm_result.water_mask

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

    input_boundary_geojson = {
        "type": "Polygon",
        "coordinates": [[
            [bbox.west,  bbox.south],
            [bbox.east,  bbox.south],
            [bbox.east,  bbox.north],
            [bbox.west,  bbox.north],
            [bbox.west,  bbox.south],
        ]],
    }

    all_candidates_full = []
    for rank, cand, pp, cat in candidate_results:
        all_candidates_full.append({
            "rank":              rank,
            "longitude":         cand.lon,
            "latitude":          cand.lat,
            "elevation_m":       cand.elevation_m,
            "suitability_score": cand.suitability_score,
            "slope_degrees":     cand.slope_degrees,
            "flow_accumulation": cand.flow_accumulation,
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

    best_c = all_candidates_full[0]

    return {
        "status": "success",
        "input_source": "area",
        "input_boundary": input_boundary_geojson,
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
