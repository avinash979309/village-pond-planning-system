"""
Contour analysis service — orchestration layer.

Responsibilities
----------------
- Accept raw uploaded file bytes and parameters.
- Call geo modules in the correct order.
- Manage temporary files (create in temp dir, always clean up).
- Translate geo-module outputs into the structured dict consumed by the API route.
- Raise informative errors that the route can convert to HTTP responses.

This module contains NO geospatial algorithm logic.
All computation is delegated to geo/ modules.

Pipeline sequence
-----------------
parse_upload()                 ← kml_parser
    ↓
detect_water_features()        ← water_feature_detector
    ↓
build_elevation_grid()         ← terrain_builder
    ↓
compute_slope()                ← terrain_conditioner
    ↓
run_hydrology()                ← hydrology_engine
    (fills sinks, D8, flow accum, drainage mask)
    ↓
select_pond_candidate()        ← pond_candidate_selector
    ↓
snap_to_pour_point()           ← catchment_delineator
    ↓
delineate_catchment()          ← catchment_delineator
    ↓
assemble result dict           ← (this module)
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.parse
from typing import Optional

import numpy as np

from app.geo.kml_parser import parse_upload
from app.geo.water_feature_detector import detect_water_features, WaterFeatureResult
from app.geo.osm_water_fetcher import fetch_osm_water_mask, OSMWaterResult
from app.geo.terrain_water_detector import detect_terrain_water, TerrainWaterResult
from app.geo.terrain_builder import build_elevation_grid
from app.geo.terrain_conditioner import compute_slope
from app.geo.hydrology_engine import run_hydrology
from app.geo.pond_candidate_selector import select_pond_candidate, select_top_candidates, DEFAULT_WEIGHTS
from app.geo.catchment_delineator import snap_to_pour_point, delineate_catchment
from app.geo.utils import approx_cell_size_m


async def analyze_contour(
    file_bytes: bytes,
    filename: str,
    grid_resolution: int = 200,
    drainage_threshold_pct: float = 2.0,
    drainage_buffer_cells: int = 2,
    snap_radius_cells: int = 5,
    skip_osm: bool = False,
) -> dict:
    """
    Run the full contour analysis pipeline and return a structured result dict.

    Parameters
    ----------
    file_bytes : bytes
        Raw uploaded file content.
    filename : str
        Original filename (used only to determine KML vs KMZ format).
    grid_resolution : int
        Grid cells per axis for elevation interpolation.
    drainage_threshold_pct : float
        Top N% of flow accumulation cells treated as drainage channels.
    drainage_buffer_cells : int
        Exclusion buffer in grid cells around drainage channels.
    snap_radius_cells : int
        Pour-point snap search radius in grid cells.

    Returns
    -------
    dict matching ContourAnalysisData schema

    Raises
    ------
    ValueError
        For invalid input or processing failures (caller converts to HTTP 400/422).
    RuntimeError
        For internal processing errors (caller converts to HTTP 500).
    """
    # Use a single temp directory for all temporary files in this request
    with tempfile.TemporaryDirectory(prefix="pond_analysis_") as tmp_dir:
        return await _run_pipeline(
            file_bytes=file_bytes,
            filename=filename,
            grid_resolution=grid_resolution,
            drainage_threshold_pct=drainage_threshold_pct,
            drainage_buffer_cells=drainage_buffer_cells,
            snap_radius_cells=snap_radius_cells,
            skip_osm=skip_osm,
            tmp_dir=tmp_dir,
        )


async def _run_pipeline(
    file_bytes: bytes,
    filename: str,
    grid_resolution: int,
    drainage_threshold_pct: float,
    drainage_buffer_cells: int,
    snap_radius_cells: int,
    skip_osm: bool,
    tmp_dir: str,
) -> dict:
    """Internal pipeline — runs inside a temp directory context."""

    # ── 1. Parse KML / KMZ ───────────────────────────────────────────────────
    parsed = parse_upload(file_bytes, filename)
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "kml"

    # ── 2. Detect explicit water features ────────────────────────────────────
    water_result: WaterFeatureResult = detect_water_features(parsed.other_features)

    # ── 3. Build elevation grid ───────────────────────────────────────────────
    elev_grid_obj = build_elevation_grid(
        contour_lines=parsed.contour_lines,
        bbox=parsed.bbox,
        grid_resolution=grid_resolution,
        max_points_per_contour=50,
    )
    elev_grid = elev_grid_obj.data
    bbox = parsed.bbox

    # ── 4. Compute slope ──────────────────────────────────────────────────────
    slope_grid_obj = compute_slope(elev_grid, bbox)
    slope_grid = slope_grid_obj.data

    # ── 5. Hydrology (sink fill, D8, flow accumulation, drainage) ─────────────
    hydro = run_hydrology(
        elev_grid=elev_grid,
        bbox=bbox,
        drainage_threshold_pct=drainage_threshold_pct,
        drainage_buffer_cells=drainage_buffer_cells,
        tmp_dir=tmp_dir,
    )

    # ── 5b. Terrain-based water / floodplain exclusion ────────────────────────
    # Detects river beds, floodplains, and flat valley floors purely from the
    # DEM — no network access needed. This is ALWAYS applied, regardless of
    # whether OSM is available.
    #
    # The algorithm identifies three terrain zones as water-excluded:
    # 1. Absolute low-elevation cells (bottom 15% of elevation range)
    # 2. High-flow-accumulation corridors (top 2%, buffer 8 cells)
    # 3. Flat low cells (elev ≤ p20 AND slope ≤ 1°), i.e. floodplain
    #
    # This correctly handles rivers like Shivnath that create a wide flat
    # low-elevation band through the map even when OSM is unreachable.
    terrain_water: TerrainWaterResult = detect_terrain_water(
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

    # ── 5c. OSM water body exclusion ─────────────────────────────────────────
    # Additionally fetch real water bodies from OpenStreetMap when network
    # is available. This provides authoritative polygons for named rivers,
    # lakes, and reservoirs. When unreachable, terrain-based detection above
    # already handles the exclusion.
    osm_result: OSMWaterResult = fetch_osm_water_mask(
        bbox=bbox,
        grid_shape=elev_grid.shape,
        buffer_cells=drainage_buffer_cells,
        skip_osm=skip_osm,
    )

    # ── Build combined exclusion mask ────────────────────────────────────────
    # Merge: hydrology drainage exclusion + terrain water + OSM water
    combined_exclusion_mask = hydro.exclusion_mask.copy()
    combined_exclusion_mask = combined_exclusion_mask | terrain_water.water_mask
    if osm_result.found and osm_result.water_mask is not None:
        combined_exclusion_mask = combined_exclusion_mask | osm_result.water_mask

    # ── 6. Select top N pond candidates ──────────────────────────────────────
    # Returns up to 3 spatially-separated candidates using iterative spatial
    # suppression. Each candidate is at least 15 grid cells (~225m) apart.
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
    # Best candidate for backward-compatible single result fields
    candidate = candidates[0]

    # ── 7 & 8. Snap pour point + delineate catchment for each candidate ───────
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
            # If delineation fails for a secondary candidate, skip it
            if rank == 0:
                raise
            continue

    # Best result
    _, candidate, pour_point, catchment = candidate_results[0]

    # ── 9. Assemble response dict ─────────────────────────────────────────────
    lon_cell_m, lat_cell_m = approx_cell_size_m(bbox, elev_grid_obj.shape)

    drainage_method = "terrain_derived"
    drainage_note = (
        "Drainage network derived from D8 flow accumulation. "
        "This is terrain-derived and does NOT represent verified geographic "
        "river boundaries or legal water ownership data."
    )
    if water_result.found:
        drainage_method = "explicit_feature"
        drainage_note = (
            f"Explicit water features detected in KML "
            f"({len(water_result.features)} feature(s)). "
            "Exclusion zone applied from encoded water geometry."
        )

    # ── 10. Build multi-candidate colored GeoJSON ─────────────────────────────
    # Rank colors: #1=green, #2=orange, #3=purple. Pour points darker shade.
    # Catchments outlined in same hue. All use Mapbox SimpleStyle.
    _RANK_COLORS = ["#27AE60", "#E67E22", "#8E44AD"]   # green / orange / purple
    _POUR_COLORS = ["#1A7A43", "#B35A10", "#5E2C7B"]   # darker shades for pour pts

    multi_geojson_features = []
    top_candidates_list = []

    for rank, cand, pp, cat in candidate_results:
        rank_label = f"#{rank + 1}"
        color = _RANK_COLORS[min(rank, 2)]
        pour_color = _POUR_COLORS[min(rank, 2)]

        # Catchment polygon for this candidate
        multi_geojson_features.append({
            "type": "Feature",
            "geometry": cat.geojson["geometry"],
            "properties": {
                "title": f"Catchment {rank_label}",
                "rank": rank + 1,
                "area_sq_km": round(cat.area_sq_km, 4),
                "area_sq_m": round(cat.area_sq_m, 1),
                "avg_elevation_m": round(cat.avg_elevation_m, 2),
                "cell_count": cat.cell_count,
                "description": f"Catchment {rank_label} | Area: {round(cat.area_sq_km, 4)} km²",
                "stroke": color,
                "stroke-width": 2,
                "stroke-opacity": 0.9,
                "fill": color,
                "fill-opacity": 0.15,
            },
        })
        # Pond candidate point
        multi_geojson_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(cand.lon, 7), round(cand.lat, 7)]},
            "properties": {
                "title": f"Pond Candidate {rank_label}",
                "rank": rank + 1,
                "elevation_m": round(cand.elevation_m, 2),
                "slope_degrees": round(cand.slope_degrees, 3),
                "flow_accumulation": round(cand.flow_accumulation, 1),
                "suitability_score": round(cand.suitability_score, 4),
                "score_breakdown": {k: round(v, 4) for k, v in cand.score_breakdown.items()},
                "on_drainage_channel": cand.on_drainage_channel,
                "exclusion_zone_respected": cand.exclusion_zone_respected,
                "description": (
                    f"Rank {rank + 1} | Score: {round(cand.suitability_score, 4)} "
                    f"| Elev: {round(cand.elevation_m, 2)}m "
                    f"| Slope: {round(cand.slope_degrees, 3)}°"
                ),
                "marker-color": color,
                "marker-size": "large" if rank == 0 else "medium",
                "marker-symbol": "circle",
            },
        })
        # Pour point
        multi_geojson_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(pp.lon, 7), round(pp.lat, 7)]},
            "properties": {
                "title": f"Pour Point {rank_label}",
                "rank": rank + 1,
                "snap_distance_m": round(pp.snap_distance_m, 1),
                "flow_accumulation": round(pp.flow_accumulation, 1),
                "description": f"Pour Point {rank_label} | Flow acc: {round(pp.flow_accumulation, 1)}",
                "marker-color": pour_color,
                "marker-size": "small",
                "marker-symbol": "circle",
            },
        })

        top_candidates_list.append({
            "rank": rank + 1,
            "pond_candidate": {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(cand.lon, 7), round(cand.lat, 7)]},
                "properties": {
                    "rank": rank + 1,
                    "elevation_m": round(cand.elevation_m, 2),
                    "slope_degrees": round(cand.slope_degrees, 3),
                    "flow_accumulation": round(cand.flow_accumulation, 1),
                    "suitability_score": round(cand.suitability_score, 4),
                    "score_breakdown": {k: round(v, 4) for k, v in cand.score_breakdown.items()},
                    "on_drainage_channel": cand.on_drainage_channel,
                    "exclusion_zone_respected": cand.exclusion_zone_respected,
                    "osm_water_excluded": osm_result.found,
                },
            },
            "pour_point": {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(pp.lon, 7), round(pp.lat, 7)]},
                "properties": {
                    "snap_distance_m": round(pp.snap_distance_m, 1),
                    "flow_accumulation": round(pp.flow_accumulation, 1),
                },
            },
            "catchment": {
                "type": "Feature",
                "geometry": cat.geojson["geometry"],
                "properties": {
                    "area_sq_km": round(cat.area_sq_km, 4),
                    "area_sq_m": round(cat.area_sq_m, 1),
                    "avg_elevation_m": round(cat.avg_elevation_m, 2),
                    "cell_count": cat.cell_count,
                    "projection_used": f"EPSG:{cat.projection_epsg}",
                },
            },
            "color": color,
        })

    colored_geojson = {
        "type": "FeatureCollection",
        "legend": {
            "🟢 Green (#1)": "Best pond candidate + catchment",
            "🟠 Orange (#2)": "2nd candidate + catchment",
            "🟣 Purple (#3)": "3rd candidate + catchment",
            "Darker shade": "Pour point (catchment outlet) for each candidate",
        },
        "features": multi_geojson_features,
    }

    # Backward-compat single-candidate colored GeoJSON (rank #1 only)
    best_colored_geojson = _build_colored_geojson(
        catchment_geojson=catchment.geojson["geometry"],
        catchment_props={
            "area_sq_km": round(catchment.area_sq_km, 4),
            "area_sq_m": round(catchment.area_sq_m, 1),
            "avg_elevation_m": round(catchment.avg_elevation_m, 2),
            "cell_count": catchment.cell_count,
            "projection_used": f"EPSG:{catchment.projection_epsg}",
        },
        pond_coords=[round(candidate.lon, 7), round(candidate.lat, 7)],
        pond_props={
            "elevation_m": round(candidate.elevation_m, 2),
            "slope_degrees": round(candidate.slope_degrees, 3),
            "flow_accumulation": round(candidate.flow_accumulation, 1),
            "suitability_score": round(candidate.suitability_score, 4),
            "score_breakdown": {k: round(v, 4) for k, v in candidate.score_breakdown.items()},
            "on_drainage_channel": candidate.on_drainage_channel,
            "exclusion_zone_respected": candidate.exclusion_zone_respected,
            "osm_water_excluded": osm_result.found,
        },
        pour_coords=[round(pour_point.lon, 7), round(pour_point.lat, 7)],
        pour_props={
            "snap_distance_m": round(pour_point.snap_distance_m, 1),
            "flow_accumulation": round(pour_point.flow_accumulation, 1),
            "note": (
                "Pour point is the hydrological input for catchment delineation. "
                "Snapped to nearest high-accumulation drainage cell within search radius."
            ),
        },
    )

    # Build geojson.io visualization URL — uses all-candidates GeoJSON
    geojson_compact = json.dumps(colored_geojson, separators=(",", ":"))
    encoded = urllib.parse.quote(geojson_compact)
    visualize_url = f"https://geojson.io/#data=data:application/json,{encoded}"

    osm_water_info = {
        "osm_query_performed": not skip_osm,
        "water_bodies_found": osm_result.found,
        "water_body_count": osm_result.feature_count,
        "water_body_names": osm_result.feature_names,
        "source": osm_result.source,
    }
    if osm_result.warning:
        osm_water_info["warning"] = osm_result.warning

    return {
        "input_summary": {
            "filename": filename,
            "file_format": file_ext,
            "contour_line_count": len(parsed.contour_lines),
            "elevation_range_m": {
                "min_m": parsed.elevation_range[0],
                "max_m": parsed.elevation_range[1],
            },
            "spatial_extent": bbox.to_dict(),
            "contour_interval_m": parsed.contour_interval_m,
            "explicit_water_features_found": water_result.found,
            "explicit_water_feature_count": len(water_result.features),
        },
        "terrain": {
            "grid_resolution": grid_resolution,
            "grid_shape": list(elev_grid_obj.shape),
            "interpolation_method": elev_grid_obj.interpolation_method,
            "cell_size_approx_m": [round(lon_cell_m, 1), round(lat_cell_m, 1)],
            "elevation_stats": {
                k: round(v, 2) if v is not None else None
                for k, v in elev_grid_obj.elevation_stats().items()
            },
        },
        "drainage": {
            "method": drainage_method,
            "drainage_threshold_pct": drainage_threshold_pct,
            "drainage_cells_count": hydro.drainage_cell_count,
            "exclusion_buffer_cells": drainage_buffer_cells,
            "note": drainage_note,
        },
        "osm_water_exclusion": osm_water_info,
        "terrain_water_exclusion": {
            "applied": True,
            "coverage_pct": round(terrain_water.coverage_pct, 1),
            "description": terrain_water.description,
            "note": (
                "Terrain-based floodplain/river exclusion is always applied "
                "regardless of OSM availability. Detects river corridors via "
                "low elevation + high flow accumulation + flat slope signatures."
            ),
        },
        # ── Best candidate (rank #1) — kept for backward compatibility ─────────
        "pond_candidate": top_candidates_list[0]["pond_candidate"],
        "pour_point": top_candidates_list[0]["pour_point"],
        "catchment": top_candidates_list[0]["catchment"],
        # ── All top candidates ─────────────────────────────────────────────────
        "top_candidates": top_candidates_list,
        "colored_geojson": colored_geojson,
        "best_candidate_geojson": best_colored_geojson,
        "visualization_urls": {
            "geojson_io": visualize_url,
            "note": (
                "All candidates shown: green=#1 (best), orange=#2, purple=#3. "
                "Open in geojson.io to compare catchments visually and pick the "
                "most practical site. Use /download-geojson endpoint for file download."
            ),
        },
        "methodology": {
            "contour_interpolation": "scipy.griddata — linear triangulation + nearest-neighbour boundary fill",
            "flow_direction_algorithm": "D8 (deterministic 8-direction, pysheds)",
            "catchment_delineation": "pysheds upstream tracing from pour point",
            "area_calculation_projection": f"UTM EPSG:{catchment.projection_epsg} (projected, not lat/lon)",
            "drainage_derivation": drainage_method,
            "water_body_exclusion": "Terrain-based (always) + OSM Overpass API (when network available)",
            "candidate_scoring": "weighted multi-factor: elevation + slope + flow_accumulation + proximity_to_drainage",
            "multi_candidate_method": "iterative spatial suppression — circular exclusion zone per pick",
            "weights": DEFAULT_WEIGHTS,
        },
    }



# ── GeoJSON colour builder ────────────────────────────────────────────────────

def _build_colored_geojson(
    catchment_geojson: dict,
    catchment_props: dict,
    pond_coords: list,
    pond_props: dict,
    pour_coords: list,
    pour_props: dict,
) -> dict:
    """
    Build a styled GeoJSON FeatureCollection using the Mapbox SimpleStyle spec.

    Colours:
    - Catchment polygon : red (#E74C3C) fill, red stroke
    - Pond candidate    : green (#27AE60) marker
    - Pour point        : blue (#2980B9) marker

    geojson.io and most GeoJSON viewers honour these style properties natively.
    A 'legend' property on the FeatureCollection documents the colour scheme.
    """
    return {
        "type": "FeatureCollection",
        "legend": {
            "🟢 Green circle": "Pond Candidate — recommended pond construction site",
            "🔵 Blue circle": "Pour Point — hydrological outlet / catchment outlet",
            "🔴 Red polygon": "Catchment Boundary — all rainfall inside drains to pond",
        },
        "features": [
            # ── Catchment polygon (red) ────────────────────────────────────
            {
                "type": "Feature",
                "geometry": catchment_geojson,
                "properties": {
                    **catchment_props,
                    "title": "Catchment Boundary",
                    "description": (
                        f"Area: {catchment_props.get('area_sq_km', '?')} km² "
                        f"| Avg elevation: {catchment_props.get('avg_elevation_m', '?')} m"
                    ),
                    # Mapbox SimpleStyle polygon colours
                    "stroke": "#E74C3C",
                    "stroke-width": 2,
                    "stroke-opacity": 1,
                    "fill": "#E74C3C",
                    "fill-opacity": 0.25,
                },
            },
            # ── Pond candidate (green) ─────────────────────────────────────
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": pond_coords},
                "properties": {
                    **pond_props,
                    "title": "Pond Candidate",
                    "description": (
                        f"Suitability score: {pond_props.get('suitability_score', '?')} / 1.0 "
                        f"| Elevation: {pond_props.get('elevation_m', '?')} m "
                        f"| Slope: {pond_props.get('slope_degrees', '?')}°"
                    ),
                    # Mapbox SimpleStyle marker — "circle" is always valid in geojson.io
                    "marker-color": "#27AE60",
                    "marker-size": "large",
                    "marker-symbol": "circle",
                },
            },
            # ── Pour point (blue) ──────────────────────────────────────────
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": pour_coords},
                "properties": {
                    **pour_props,
                    "title": "Pour Point (Catchment Outlet)",
                    "description": (
                        f"Flow accumulation: {pour_props.get('flow_accumulation', '?')} "
                        f"| Snap distance: {pour_props.get('snap_distance_m', '?')} m"
                    ),
                    "marker-color": "#2980B9",
                    "marker-size": "medium",
                    "marker-symbol": "circle",
                },
            },
        ],
    }
