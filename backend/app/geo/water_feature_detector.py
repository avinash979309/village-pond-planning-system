"""
Explicit water / river feature detector.

Scans the OtherFeature list from ParsedKML and classifies any features
that appear to represent water bodies or drainage channels.

Two cases are handled
---------------------
Case A — Feature is explicitly named or styled as water:
    Returns a WaterFeatureResult with the detected geometries.

Case B — No explicit water feature found:
    Returns a WaterFeatureResult with found=False.
    The hydrology engine will derive drainage from terrain in this case.

Design principle
----------------
This module must NOT hardcode any sample-specific names or coordinates.
It searches for water indicators generically across all input features.
Detection uses multiple independent signals:
    1. Feature name contains a water keyword.
    2. Enclosing folder name contains a water keyword.
    3. KML style colour is blue-dominant (KML uses AABBGGRR).
    4. Feature geometry type is Polygon AND name/folder suggests water.

At least ONE strong signal (name or folder keyword) OR
two weak signals (colour + context) are required for detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.geo.kml_parser import OtherFeature, WATER_KEYWORDS


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class WaterFeatureResult:
    """
    Result of explicit water feature detection.

    Attributes
    ----------
    found : bool
        True if at least one probable water feature was identified.
    features : list of detected OtherFeature
    all_coordinates : flat list of (lon, lat) from all detected features
    detection_signals : human-readable list of detection reasons (for response metadata)
    """
    found: bool = False
    features: List[OtherFeature] = field(default_factory=list)
    all_coordinates: List[Tuple[float, float]] = field(default_factory=list)
    detection_signals: List[str] = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────

def detect_water_features(other_features: List[OtherFeature]) -> WaterFeatureResult:
    """
    Scan non-contour KML features for water / river / drainage indicators.

    Parameters
    ----------
    other_features : list of OtherFeature
        Produced by kml_parser.parse_upload().

    Returns
    -------
    WaterFeatureResult
    """
    detected: List[OtherFeature] = []
    signals: List[str] = []

    for feat in other_features:
        feature_signals: List[str] = []

        # Signal 1 — name keyword
        if feat.name and _contains_water_keyword(feat.name):
            feature_signals.append(f"name '{feat.name}' matches water keyword")

        # Signal 2 — folder keyword
        if feat.folder_name and _contains_water_keyword(feat.folder_name):
            feature_signals.append(f"folder '{feat.folder_name}' matches water keyword")

        # Signal 3 — blue-dominant style colour (KML: AABBGGRR hex)
        blue_colors = [c for c in feat.style_colors if _is_blue_dominant(c)]
        if blue_colors:
            feature_signals.append(f"style colour is blue-dominant ({blue_colors[0]})")

        # Detection threshold:
        # - Any name/folder keyword → definite water feature
        # - Only colour hint with Polygon geometry → probable water
        name_or_folder_match = any(
            "name" in s or "folder" in s for s in feature_signals
        )
        colour_plus_polygon = blue_colors and feat.geometry_type == "Polygon"

        if name_or_folder_match or colour_plus_polygon:
            detected.append(feat)
            signals.extend(feature_signals)

    if not detected:
        return WaterFeatureResult(found=False)

    all_coords: List[Tuple[float, float]] = []
    for feat in detected:
        all_coords.extend(feat.coordinates)

    return WaterFeatureResult(
        found=True,
        features=detected,
        all_coordinates=all_coords,
        detection_signals=list(set(signals)),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _contains_water_keyword(text: str) -> bool:
    """Return True if text (lowercased) contains any water-related keyword."""
    low = text.lower()
    return any(kw in low for kw in WATER_KEYWORDS)


def _is_blue_dominant(kml_color: str) -> bool:
    """
    Check if a KML colour string is blue-dominant.

    KML colour format: AABBGGRR (8 hex chars, alpha-blue-green-red).
    Blue-dominant means BB component > RR and BB > GG.

    Also handles CSS-style '#RRGGBB' or 'rgb(...)' if present.
    """
    cleaned = kml_color.strip().lstrip("#")
    if len(cleaned) == 8:
        # KML AABBGGRR
        try:
            alpha = int(cleaned[0:2], 16)  # noqa: F841
            blue = int(cleaned[2:4], 16)
            green = int(cleaned[4:6], 16)
            red = int(cleaned[6:8], 16)
            return blue > red and blue > green and blue > 100
        except ValueError:
            return False
    if len(cleaned) == 6:
        # CSS RRGGBB
        try:
            red = int(cleaned[0:2], 16)
            green = int(cleaned[2:4], 16)
            blue = int(cleaned[4:6], 16)
            return blue > red and blue > green and blue > 100
        except ValueError:
            return False
    return False
