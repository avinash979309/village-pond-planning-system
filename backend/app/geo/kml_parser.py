"""
KML / KMZ parser for contour maps.

Responsibilities
----------------
- Parse .kml files and .kmz archives (ZIP-wrapped KML).
- Extract contour LineString features with their elevation values.
- Collect non-contour features (Points, Polygons, other named features)
  for downstream water-feature detection.
- Compute the bounding box of all contour geometry.
- Derive the minimum contour interval from unique elevation values.

What this module does NOT do
-----------------------------
- Classify water or drainage features (→ water_feature_detector.py).
- Perform any terrain analysis (→ terrain_builder.py, hydrology_engine.py).

Design note
-----------
KML/KMZ parsing is intentionally isolated so that future DEM-based input
can skip this step entirely and feed a grid directly into the terrain
pipeline at terrain_builder.py.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from lxml import etree

from app.geo.utils import BBox

# KML namespace
_KML_NS = "http://www.opengis.net/kml/2.2"
_TAG = lambda local: f"{{{_KML_NS}}}{local}"  # noqa: E731

# Water-related keywords for feature classification (used by detector)
WATER_KEYWORDS = frozenset({
    "river", "stream", "nala", "nadi", "canal", "lake", "pond",
    "reservoir", "waterbody", "water", "drain", "drainage",
    "jheel", "talab", "kund",
})


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ContourLine:
    """A single contour line with its elevation."""
    elevation_m: float
    coordinates: List[Tuple[float, float]]  # list of (lon, lat)


@dataclass
class LabelPoint:
    """A point label feature (typically contour elevation labels)."""
    name: str
    lon: float
    lat: float


@dataclass
class OtherFeature:
    """
    Any non-contour Placemark in the KML.

    Preserved so water_feature_detector.py can scan names, styles,
    and geometry types without re-parsing the KML.
    """
    name: Optional[str]
    folder_name: Optional[str]
    geometry_type: str           # "LineString" | "Point" | "Polygon" | "MultiGeometry"
    style_colors: List[str]      # raw KML color strings found in style elements
    coordinates: List[Tuple[float, float]]  # representative coordinate list


@dataclass
class ParsedKML:
    """Structured result of parsing a KML/KMZ contour file."""
    contour_lines: List[ContourLine] = field(default_factory=list)
    label_points: List[LabelPoint] = field(default_factory=list)
    other_features: List[OtherFeature] = field(default_factory=list)
    bbox: Optional[BBox] = None
    elevation_range: Tuple[float, float] = (0.0, 0.0)   # (min, max) metres
    unique_elevations: List[float] = field(default_factory=list)
    contour_interval_m: Optional[float] = None           # min gap between sorted unique elevations


# ── Public API ────────────────────────────────────────────────────────────────

def parse_upload(file_bytes: bytes, filename: str) -> ParsedKML:
    """
    Parse uploaded KML or KMZ bytes into a ParsedKML structure.

    Parameters
    ----------
    file_bytes : bytes
        Raw bytes of the uploaded file.
    filename : str
        Original filename (used only to determine format; no logic branches
        on the actual name, only on the extension).

    Returns
    -------
    ParsedKML

    Raises
    ------
    ValueError
        If the file is not a valid KML/KMZ, or contains no contour features.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "kmz":
        kml_bytes = _extract_kml_from_kmz(file_bytes)
    elif ext == "kml":
        kml_bytes = file_bytes
    else:
        raise ValueError(
            f"Unsupported file format '{ext}'. Upload a .kml or .kmz file."
        )
    return _parse_kml_bytes(kml_bytes)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_kml_from_kmz(kmz_bytes: bytes) -> bytes:
    """Extract the first .kml file found inside a KMZ (ZIP) archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(kmz_bytes)) as zf:
            kml_names = [n for n in zf.namelist() if n.lower().endswith(".kml")]
            if not kml_names:
                raise ValueError("KMZ archive contains no .kml file.")
            # Prefer doc.kml (Google Earth convention), else first .kml
            target = next((n for n in kml_names if n.lower() == "doc.kml"), kml_names[0])
            return zf.read(target)
    except zipfile.BadZipFile as exc:
        raise ValueError("File is not a valid KMZ (ZIP) archive.") from exc


def _parse_kml_bytes(kml_bytes: bytes) -> ParsedKML:
    """Parse raw KML bytes and return a ParsedKML."""
    try:
        root = etree.fromstring(kml_bytes)
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"Malformed KML XML: {exc}") from exc

    # Strip namespace prefix for convenience
    _strip_ns(root)

    contour_lines: List[ContourLine] = []
    label_points: List[LabelPoint] = []
    other_features: List[OtherFeature] = []

    # Walk all Placemarks
    for placemark in root.iter("Placemark"):
        name_el = placemark.find("name")
        name_text = (name_el.text or "").strip() if name_el is not None else ""
        folder_name = _parent_folder_name(placemark)

        # Determine elevation from name (numeric names = elevation in metres)
        elevation = _try_parse_float(name_text)

        # Collect style color hints
        style_colors = [
            el.text.strip()
            for el in placemark.iter("color")
            if el.text
        ]

        # ── LineString ───────────────────────────────────────────────────────
        ls_el = placemark.find(".//LineString")
        if ls_el is not None:
            coords = _parse_coordinates(ls_el.find("coordinates"))
            if elevation is not None and coords:
                contour_lines.append(ContourLine(elevation_m=elevation, coordinates=coords))
            elif coords:
                # Named non-contour line feature
                other_features.append(OtherFeature(
                    name=name_text or None,
                    folder_name=folder_name,
                    geometry_type="LineString",
                    style_colors=style_colors,
                    coordinates=coords,
                ))
            continue

        # ── Point ────────────────────────────────────────────────────────────
        pt_el = placemark.find(".//Point")
        if pt_el is not None:
            coords = _parse_coordinates(pt_el.find("coordinates"))
            if coords:
                lon, lat = coords[0]
                if elevation is not None:
                    label_points.append(LabelPoint(name=name_text, lon=lon, lat=lat))
                else:
                    other_features.append(OtherFeature(
                        name=name_text or None,
                        folder_name=folder_name,
                        geometry_type="Point",
                        style_colors=style_colors,
                        coordinates=coords,
                    ))
            continue

        # ── Polygon ──────────────────────────────────────────────────────────
        poly_el = placemark.find(".//Polygon")
        if poly_el is not None:
            outer = poly_el.find(".//outerBoundaryIs//coordinates")
            coords = _parse_coordinates(outer) if outer is not None else []
            other_features.append(OtherFeature(
                name=name_text or None,
                folder_name=folder_name,
                geometry_type="Polygon",
                style_colors=style_colors,
                coordinates=coords,
            ))
            continue

    # ── Validation ────────────────────────────────────────────────────────────
    if not contour_lines:
        raise ValueError(
            "No contour features found in the uploaded file. "
            "Ensure the KML contains LineString placemarks named with numeric elevation values."
        )

    # ── Derived statistics ────────────────────────────────────────────────────
    all_lons: List[float] = []
    all_lats: List[float] = []
    for cl in contour_lines:
        for lon, lat in cl.coordinates:
            all_lons.append(lon)
            all_lats.append(lat)

    bbox = BBox(
        west=min(all_lons),
        east=max(all_lons),
        south=min(all_lats),
        north=max(all_lats),
    )

    elevations = sorted({cl.elevation_m for cl in contour_lines})
    elev_range = (elevations[0], elevations[-1])

    # Contour interval = minimum non-zero gap between consecutive sorted unique elevations
    intervals = [
        elevations[i + 1] - elevations[i]
        for i in range(len(elevations) - 1)
        if elevations[i + 1] - elevations[i] > 0
    ]
    contour_interval = min(intervals) if intervals else None

    return ParsedKML(
        contour_lines=contour_lines,
        label_points=label_points,
        other_features=other_features,
        bbox=bbox,
        elevation_range=elev_range,
        unique_elevations=elevations,
        contour_interval_m=contour_interval,
    )


# ── XML helpers ───────────────────────────────────────────────────────────────

def _strip_ns(root: etree._Element) -> None:
    """
    Remove all XML namespaces from element tags in-place.
    Allows simple tag lookups like root.find("Placemark").

    Skips processing instructions and comments (their .tag is callable in lxml).
    """
    for el in root.iter():
        # lxml processing instructions / comments have callable .tag — skip them
        if callable(el.tag):
            continue
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]



def _try_parse_float(text: str) -> Optional[float]:
    """Return float if text is a valid number, else None."""
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _parse_coordinates(coord_el) -> List[Tuple[float, float]]:
    """
    Parse a KML <coordinates> element into a list of (lon, lat) tuples.

    KML coordinate format: "lon,lat[,alt] lon,lat[,alt] ..."
    Altitude (Z) is ignored — elevation comes from the Placemark name.
    """
    if coord_el is None or not coord_el.text:
        return []
    coords = []
    for token in coord_el.text.strip().split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                coords.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return coords


def _parent_folder_name(el: etree._Element) -> Optional[str]:
    """Walk up the element tree to find the nearest enclosing Folder name."""
    parent = el.getparent()
    while parent is not None:
        if parent.tag in ("Folder", "Document"):
            name_el = parent.find("name")
            if name_el is not None and name_el.text:
                return name_el.text.strip()
        parent = parent.getparent()
    return None
