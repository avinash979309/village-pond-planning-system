"""
OSM water body fetcher.

Queries OpenStreetMap Overpass API for real water bodies (rivers, lakes,
reservoirs, etc.) within a bounding box and rasterises them onto the
analysis grid as an exclusion mask.

Why this module exists
----------------------
When a KML contour map contains no explicit water feature geometry (Case B),
terrain-derived drainage gives a flow network but cannot know about
actual rivers and water bodies. The D8 algorithm will naturally place
the pond candidate at the lowest flat area — which may be the river bed.

This module fetches authoritative water body polygons from OSM and marks
every grid cell that overlaps a water body as excluded, so that
select_pond_candidate() never picks a location inside a real river or lake.

Design principles
-----------------
- Graceful degradation: if the network call fails or times out, the module
  returns an empty (all-False) mask and logs a warning. The pipeline continues
  without OSM data rather than crashing.
- No hardcoding: bbox is derived from the uploaded KML, so any input map
  triggers the appropriate OSM query.
- Offline-safe: the function accepts an optional ``skip_osm`` flag so tests
  and air-gapped environments can bypass the network call.
- Buffer: water body cells are dilated by ``buffer_cells`` so candidates
  cannot be placed on the river bank either.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from app.geo.utils import BBox, coords_to_grid_index

logger = logging.getLogger(__name__)

# Overpass API mirrors tried in order (fastest/most reliable first)
_OVERPASS_MIRRORS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

# Timeout per mirror in seconds (bbox water queries are heavier than test pings)
_OVERPASS_TIMEOUT = 30

# Overpass QL query template:
# Fetches all waterway polygons, natural water, and reservoir landuse
# that intersect the bounding box.
_QUERY_TEMPLATE = """
[out:json][timeout:25];
(
  way["natural"="water"]({south},{west},{north},{east});
  way["waterway"~"river|stream|canal|drain"]({south},{west},{north},{east});
  way["landuse"="reservoir"]({south},{west},{north},{east});
);
out geom;
"""


# ── Output ─────────────────────────────────────────────────────────────────────

@dataclass
class OSMWaterResult:
    """
    Result of the OSM water body query.

    Attributes
    ----------
    found : bool
        True if at least one water body polygon was found.
    water_mask : np.ndarray (bool, rows × cols)
        True for every grid cell that overlaps a real water body (after buffer).
    feature_count : int
        Number of OSM elements returned.
    feature_names : list of str
        Names of detected water bodies (for logging / response metadata).
    source : str
        "osm", "skipped", or "failed"
    warning : str or None
        Set if the query failed or was skipped.
    """
    found: bool = False
    water_mask: Optional[np.ndarray] = None
    feature_count: int = 0
    feature_names: List[str] = field(default_factory=list)
    source: str = "skipped"
    warning: Optional[str] = None


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_osm_water_mask(
    bbox: BBox,
    grid_shape: tuple,
    buffer_cells: int = 3,
    skip_osm: bool = False,
) -> OSMWaterResult:
    """
    Fetch OSM water body polygons and rasterise onto the analysis grid.

    Parameters
    ----------
    bbox : BBox
        Bounding box from the uploaded KML (WGS84).
    grid_shape : (rows, cols)
        Shape of the elevation/hydrology grid.
    buffer_cells : int
        Number of grid cells to dilate around each water body. Prevents
        pond candidate from being placed right on the river bank.
    skip_osm : bool
        If True, skip the network call and return an empty result.
        Used in tests and offline environments.

    Returns
    -------
    OSMWaterResult
    """
    rows, cols = grid_shape
    empty_mask = np.zeros((rows, cols), dtype=bool)

    if skip_osm:
        return OSMWaterResult(
            found=False,
            water_mask=empty_mask,
            source="skipped",
            warning="OSM query skipped (skip_osm=True).",
        )

    # Build Overpass query
    query = _QUERY_TEMPLATE.format(
        south=bbox.south,
        west=bbox.west,
        north=bbox.north,
        east=bbox.east,
    )

    import httpx
    data = None
    last_exc: Exception = RuntimeError("No mirrors tried")
    for mirror_url in _OVERPASS_MIRRORS:
        try:
            response = httpx.post(
                mirror_url,
                data={"data": query},
                timeout=_OVERPASS_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            logger.debug("OSM query succeeded via %s", mirror_url)
            break
        except Exception as exc:
            logger.debug("OSM mirror %s failed: %s", mirror_url, exc)
            last_exc = exc
            continue

    if data is None:
        logger.warning("All OSM mirrors failed. Last error: %s. Continuing without OSM water mask.", last_exc)
        return OSMWaterResult(
            found=False,
            water_mask=empty_mask,
            source="failed",
            warning=f"OSM query failed (all mirrors): {last_exc}. Results may include water body cells.",
        )

    elements = data.get("elements", [])
    if not elements:
        return OSMWaterResult(
            found=False,
            water_mask=empty_mask,
            feature_count=0,
            source="osm",
        )

    # Rasterise each element's geometry onto the grid
    water_mask = np.zeros((rows, cols), dtype=bool)
    feature_names: List[str] = []
    rasterised_count = 0

    for elem in elements:
        geometry = elem.get("geometry", [])
        tags = elem.get("tags", {})
        name = tags.get("name", tags.get("waterway", tags.get("natural", "unnamed")))

        # geometry is a list of {lat, lon} dicts for ways
        if not geometry:
            continue

        try:
            coords = [(pt["lon"], pt["lat"]) for pt in geometry if "lon" in pt and "lat" in pt]
            if len(coords) < 2:
                continue

            # Rasterise as filled polygon if closed ring, else as polyline
            _rasterise_feature(coords, bbox, water_mask)
            feature_names.append(name)
            rasterised_count += 1
        except Exception as e:
            logger.debug("Could not rasterise OSM element %s: %s", elem.get("id"), e)
            continue

    if rasterised_count == 0:
        return OSMWaterResult(
            found=False,
            water_mask=empty_mask,
            feature_count=len(elements),
            source="osm",
            warning="OSM returned elements but none could be rasterised onto the grid.",
        )

    # Dilate water mask by buffer_cells
    if buffer_cells > 0:
        from scipy.ndimage import binary_dilation
        struct = np.ones((2 * buffer_cells + 1, 2 * buffer_cells + 1), dtype=bool)
        water_mask = binary_dilation(water_mask, structure=struct)

    return OSMWaterResult(
        found=bool(water_mask.any()),
        water_mask=water_mask,
        feature_count=rasterised_count,
        feature_names=list(set(feature_names)),
        source="osm",
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _rasterise_feature(
    coords: list,
    bbox: BBox,
    mask: np.ndarray,
) -> None:
    """
    Paint all grid cells touched by a polygon or polyline onto the mask.

    For closed polygons (first == last coord): fills interior using
    a scanline approach via shapely.
    For open polylines (rivers as ways): marks cells along each segment.

    This is intentionally simple (grid-cell resolution) — sub-cell
    accuracy is unnecessary given the grid is ~15–50 m per cell.
    """
    rows, cols = mask.shape
    is_closed = len(coords) >= 4 and coords[0] == coords[-1]

    if is_closed:
        # Use shapely to fill polygon interior
        try:
            from shapely.geometry import Polygon
            poly = Polygon(coords)
            if not poly.is_valid:
                poly = poly.buffer(0)
            _fill_polygon_on_mask(poly, bbox, mask)
            return
        except Exception:
            pass  # Fall through to polyline approach

    # Polyline: mark all cells along each segment
    for i in range(len(coords) - 1):
        lon0, lat0 = coords[i]
        lon1, lat1 = coords[i + 1]
        _draw_line_on_mask(lon0, lat0, lon1, lat1, bbox, mask)


def _fill_polygon_on_mask(poly, bbox: BBox, mask: np.ndarray) -> None:
    """Mark all grid cells whose centres fall inside the polygon."""
    from shapely.geometry import Point

    rows, cols = mask.shape
    min_lon, min_lat, max_lon, max_lat = poly.bounds

    # Clamp to bbox
    col_lo = max(0, int((min_lon - bbox.west) / bbox.lon_range * cols) - 1)
    col_hi = min(cols - 1, int((max_lon - bbox.west) / bbox.lon_range * cols) + 1)
    row_lo = max(0, int((bbox.north - max_lat) / bbox.lat_range * rows) - 1)
    row_hi = min(rows - 1, int((bbox.north - min_lat) / bbox.lat_range * rows) + 1)

    for r in range(row_lo, row_hi + 1):
        lat = bbox.north - (r + 0.5) * bbox.lat_range / rows
        for c in range(col_lo, col_hi + 1):
            lon = bbox.west + (c + 0.5) * bbox.lon_range / cols
            if poly.contains(Point(lon, lat)):
                mask[r, c] = True


def _draw_line_on_mask(
    lon0: float, lat0: float,
    lon1: float, lat1: float,
    bbox: BBox,
    mask: np.ndarray,
) -> None:
    """Mark all grid cells along a line segment (Bresenham-style)."""
    rows, cols = mask.shape
    from app.geo.utils import coords_to_grid_index

    r0, c0 = coords_to_grid_index(lon0, lat0, bbox, (rows, cols))
    r1, c1 = coords_to_grid_index(lon1, lat1, bbox, (rows, cols))

    # Bresenham line
    dr = abs(r1 - r0)
    dc = abs(c1 - c0)
    sr = 1 if r0 < r1 else -1
    sc = 1 if c0 < c1 else -1
    err = dr - dc

    r, c = r0, c0
    steps = 0
    max_steps = dr + dc + 1

    while steps <= max_steps:
        if 0 <= r < rows and 0 <= c < cols:
            mask[r, c] = True
        if r == r1 and c == c1:
            break
        e2 = 2 * err
        if e2 > -dc:
            err -= dc
            r += sr
        if e2 < dr:
            err += dr
            c += sc
        steps += 1
