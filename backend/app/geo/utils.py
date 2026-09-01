"""
Geospatial utility functions shared across geo modules.

These utilities handle coordinate transformations, distance calculations,
and grid/raster helper operations. They do NOT contain business logic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np


# ── BBox dataclass ────────────────────────────────────────────────────────────

@dataclass
class BBox:
    """Axis-aligned bounding box in WGS84 (EPSG:4326)."""
    west: float   # min longitude
    east: float   # max longitude
    south: float  # min latitude
    north: float  # max latitude

    @property
    def lon_range(self) -> float:
        return self.east - self.west

    @property
    def lat_range(self) -> float:
        return self.north - self.south

    @property
    def center_lon(self) -> float:
        return (self.west + self.east) / 2.0

    @property
    def center_lat(self) -> float:
        return (self.south + self.north) / 2.0

    def to_dict(self) -> dict:
        return {
            "west": self.west,
            "east": self.east,
            "south": self.south,
            "north": self.north,
        }


# ── UTM zone selection ────────────────────────────────────────────────────────

def utm_epsg_for_bbox(bbox: BBox) -> int:
    """
    Return the EPSG code for the UTM zone covering the centre of the bbox.

    Used for projected-area calculations. Covers both hemispheres.

    Algorithm:
    - UTM zone number = floor((lon + 180) / 6) + 1
    - Northern hemisphere zones: 32600 + zone_number (EPSG)
    - Southern hemisphere zones: 32700 + zone_number (EPSG)
    """
    lon = bbox.center_lon
    lat = bbox.center_lat
    zone_number = int((lon + 180.0) / 6.0) + 1
    # Clamp to valid UTM range 1–60
    zone_number = max(1, min(60, zone_number))
    if lat >= 0:
        return 32600 + zone_number  # WGS84 / UTM Zone N
    else:
        return 32700 + zone_number  # WGS84 / UTM Zone S


# ── Approximate cell size in metres ──────────────────────────────────────────

def approx_cell_size_m(bbox: BBox, grid_shape: Tuple[int, int]) -> Tuple[float, float]:
    """
    Return approximate (lon_cell_m, lat_cell_m) for a regular WGS84 grid.

    Uses the standard approximation:
    - 1 degree latitude  ≈ 110 540 m
    - 1 degree longitude ≈ 111 320 * cos(lat) m

    Parameters
    ----------
    bbox : BBox
    grid_shape : (rows, cols)

    Returns
    -------
    (lon_cell_m, lat_cell_m) – width and height of one grid cell in metres
    """
    rows, cols = grid_shape
    lat_m_per_deg = 110_540.0
    lon_m_per_deg = 111_320.0 * math.cos(math.radians(bbox.center_lat))
    lat_cell_m = (bbox.lat_range / rows) * lat_m_per_deg
    lon_cell_m = (bbox.lon_range / cols) * lon_m_per_deg
    return lon_cell_m, lat_cell_m


# ── Grid index ↔ coordinates ──────────────────────────────────────────────────

def grid_index_to_coords(row: int, col: int, bbox: BBox, grid_shape: Tuple[int, int]) -> Tuple[float, float]:
    """
    Convert (row, col) grid indices to (lon, lat) WGS84 coordinates.

    Row 0 = northernmost row, col 0 = westernmost column.
    Returns the centre of the grid cell.
    """
    rows, cols = grid_shape
    lon = bbox.west + (col + 0.5) * bbox.lon_range / cols
    lat = bbox.north - (row + 0.5) * bbox.lat_range / rows
    return lon, lat


def coords_to_grid_index(lon: float, lat: float, bbox: BBox, grid_shape: Tuple[int, int]) -> Tuple[int, int]:
    """
    Convert (lon, lat) WGS84 coordinates to nearest (row, col) grid indices.

    Returns clamped indices (never out of bounds).
    """
    rows, cols = grid_shape
    col = int((lon - bbox.west) / bbox.lon_range * cols)
    row = int((bbox.north - lat) / bbox.lat_range * rows)
    col = max(0, min(cols - 1, col))
    row = max(0, min(rows - 1, row))
    return row, col


# ── Haversine distance ────────────────────────────────────────────────────────

def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Great-circle distance in metres between two WGS84 points.
    Accuracy: <0.5% for distances under ~1000 km.
    """
    R = 6_371_000.0  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ── Normalisation helpers ─────────────────────────────────────────────────────

def normalise_01(arr: np.ndarray) -> np.ndarray:
    """
    Linearly scale an array to [0, 1].
    Returns zeros if all values are identical (prevents division by zero).
    """
    lo, hi = float(np.nanmin(arr)), float(np.nanmax(arr))
    if hi == lo:
        return np.zeros_like(arr, dtype=np.float64)
    return (arr - lo) / (hi - lo)


def invert_normalise_01(arr: np.ndarray) -> np.ndarray:
    """Normalise and invert so that the smallest value maps to 1."""
    return 1.0 - normalise_01(arr)
