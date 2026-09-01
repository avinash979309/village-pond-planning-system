"""
Terrain-based water body / floodplain detector.

Detects river beds, floodplains, and standing water zones purely from the
DEM — no network access required.

Why this module exists
----------------------
The OSM Overpass API can be unreachable (air-gapped servers, network
restrictions). When OSM fails, the pipeline previously returned an empty
exclusion mask, allowing pond candidates to land inside active river beds.

This module provides an offline fallback (and primary layer) that identifies
likely water / floodplain areas using three terrain signals:

1. **Absolute low-elevation zone** — the bottom N% of the elevation
   distribution forms the valley / river bed. These cells are excluded
   regardless of flow accumulation.

2. **High-flow-accumulation corridor** — cells at or above the 98th
   percentile of flow accumulation are major drainage channels (rivers).
   These are dilated by ``river_buffer_cells`` to cover the full river width.

3. **Flat low zone** — cells that are BOTH in the bottom 20% of elevation
   AND have slope < 1 degree form the flat floodplain / river terrace.
   These are typically uninhabitable valley floors.

All three masks are OR-combined and then dilated by ``buffer_cells`` to
provide a safety margin so candidates are not placed right at the edge of
the river bank.

This approach generalises: it does not rely on any coordinates, place names,
or hardcoded values. Any DEM with a dominant river corridor will trigger
appropriate exclusion.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.ndimage import binary_dilation

from app.geo.utils import BBox

logger = logging.getLogger(__name__)

# ── Output ─────────────────────────────────────────────────────────────────────

@dataclass
class TerrainWaterResult:
    """
    Result of terrain-based water / floodplain detection.

    Attributes
    ----------
    water_mask : np.ndarray (bool, rows × cols)
        True for every grid cell identified as water body or floodplain.
    low_elev_mask : np.ndarray (bool)
        Cells in the absolute lowest elevation zone.
    high_acc_mask : np.ndarray (bool)
        Cells with very high flow accumulation (river channels), after dilation.
    flat_low_mask : np.ndarray (bool)
        Cells that are both flat and in the low-elevation zone.
    coverage_pct : float
        Percentage of grid covered by the combined water mask.
    description : str
        Human-readable summary of what was detected.
    """
    water_mask: np.ndarray
    low_elev_mask: np.ndarray
    high_acc_mask: np.ndarray
    flat_low_mask: np.ndarray
    coverage_pct: float
    description: str


# ── Public API ─────────────────────────────────────────────────────────────────

def detect_terrain_water(
    elev_grid: np.ndarray,
    slope_grid: np.ndarray,
    flow_accumulation: np.ndarray,
    low_elev_pct: float = 15.0,
    river_acc_pct: float = 98.0,
    river_buffer_cells: int = 8,
    flat_slope_threshold: float = 1.0,
    buffer_cells: int = 3,
    max_coverage_pct: float = 60.0,
) -> TerrainWaterResult:
    """
    Detect river beds and floodplains from terrain data alone.

    Parameters
    ----------
    elev_grid : np.ndarray (rows, cols)
        Elevation grid in metres.
    slope_grid : np.ndarray (rows, cols)
        Slope in degrees.
    flow_accumulation : np.ndarray (rows, cols)
        D8 flow accumulation values.
    low_elev_pct : float
        Bottom N% of elevation range treated as valley / river floor.
        Default 15 means all cells within 15% of the total elevation range
        above the minimum are flagged.
    river_acc_pct : float
        Percentile threshold for identifying major river channels from
        flow accumulation. Top (100 - river_acc_pct)% of cells are channels.
    river_buffer_cells : int
        Dilation radius around detected river channel cells. Set large enough
        to cover the full physical river width at the given grid resolution.
        At ~15 m/cell, 8 cells ≈ 120 m buffer on each side.
    flat_slope_threshold : float
        Maximum slope (degrees) for a cell to be considered "flat" (valley
        floor / floodplain).
    buffer_cells : int
        Additional dilation applied to the combined mask for safety margin.
    max_coverage_pct : float
        Safety cap: if the combined mask would cover more than this fraction
        of the grid, relax the thresholds progressively to avoid excluding
        all valid candidates.

    Returns
    -------
    TerrainWaterResult
    """
    rows, cols = elev_grid.shape
    n_cells = rows * cols

    # ── Layer 1: Absolute low-elevation zone ────────────────────────────────
    min_elev = float(np.nanmin(elev_grid))
    max_elev = float(np.nanmax(elev_grid))
    elev_range = max_elev - min_elev

    low_elev_thresh = min_elev + elev_range * (low_elev_pct / 100.0)
    low_elev_mask = elev_grid <= low_elev_thresh

    # ── Layer 2: High-flow-accumulation river channels ───────────────────────
    acc_threshold = float(np.percentile(flow_accumulation, river_acc_pct))
    river_channel_raw = flow_accumulation >= acc_threshold

    # Dilate river channel to cover full river width
    if river_buffer_cells > 0 and river_channel_raw.any():
        struct_r = np.ones(
            (2 * river_buffer_cells + 1, 2 * river_buffer_cells + 1), dtype=bool
        )
        high_acc_mask = binary_dilation(river_channel_raw, structure=struct_r)
    else:
        high_acc_mask = river_channel_raw.copy()

    # ── Layer 3: Flat low zone (floodplain / valley floor) ───────────────────
    p20_elev = float(np.nanpercentile(elev_grid, 20))
    flat_low_raw = (elev_grid <= p20_elev) & (slope_grid <= flat_slope_threshold)
    if buffer_cells > 0 and flat_low_raw.any():
        struct_fl = np.ones((2 * buffer_cells + 1, 2 * buffer_cells + 1), dtype=bool)
        flat_low_mask = binary_dilation(flat_low_raw, structure=struct_fl)
    else:
        flat_low_mask = flat_low_raw.copy()

    # ── Combine all layers ───────────────────────────────────────────────────
    combined = low_elev_mask | high_acc_mask | flat_low_mask

    # ── Safety cap: relax if too much of the grid is excluded ────────────────
    coverage = 100.0 * combined.sum() / n_cells
    if coverage > max_coverage_pct:
        logger.warning(
            "Terrain water mask covers %.1f%% of grid (> %.1f%% cap). "
            "Falling back to high-accumulation-only mask.",
            coverage,
            max_coverage_pct,
        )
        # Fallback: use only the high-acc river channel (smaller footprint)
        combined = high_acc_mask.copy()
        coverage = 100.0 * combined.sum() / n_cells

    # ── Final dilation (safety margin) ──────────────────────────────────────
    if buffer_cells > 0 and combined.any():
        struct_b = np.ones((2 * buffer_cells + 1, 2 * buffer_cells + 1), dtype=bool)
        combined = binary_dilation(combined, structure=struct_b)

    coverage_final = 100.0 * combined.sum() / n_cells

    parts = []
    if low_elev_mask.any():
        parts.append(
            f"low-elevation zone (bottom {low_elev_pct:.0f}% of {elev_range:.0f}m range)"
        )
    if river_channel_raw.any():
        parts.append(
            f"river channel (top {100-river_acc_pct:.0f}% flow accumulation, "
            f"buffer {river_buffer_cells} cells)"
        )
    if flat_low_raw.any():
        parts.append(
            f"flat floodplain (elev ≤ p20 + slope ≤ {flat_slope_threshold}°)"
        )

    description = (
        f"Terrain-based water exclusion: {'; '.join(parts) if parts else 'none detected'}. "
        f"Covers {coverage_final:.1f}% of grid."
    )

    logger.info("Terrain water detection: %s", description)

    return TerrainWaterResult(
        water_mask=combined,
        low_elev_mask=low_elev_mask,
        high_acc_mask=high_acc_mask,
        flat_low_mask=flat_low_mask,
        coverage_pct=coverage_final,
        description=description,
    )
