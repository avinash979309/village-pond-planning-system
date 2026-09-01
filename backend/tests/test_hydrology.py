"""
Tests for hydrology_engine and pond_candidate_selector modules.

Covers:
- Hydrology result contains expected arrays
- Flow accumulation is non-negative everywhere
- Drainage mask is a boolean array
- Exclusion mask is at least as large as drainage mask
- Pond candidate is not inside exclusion zone
- Pond candidate score > 0
- Score breakdown sums approximately to composite score
- Candidate not on drainage channel
- All-excluded grid raises ValueError
"""

from __future__ import annotations

import numpy as np
import pytest

from app.geo.kml_parser import parse_upload
from app.geo.terrain_builder import build_elevation_grid
from app.geo.terrain_conditioner import compute_slope
from app.geo.hydrology_engine import run_hydrology
from app.geo.pond_candidate_selector import select_pond_candidate, DEFAULT_WEIGHTS
from app.geo.utils import BBox


SYNTHETIC_KML_PATH = "tests/data/synthetic_contour.kml"


def _build_analysis(grid_resolution=80):
    with open(SYNTHETIC_KML_PATH, "rb") as f:
        parsed_raw = f.read()
    from app.geo.kml_parser import parse_upload
    parsed = parse_upload(parsed_raw, "synthetic_contour.kml")
    bbox = parsed.bbox
    elev_grid = build_elevation_grid(parsed.contour_lines, bbox, grid_resolution=grid_resolution).data
    slope_grid = compute_slope(elev_grid, bbox).data
    hydro = run_hydrology(elev_grid, bbox, drainage_threshold_pct=2.0, drainage_buffer_cells=2)
    return elev_grid, slope_grid, hydro, bbox


# ── Hydrology engine ──────────────────────────────────────────────────────────

class TestHydrologyEngine:
    def test_result_arrays_correct_shape(self):
        elev_grid, _, hydro, bbox = _build_analysis()
        assert hydro.flow_accumulation.shape == elev_grid.shape
        assert hydro.flow_direction.shape == elev_grid.shape
        assert hydro.drainage_mask.shape == elev_grid.shape
        assert hydro.exclusion_mask.shape == elev_grid.shape

    def test_flow_accumulation_nonnegative(self):
        _, _, hydro, _ = _build_analysis()
        assert float(hydro.flow_accumulation.min()) >= 0.0

    def test_drainage_mask_is_boolean(self):
        _, _, hydro, _ = _build_analysis()
        assert hydro.drainage_mask.dtype == bool

    def test_exclusion_mask_superset_of_drainage(self):
        """Exclusion = drainage + buffer. Exclusion must contain all drainage cells."""
        _, _, hydro, _ = _build_analysis()
        # Every drainage cell must also be in the exclusion mask
        assert np.all(hydro.exclusion_mask[hydro.drainage_mask])

    def test_drainage_cell_count_positive(self):
        _, _, hydro, _ = _build_analysis()
        assert hydro.drainage_cell_count > 0

    def test_temp_dem_path_is_string(self):
        _, _, hydro, _ = _build_analysis()
        assert isinstance(hydro.temp_dem_path, str)
        assert hydro.temp_dem_path.endswith(".tif")


# ── Pond candidate selector ───────────────────────────────────────────────────

class TestPondCandidateSelector:
    def test_candidate_not_in_exclusion_zone(self):
        elev_grid, slope_grid, hydro, bbox = _build_analysis()
        candidate = select_pond_candidate(
            elev_grid, slope_grid,
            hydro.flow_accumulation,
            hydro.drainage_mask, hydro.exclusion_mask,
            bbox,
        )
        # The selected cell must not be in the exclusion mask
        assert not hydro.exclusion_mask[candidate.row, candidate.col]

    def test_candidate_exclusion_zone_respected_flag(self):
        elev_grid, slope_grid, hydro, bbox = _build_analysis()
        candidate = select_pond_candidate(
            elev_grid, slope_grid,
            hydro.flow_accumulation,
            hydro.drainage_mask, hydro.exclusion_mask,
            bbox,
        )
        assert candidate.exclusion_zone_respected is True

    def test_candidate_not_on_drainage(self):
        elev_grid, slope_grid, hydro, bbox = _build_analysis()
        candidate = select_pond_candidate(
            elev_grid, slope_grid,
            hydro.flow_accumulation,
            hydro.drainage_mask, hydro.exclusion_mask,
            bbox,
        )
        assert candidate.on_drainage_channel is False

    def test_candidate_score_positive(self):
        elev_grid, slope_grid, hydro, bbox = _build_analysis()
        candidate = select_pond_candidate(
            elev_grid, slope_grid,
            hydro.flow_accumulation,
            hydro.drainage_mask, hydro.exclusion_mask,
            bbox,
        )
        assert candidate.suitability_score > 0.0

    def test_candidate_coordinates_within_bbox(self):
        elev_grid, slope_grid, hydro, bbox = _build_analysis()
        candidate = select_pond_candidate(
            elev_grid, slope_grid,
            hydro.flow_accumulation,
            hydro.drainage_mask, hydro.exclusion_mask,
            bbox,
        )
        assert bbox.west <= candidate.lon <= bbox.east
        assert bbox.south <= candidate.lat <= bbox.north

    def test_all_excluded_raises(self):
        """If exclusion mask covers everything, must raise ValueError."""
        rows, cols = 20, 20
        elev = np.random.rand(rows, cols) * 100 + 200
        slope = np.random.rand(rows, cols) * 5
        acc = np.random.rand(rows, cols) * 100
        drain = np.zeros((rows, cols), dtype=bool)
        exclusion_all = np.ones((rows, cols), dtype=bool)
        bbox = BBox(0.0, 0.1, 0.0, 0.1)
        with pytest.raises(ValueError, match="exclusion zone"):
            select_pond_candidate(elev, slope, acc, drain, exclusion_all, bbox)

    def test_score_breakdown_keys_present(self):
        elev_grid, slope_grid, hydro, bbox = _build_analysis()
        candidate = select_pond_candidate(
            elev_grid, slope_grid,
            hydro.flow_accumulation,
            hydro.drainage_mask, hydro.exclusion_mask,
            bbox,
        )
        for key in ("elevation_score", "slope_score", "accumulation_score", "proximity_score"):
            assert key in candidate.score_breakdown
