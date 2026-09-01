"""
Hydrology engine: D8 flow direction, flow accumulation, drainage derivation.

Pipeline
--------
1. Write the elevation grid to a temporary GeoTIFF (rasterio).
   pysheds requires a real GeoTIFF on disk — it cannot consume raw numpy arrays.

2. Load the GeoTIFF into a pysheds Grid.

3. Condition the DEM:
   a. Fill pits           (single-cell depressions)
   b. Fill depressions    (multi-cell enclosed basins)
   c. Resolve flats       (flat regions with no gradient)
   These three steps ensure every cell has a defined downhill neighbour,
   which is required for D8 flow direction computation.

4. D8 flow direction:
   Each cell is assigned a flow code indicating which of its 8 neighbours
   is lowest (or, after conditioning, which has the defined outflow).
   pysheds uses power-of-2 encoding: E=1, SE=2, S=4, SW=8, W=16, NW=32, N=64, NE=128.

5. Flow accumulation:
   For each cell, count the total number of upstream cells that drain to it.
   High accumulation → convergent drainage → stream channel.

6. Derive drainage network:
   Cells where flow_accumulation > threshold are classified as drainage channels.
   Threshold = percentile(flow_accum, 100 - drainage_threshold_pct).

7. Build exclusion mask:
   Dilate the drainage mask by buffer_cells using binary dilation
   (scipy.ndimage). Exclusion zone = drainage channel + buffer.

Why pysheds?
------------
pysheds (ADR-009, APPROVED) provides a tested, well-documented Python
implementation of the standard GIS hydrological workflow. Writing these
algorithms from scratch would be error-prone.

Important
---------
This module writes and manages temporary files internally using
tempfile.NamedTemporaryFile. Callers must not assume any side effects
on the filesystem beyond what is returned in HydrologyResult.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from scipy.ndimage import binary_dilation

# ── NumPy 2.x compatibility for pysheds ──────────────────────────────────────
# pysheds (<=0.5) calls np.in1d, removed in NumPy 2.0. Patch before import.
if not hasattr(np, "in1d"):
    def _in1d_compat(ar1, ar2, **kw):
        import numpy as _n
        return _n.isin(ar1, ar2, **kw).ravel()
    np.in1d = _in1d_compat
# ─────────────────────────────────────────────────────────────────────────────


from app.geo.utils import BBox

try:
    from pysheds.grid import Grid as PyshedsGrid
    _PYSHEDS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYSHEDS_AVAILABLE = False



# ── Output ────────────────────────────────────────────────────────────────────

@dataclass
class HydrologyResult:
    """
    Result of hydrological analysis on an elevation grid.

    Attributes
    ----------
    conditioned_dem : np.ndarray
        Sink-filled, flat-resolved elevation grid used for D8 analysis.
    flow_direction : np.ndarray
        D8 flow direction encoded as pysheds integers.
    flow_accumulation : np.ndarray
        Per-cell upstream contributing-cell count.
    drainage_mask : np.ndarray (bool)
        True where flow_accumulation exceeds the drainage threshold.
    exclusion_mask : np.ndarray (bool)
        drainage_mask dilated by buffer_cells. Pond candidates excluded here.
    drainage_cell_count : int
    drainage_threshold_value : float
        Actual flow-accumulation value used as threshold.
    temp_dem_path : str
        Path to the temporary GeoTIFF written during analysis.
        Caller is responsible for deleting it when no longer needed.
    pysheds_grid : PyshedsGrid instance (or None if pysheds unavailable)
    """
    conditioned_dem: np.ndarray
    flow_direction: np.ndarray
    flow_accumulation: np.ndarray
    drainage_mask: np.ndarray
    exclusion_mask: np.ndarray
    drainage_cell_count: int
    drainage_threshold_value: float
    temp_dem_path: str
    pysheds_grid: object  # PyshedsGrid | None


# ── Public API ────────────────────────────────────────────────────────────────

def run_hydrology(
    elev_grid: np.ndarray,
    bbox: BBox,
    drainage_threshold_pct: float = 2.0,
    drainage_buffer_cells: int = 2,
    tmp_dir: str | None = None,
) -> HydrologyResult:
    """
    Run the full hydrological analysis pipeline on an elevation grid.

    Parameters
    ----------
    elev_grid : np.ndarray, shape (rows, cols)
        Elevation in metres. Row 0 = northernmost row.
    bbox : BBox
        Spatial extent in WGS84 (EPSG:4326).
    drainage_threshold_pct : float
        Percentage used to define drainage threshold.
        Top `drainage_threshold_pct`% of flow-accumulation values are
        treated as drainage channels.
    drainage_buffer_cells : int
        Number of grid cells to dilate around drainage channels for the
        exclusion zone.
    tmp_dir : str, optional
        Directory for temporary GeoTIFF. Defaults to system temp dir.

    Returns
    -------
    HydrologyResult
    """
    if not _PYSHEDS_AVAILABLE:
        raise RuntimeError(  # pragma: no cover
            "pysheds is not installed. Install it with: pip install pysheds"
        )

    rows, cols = elev_grid.shape

    # ── Step 1: Write elevation grid to temporary GeoTIFF ────────────────────
    tmp_path = _write_temp_geotiff(elev_grid, bbox, tmp_dir)

    # ── Step 2: Load into pysheds ─────────────────────────────────────────────
    grid = PyshedsGrid.from_raster(tmp_path)
    dem = grid.read_raster(tmp_path)

    # ── Step 3: Condition DEM ─────────────────────────────────────────────────
    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)
    conditioned = np.array(inflated)

    # ── Step 4: Flow direction (D8) ──────────────────────────────────────────
    fdir = grid.flowdir(inflated)
    fdir_arr = np.array(fdir)

    # ── Step 5: Flow accumulation ─────────────────────────────────────────────
    acc = grid.accumulation(fdir)
    acc_arr = np.array(acc, dtype=np.float64)

    # ── Step 6: Drainage threshold ────────────────────────────────────────────
    # "Top drainage_threshold_pct% of cells" → percentile threshold
    threshold_percentile = 100.0 - drainage_threshold_pct
    threshold_value = float(np.percentile(acc_arr, threshold_percentile))
    drainage_mask = acc_arr >= threshold_value
    drainage_cell_count = int(drainage_mask.sum())

    # ── Step 7: Exclusion mask (dilated drainage) ─────────────────────────────
    if drainage_buffer_cells > 0:
        struct = np.ones(
            (2 * drainage_buffer_cells + 1, 2 * drainage_buffer_cells + 1),
            dtype=bool,
        )
        exclusion_mask = binary_dilation(drainage_mask, structure=struct)
    else:
        exclusion_mask = drainage_mask.copy()

    return HydrologyResult(
        conditioned_dem=conditioned,
        flow_direction=fdir_arr,
        flow_accumulation=acc_arr,
        drainage_mask=drainage_mask,
        exclusion_mask=exclusion_mask,
        drainage_cell_count=drainage_cell_count,
        drainage_threshold_value=threshold_value,
        temp_dem_path=tmp_path,
        pysheds_grid=grid,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _write_temp_geotiff(
    elev_grid: np.ndarray,
    bbox: BBox,
    tmp_dir: str | None,
) -> str:
    """
    Write a numpy elevation array to a temporary GeoTIFF and return its path.

    The caller is responsible for deleting the file.
    NoData is set to -9999 for compatibility with pysheds.
    """
    rows, cols = elev_grid.shape
    transform = from_bounds(bbox.west, bbox.south, bbox.east, bbox.north, cols, rows)

    # Replace NaN with NoData value before writing
    data_out = elev_grid.copy().astype(np.float32)
    data_out[np.isnan(data_out)] = -9999.0

    # Create file in tmp_dir (or system temp)
    fd, tmp_path = tempfile.mkstemp(suffix=".tif", dir=tmp_dir, prefix="pond_dem_")
    os.close(fd)

    with rasterio.open(
        tmp_path,
        "w",
        driver="GTiff",
        height=rows,
        width=cols,
        count=1,
        dtype=np.float32,
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(data_out, 1)

    return tmp_path
