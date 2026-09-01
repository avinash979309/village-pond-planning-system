"""
Pond candidate selector.

Algorithm
---------
Selects the best pond location from an elevation grid using a
transparent, deterministic, weighted multi-factor scoring method.

No machine learning is used (see ADR-010: Suitability scoring over ML).
All scoring factors are computed from input terrain data alone —
no hardcoded coordinates, elevations, or sample-specific values.

Scoring factors (each normalised to [0, 1])
-------------------------------------------
1. Elevation score  (weight w1, default 0.20)
   Prefers MODERATE elevation — not the lowest (river bed / floodplain)
   and not the highest (hilltop with no catchment).
   Score peaks at the 20th–40th elevation percentile of the grid,
   decaying to 0 at both extremes.
   Rationale: Ideal pond sites are on hillside depressions above
   the river floodplain but below the watershed divide.

2. Slope score      (weight w2, default 0.30)
   Gentler slope → higher score.
   Rationale: Flat or gently sloping land is easier to excavate,
   retains water better (less seepage through steep walls), and
   is cheaper to dam.

3. Flow accumulation score  (weight w3, default 0.30)
   Higher flow accumulation → higher score.
   Rationale: High accumulation indicates the cell receives runoff
   from a large upstream contributing area — more water supply.
   Capped at the 80th percentile to prevent river-channel values
   (which are extremely high) from pulling candidates back into
   the river bed.

4. Proximity-to-drainage score  (weight w4, default 0.20)
   Cells within a configurable ring around drainage channels score 1;
   cells farther away score lower.
   Rationale: A pond near (but not on) a drainage pathway will capture
   runoff efficiently through natural topographic funnelling.

Exclusion rule
--------------
Cells in the exclusion_mask (drainage channel + buffer + water bodies
including OSM and terrain-derived floodplain) are set to score = 0
BEFORE finding the maximum. This guarantees the selected candidate
does not sit on an active drainage channel, river, or floodplain.

Output
------
The single highest-scoring non-excluded cell (select_pond_candidate), or
the top N spatially-separated candidates (select_top_candidates).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy.ndimage import distance_transform_edt

from app.geo.utils import BBox, grid_index_to_coords, normalise_01, invert_normalise_01


# ── Default scoring weights ───────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "elevation": 0.20,
    "slope": 0.30,
    "accumulation": 0.30,
    "proximity": 0.20,
}


# ── Output ────────────────────────────────────────────────────────────────────

@dataclass
class CandidateResult:
    """Best pond candidate location."""
    row: int
    col: int
    lon: float
    lat: float
    elevation_m: float
    slope_degrees: float
    flow_accumulation: float
    suitability_score: float
    score_breakdown: dict  # {"elevation": float, "slope": float, ...}
    on_drainage_channel: bool
    exclusion_zone_respected: bool
    score_grid: np.ndarray  # full score grid (for debugging / visualisation)


# ── Public API ────────────────────────────────────────────────────────────────

def select_pond_candidate(
    elev_grid: np.ndarray,
    slope_grid: np.ndarray,
    flow_accumulation: np.ndarray,
    drainage_mask: np.ndarray,
    exclusion_mask: np.ndarray,
    bbox: BBox,
    weights: Optional[dict] = None,
) -> CandidateResult:
    """
    Select the best pond candidate cell using weighted suitability scoring.

    Parameters
    ----------
    elev_grid : np.ndarray (rows, cols)
    slope_grid : np.ndarray (rows, cols)  — slope in degrees
    flow_accumulation : np.ndarray (rows, cols)
    drainage_mask : np.ndarray (bool, rows, cols)
        True = drainage channel cell.
    exclusion_mask : np.ndarray (bool, rows, cols)
        True = excluded from candidate selection (drainage + buffer).
    bbox : BBox
    weights : dict, optional
        Keys: "elevation", "slope", "accumulation", "proximity".
        Values must sum to 1.0. Defaults to DEFAULT_WEIGHTS.

    Returns
    -------
    CandidateResult

    Raises
    ------
    ValueError
        If all cells are in the exclusion zone (no valid candidates).
    """
    w = weights or DEFAULT_WEIGHTS

    # ── Factor 1: Elevation score (moderate elevation preferred) ──────────────
    # Scoring: peaks at the 20th–40th percentile band of the elevation
    # distribution, decaying to 0 at both extremes.
    # This prevents the algorithm from picking cells in the river bed
    # (absolute minimum) or on barren hilltops (absolute maximum).
    p20_elev = float(np.nanpercentile(elev_grid, 20))
    p40_elev = float(np.nanpercentile(elev_grid, 40))
    min_elev = float(np.nanmin(elev_grid))
    max_elev = float(np.nanmax(elev_grid))

    elev_score = np.zeros(elev_grid.shape, dtype=np.float64)
    # Below p20: linearly 0 at global min → 1 at p20 (rises toward preferred band)
    mask_lo = elev_grid <= p20_elev
    denom_lo = max(p20_elev - min_elev, 1e-6)
    elev_score[mask_lo] = np.clip((elev_grid[mask_lo] - min_elev) / denom_lo, 0.0, 1.0)
    # p20–p40: score = 1.0 (the preferred band)
    mask_mid = (elev_grid > p20_elev) & (elev_grid <= p40_elev)
    elev_score[mask_mid] = 1.0
    # Above p40: linearly 1 at p40 → 0 at global max (decays beyond preferred band)
    mask_hi = elev_grid > p40_elev
    denom_hi = max(max_elev - p40_elev, 1e-6)
    elev_score[mask_hi] = np.clip(1.0 - (elev_grid[mask_hi] - p40_elev) / denom_hi, 0.0, 1.0)

    # ── Factor 2: Slope score (lower slope = better) ──────────────────────────
    slope_score = invert_normalise_01(slope_grid)

    # ── Factor 3: Flow accumulation score ────────────────────────────────────
    # Cap at 80th percentile (not 95th) to prevent high-accumulation river
    # cells from artificially boosting scores in the river corridor.
    cap_val = float(np.percentile(flow_accumulation, 80))
    acc_capped = np.clip(flow_accumulation, 0, cap_val)
    acc_score = normalise_01(acc_capped)

    # ── Factor 4: Proximity-to-drainage score ─────────────────────────────────
    # Distance transform gives distance (in cells) from nearest drainage cell.
    # Invert: cells CLOSE to drainage (but not on it) score higher.
    # Cells ON drainage are excluded anyway, so this is safe.
    if drainage_mask.any():
        # distance_transform_edt: distance from nearest False pixel (non-drainage)
        # We want distance from nearest True pixel (drainage cell)
        dist_to_drainage = distance_transform_edt(~drainage_mask)
        # Clamp: very distant cells score 0; cells adjacent to drainage score 1
        max_meaningful_dist = float(np.percentile(dist_to_drainage, 80))
        if max_meaningful_dist > 0:
            prox_raw = 1.0 - np.clip(dist_to_drainage / max_meaningful_dist, 0.0, 1.0)
        else:
            prox_raw = np.zeros_like(dist_to_drainage)
        proximity_score = prox_raw
    else:
        # No drainage cells: proximity factor contributes nothing
        proximity_score = np.zeros_like(elev_grid)

    # ── Composite score ───────────────────────────────────────────────────────
    composite = (
        w["elevation"] * elev_score
        + w["slope"] * slope_score
        + w["accumulation"] * acc_score
        + w["proximity"] * proximity_score
    )

    # ── Apply exclusion zone ──────────────────────────────────────────────────
    composite[exclusion_mask] = 0.0

    if composite.max() == 0.0:
        raise ValueError(
            "All grid cells fall within the drainage exclusion zone. "
            "Try reducing drainage_threshold_pct or drainage_buffer_cells."
        )

    # ── Select best cell ──────────────────────────────────────────────────────
    flat_idx = int(np.argmax(composite))
    row, col = np.unravel_index(flat_idx, composite.shape)
    lon, lat = grid_index_to_coords(row, col, bbox, composite.shape)

    score_breakdown = {
        "elevation_score": float(elev_score[row, col]),
        "slope_score": float(slope_score[row, col]),
        "accumulation_score": float(acc_score[row, col]),
        "proximity_score": float(proximity_score[row, col]),
    }

    return CandidateResult(
        row=int(row),
        col=int(col),
        lon=lon,
        lat=lat,
        elevation_m=float(elev_grid[row, col]),
        slope_degrees=float(slope_grid[row, col]),
        flow_accumulation=float(flow_accumulation[row, col]),
        suitability_score=float(composite[row, col]),
        score_breakdown=score_breakdown,
        on_drainage_channel=bool(drainage_mask[row, col]),
        exclusion_zone_respected=not bool(exclusion_mask[row, col]),
        score_grid=composite,
    )


# ── Multi-candidate selection ─────────────────────────────────────────────────

def select_top_candidates(
    elev_grid: np.ndarray,
    slope_grid: np.ndarray,
    flow_accumulation: np.ndarray,
    drainage_mask: np.ndarray,
    exclusion_mask: np.ndarray,
    bbox: BBox,
    weights: Optional[dict] = None,
    n_candidates: int = 3,
    min_separation_cells: int = 15,
) -> List[CandidateResult]:
    """
    Select the top N spatially-separated pond candidates.

    Uses iterative spatial suppression: after selecting each candidate,
    a circular suppression zone of radius ``min_separation_cells`` is
    zeroed out in the composite score grid before picking the next one.
    This guarantees candidates are not clustered.

    Parameters
    ----------
    elev_grid, slope_grid, flow_accumulation, drainage_mask, exclusion_mask, bbox, weights
        Same as select_pond_candidate.
    n_candidates : int
        Maximum number of candidates to return (default 3).
        Fewer may be returned if the grid runs out of valid cells.
    min_separation_cells : int
        Minimum grid-cell distance between any two candidates (default 15).
        At ~15m/cell this is ~225m minimum separation.

    Returns
    -------
    List[CandidateResult]
        Ordered best → worst suitability. Always at least 1 element
        (the best candidate is always included).
    """
    w = weights or DEFAULT_WEIGHTS

    # ── Build composite score (same logic as select_pond_candidate) ───────────
    p20_elev = float(np.nanpercentile(elev_grid, 20))
    p40_elev = float(np.nanpercentile(elev_grid, 40))
    min_elev = float(np.nanmin(elev_grid))
    max_elev = float(np.nanmax(elev_grid))

    elev_score = np.zeros(elev_grid.shape, dtype=np.float64)
    mask_lo = elev_grid <= p20_elev
    denom_lo = max(p20_elev - min_elev, 1e-6)
    elev_score[mask_lo] = np.clip((elev_grid[mask_lo] - min_elev) / denom_lo, 0.0, 1.0)
    mask_mid = (elev_grid > p20_elev) & (elev_grid <= p40_elev)
    elev_score[mask_mid] = 1.0
    mask_hi = elev_grid > p40_elev
    denom_hi = max(max_elev - p40_elev, 1e-6)
    elev_score[mask_hi] = np.clip(1.0 - (elev_grid[mask_hi] - p40_elev) / denom_hi, 0.0, 1.0)

    slope_score = invert_normalise_01(slope_grid)

    cap_val = float(np.percentile(flow_accumulation, 80))
    acc_capped = np.clip(flow_accumulation, 0, cap_val)
    acc_score = normalise_01(acc_capped)

    if drainage_mask.any():
        dist_to_drainage = distance_transform_edt(~drainage_mask)
        max_meaningful_dist = float(np.percentile(dist_to_drainage, 80))
        if max_meaningful_dist > 0:
            prox_raw = 1.0 - np.clip(dist_to_drainage / max_meaningful_dist, 0.0, 1.0)
        else:
            prox_raw = np.zeros_like(dist_to_drainage)
        proximity_score = prox_raw
    else:
        proximity_score = np.zeros_like(elev_grid)

    composite = (
        w["elevation"] * elev_score
        + w["slope"] * slope_score
        + w["accumulation"] * acc_score
        + w["proximity"] * proximity_score
    )
    composite[exclusion_mask] = 0.0

    if composite.max() == 0.0:
        raise ValueError(
            "All grid cells fall within the drainage exclusion zone. "
            "Try reducing drainage_threshold_pct or drainage_buffer_cells."
        )

    # Working copy to suppress around each picked candidate
    remaining = composite.copy()
    rows, cols = composite.shape

    # Precompute suppression disk mask (used to zero cells around each pick)
    r_sq = min_separation_cells ** 2
    y_idx, x_idx = np.ogrid[-min_separation_cells:min_separation_cells + 1,
                             -min_separation_cells:min_separation_cells + 1]
    disk = (y_idx ** 2 + x_idx ** 2) <= r_sq   # True inside suppression radius

    results: List[CandidateResult] = []

    for rank in range(n_candidates):
        if remaining.max() == 0.0:
            break  # No more valid cells

        flat_idx = int(np.argmax(remaining))
        row, col = np.unravel_index(flat_idx, remaining.shape)
        lon, lat = grid_index_to_coords(row, col, bbox, remaining.shape)

        score_breakdown = {
            "elevation_score": float(elev_score[row, col]),
            "slope_score": float(slope_score[row, col]),
            "accumulation_score": float(acc_score[row, col]),
            "proximity_score": float(proximity_score[row, col]),
        }

        results.append(CandidateResult(
            row=int(row),
            col=int(col),
            lon=lon,
            lat=lat,
            elevation_m=float(elev_grid[row, col]),
            slope_degrees=float(slope_grid[row, col]),
            flow_accumulation=float(flow_accumulation[row, col]),
            suitability_score=float(composite[row, col]),
            score_breakdown=score_breakdown,
            on_drainage_channel=bool(drainage_mask[row, col]),
            exclusion_zone_respected=not bool(exclusion_mask[row, col]),
            score_grid=composite,
        ))

        # Suppress circular zone around this candidate in the working copy
        r_lo = max(0, row - min_separation_cells)
        r_hi = min(rows, row + min_separation_cells + 1)
        c_lo = max(0, col - min_separation_cells)
        c_hi = min(cols, col + min_separation_cells + 1)

        # Slice of disk aligned to clamped region
        dr_lo = r_lo - (row - min_separation_cells)
        dr_hi = dr_lo + (r_hi - r_lo)
        dc_lo = c_lo - (col - min_separation_cells)
        dc_hi = dc_lo + (c_hi - c_lo)

        remaining[r_lo:r_hi, c_lo:c_hi][disk[dr_lo:dr_hi, dc_lo:dc_hi]] = 0.0

    return results
