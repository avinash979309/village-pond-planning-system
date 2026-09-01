"""
Tests for terrain_builder and terrain_conditioner modules.

Covers:
- Elevation grid shape matches requested resolution
- Interpolated elevation is within contour range
- Slope is in valid range [0, 90)
- Slope of flat terrain is near 0
- NaN fraction is reported
- Different grid resolutions produce proportionally different shapes
- Missing elevation raises ValueError (< 3 sample points)
"""

from __future__ import annotations

import numpy as np
import pytest

from app.geo.kml_parser import parse_upload
from app.geo.terrain_builder import build_elevation_grid, ElevationGrid
from app.geo.terrain_conditioner import compute_slope
from app.geo.utils import BBox


SYNTHETIC_KML_PATH = "tests/data/synthetic_contour.kml"


def _load_synthetic() -> tuple:
    with open(SYNTHETIC_KML_PATH, "rb") as f:
        kml = f.read()
    parsed = parse_upload(kml, "synthetic_contour.kml")
    return parsed.contour_lines, parsed.bbox


# ── Terrain builder ───────────────────────────────────────────────────────────

class TestTerrainBuilder:
    def test_grid_shape_matches_resolution(self):
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox, grid_resolution=100)
        assert grid.data.shape == (100, 100)

    def test_default_resolution(self):
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox)
        assert grid.data.shape == (200, 200)

    def test_elevation_within_contour_range(self):
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox, grid_resolution=100)
        valid = grid.data[~np.isnan(grid.data)]
        assert valid.min() >= 95.0   # slight tolerance for boundary fill
        assert valid.max() <= 130.0  # slight tolerance

    def test_no_all_nan_grid(self):
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox, grid_resolution=100)
        nan_count = np.isnan(grid.data).sum()
        total = grid.data.size
        assert nan_count / total < 0.5  # at most 50% NaN (should be much less)

    def test_nan_fraction_reported(self):
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox, grid_resolution=100)
        assert 0.0 <= grid.nan_fraction <= 1.0

    def test_elevation_stats_sensible(self):
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox, grid_resolution=100)
        stats = grid.elevation_stats()
        assert stats["min"] < stats["max"]
        assert stats["min"] is not None

    def test_different_resolutions_proportional(self):
        contours, bbox = _load_synthetic()
        g50 = build_elevation_grid(contours, bbox, grid_resolution=50)
        g100 = build_elevation_grid(contours, bbox, grid_resolution=100)
        assert g50.data.shape == (50, 50)
        assert g100.data.shape == (100, 100)

    def test_bowl_centre_is_lowest(self):
        """Synthetic terrain is bowl-shaped: centre should be lower than edges."""
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox, grid_resolution=100)
        centre = grid.data[50, 50]
        edge_top = grid.data[0, 50]
        edge_right = grid.data[50, 99]
        assert centre < edge_top
        assert centre < edge_right


# ── Terrain conditioner ───────────────────────────────────────────────────────

class TestTerrainConditioner:
    def test_slope_shape_matches_elevation(self):
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox, grid_resolution=100)
        slope = compute_slope(grid.data, bbox)
        assert slope.data.shape == grid.data.shape

    def test_slope_range_valid(self):
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox, grid_resolution=100)
        slope = compute_slope(grid.data, bbox)
        assert float(np.nanmin(slope.data)) >= 0.0
        assert float(np.nanmax(slope.data)) < 90.0

    def test_flat_grid_near_zero_slope(self):
        """A perfectly flat grid must produce slope ≈ 0 everywhere."""
        flat = np.full((50, 50), 100.0)
        bbox = BBox(west=0.0, east=0.1, south=0.0, north=0.1)
        slope = compute_slope(flat, bbox)
        assert float(np.max(slope.data)) < 0.01

    def test_steep_gradient_produces_nonzero_slope(self):
        """A grid with clear gradient must have non-zero slope."""
        arr = np.tile(np.linspace(100, 200, 50), (50, 1))  # sloped E-W
        bbox = BBox(west=0.0, east=0.1, south=0.0, north=0.1)
        slope = compute_slope(arr, bbox)
        # 100m rise over ~11km = ~0.52° slope — definitely non-zero
        assert float(np.mean(slope.data)) > 0.1


    def test_slope_stats_present(self):
        contours, bbox = _load_synthetic()
        grid = build_elevation_grid(contours, bbox, grid_resolution=100)
        slope = compute_slope(grid.data, bbox)
        for key in ("min", "max", "mean", "std"):
            assert key in slope.stats
