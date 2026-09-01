"""
Subprocess worker for catchment delineation.

This module is executed as a standalone script in a child process via
subprocess.run(). Isolation is required because pysheds (<=0.5) corrupts
the C heap when fill_pits/fill_depressions/resolve_flats/flowdir/catchment
are called more than once in the same process. Running in a fresh subprocess
gives each delineation its own clean C heap.

Interface
---------
Input  (stdin): JSON with keys:
    temp_dem_path  : str   — path to GeoTIFF
    pour_lon       : float
    pour_lat       : float
    elev_grid      : list[list[float]]   — 2-D elevation array
    bbox_west/east/north/south : float
    utm_epsg       : int

Output (stdout): JSON with keys on success:
    ok         : true
    polygon    : GeoJSON geometry dict (Polygon or MultiPolygon)
    area_sq_m  : float
    area_sq_km : float
    avg_elev   : float
    cell_count : int
    centroid_lon/lat : float

Output (stdout): JSON with keys on failure:
    ok    : false
    error : str
"""

from __future__ import annotations

import json
import sys

import numpy as np


def main() -> None:
    payload = json.load(sys.stdin)

    temp_dem_path = payload["temp_dem_path"]
    pour_lon      = float(payload["pour_lon"])
    pour_lat      = float(payload["pour_lat"])
    elev_grid     = np.array(payload["elev_grid"], dtype=np.float64)
    utm_epsg      = int(payload["utm_epsg"])
    # Pre-computed flow direction from parent process (skips the heavy pipeline).
    fdir_arr_raw  = payload.get("fdir_arr")

    # ── NumPy 2.x compat shim ─────────────────────────────────────────────────
    if not hasattr(np, "in1d"):
        def _in1d_compat(ar1, ar2, **kw):
            return np.isin(ar1, ar2, **kw).ravel()
        np.in1d = _in1d_compat  # type: ignore[attr-defined]

    try:
        from pysheds.grid import Grid as PyshedsGrid
        import rasterio
        from rasterio.features import shapes
        from shapely.geometry import mapping, shape
        from shapely.ops import transform, unary_union
        from pyproj import CRS, Transformer

        # Fresh Grid per subprocess — no heap corruption possible.
        grid = PyshedsGrid.from_raster(temp_dem_path)

        if fdir_arr_raw is not None:
            # Fast path: use the flow direction already computed by the main
            # process. Skip fill_pits / fill_depressions / resolve_flats /
            # flowdir — these are the four slow steps.
            dem   = grid.read_raster(temp_dem_path)
            fdir_np = np.array(fdir_arr_raw, dtype=np.int64)
            # Wrap the numpy array in a pysheds Raster so grid.catchment accepts it
            from pysheds.sview import Raster as PyshedsRaster
            fdir = PyshedsRaster(fdir_np, viewfinder=dem.viewfinder)
        else:
            # Slow fallback path (no pre-computed fdir supplied).
            dem      = grid.read_raster(temp_dem_path)
            filled   = grid.fill_pits(dem)
            flooded  = grid.fill_depressions(filled)
            inflated = grid.resolve_flats(flooded)
            fdir     = grid.flowdir(inflated)

        catch     = grid.catchment(x=pour_lon, y=pour_lat, fdir=fdir, xytype="coordinate")
        catch_arr = np.array(catch).astype(np.uint8)

        with rasterio.open(temp_dem_path) as src:
            transform_affine = src.transform

        polys = [
            shape(geom)
            for geom, val in shapes(catch_arr, mask=(catch_arr > 0), transform=transform_affine)
            if val > 0
        ]
        if not polys:
            _fail("Catchment delineation produced no polygon.")
            return

        merged = unary_union(polys)

        wgs84 = CRS.from_epsg(4326)
        utm   = CRS.from_epsg(utm_epsg)
        tf    = Transformer.from_crs(wgs84, utm, always_xy=True)
        proj  = transform(tf.transform, merged)
        area_sq_m  = proj.area
        area_sq_km = area_sq_m / 1_000_000.0

        cell_count = int(catch_arr.sum())
        elev_cells = elev_grid[catch_arr > 0]
        avg_elev   = float(np.mean(elev_cells)) if len(elev_cells) > 0 else 0.0
        centroid   = merged.centroid

        result = {
            "ok":          True,
            "polygon":     mapping(merged),
            "area_sq_m":   area_sq_m,
            "area_sq_km":  area_sq_km,
            "avg_elev":    avg_elev,
            "cell_count":  cell_count,
            "centroid_lon": float(centroid.x),
            "centroid_lat": float(centroid.y),
        }
        print(json.dumps(result))

    except Exception as exc:  # noqa: BLE001
        _fail(str(exc))


def _fail(msg: str) -> None:
    print(json.dumps({"ok": False, "error": msg}))


if __name__ == "__main__":
    main()
