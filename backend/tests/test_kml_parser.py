"""
Tests for kml_parser module.

Covers:
- Valid KML parsing (real-structure and synthetic)
- KMZ extraction and parsing
- Malformed XML handling
- Missing elevation (non-numeric names)
- Empty coordinate handling
- BBox correctness
- Contour interval detection
- Non-contour feature collection
- Water feature name collection in other_features
"""

from __future__ import annotations

import io
import zipfile

import pytest

from app.geo.kml_parser import parse_upload, ContourLine, ParsedKML

# ── Fixtures ──────────────────────────────────────────────────────────────────

SYNTHETIC_KML_PATH = "tests/data/synthetic_contour.kml"


def _load_synthetic_kml() -> bytes:
    with open(SYNTHETIC_KML_PATH, "rb") as f:
        return f.read()


def _make_minimal_kml(placemarks: str) -> bytes:
    """Build a minimal valid KML with the given Placemark XML."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Folder>
    <name>Test</name>
    {placemarks}
  </Folder>
</kml>""".encode()


def _make_kmz(kml_bytes: bytes) -> bytes:
    """Wrap KML bytes in a KMZ (ZIP) archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("doc.kml", kml_bytes)
    return buf.getvalue()


# ── Tests: valid KML ──────────────────────────────────────────────────────────

class TestValidKML:
    def test_synthetic_kml_parses(self):
        kml = _load_synthetic_kml()
        result = parse_upload(kml, "synthetic_contour.kml")
        assert isinstance(result, ParsedKML)

    def test_contour_line_count(self):
        kml = _load_synthetic_kml()
        result = parse_upload(kml, "synthetic_contour.kml")
        assert len(result.contour_lines) == 6  # 100,105,110,115,120,125m

    def test_elevation_range(self):
        kml = _load_synthetic_kml()
        result = parse_upload(kml, "synthetic_contour.kml")
        assert result.elevation_range[0] == pytest.approx(100.0)
        assert result.elevation_range[1] == pytest.approx(125.0)

    def test_contour_interval_detected(self):
        kml = _load_synthetic_kml()
        result = parse_upload(kml, "synthetic_contour.kml")
        assert result.contour_interval_m == pytest.approx(5.0)

    def test_bbox_valid(self):
        kml = _load_synthetic_kml()
        result = parse_upload(kml, "synthetic_contour.kml")
        assert result.bbox is not None
        assert result.bbox.west < result.bbox.east
        assert result.bbox.south < result.bbox.north

    def test_contour_lines_have_coordinates(self):
        kml = _load_synthetic_kml()
        result = parse_upload(kml, "synthetic_contour.kml")
        for cl in result.contour_lines:
            assert len(cl.coordinates) >= 2
            for lon, lat in cl.coordinates:
                assert -180 <= lon <= 180
                assert -90 <= lat <= 90

    def test_minimal_single_contour(self):
        kml = _make_minimal_kml("""
            <Placemark>
              <name>250.0</name>
              <LineString>
                <coordinates>10.0,20.0 10.1,20.1 10.2,20.0</coordinates>
              </LineString>
            </Placemark>
        """)
        result = parse_upload(kml, "test.kml")
        assert len(result.contour_lines) == 1
        assert result.contour_lines[0].elevation_m == 250.0

    def test_non_numeric_names_go_to_other_features(self):
        kml = _make_minimal_kml("""
            <Placemark>
              <name>river</name>
              <LineString>
                <coordinates>10.0,20.0 10.1,20.1</coordinates>
              </LineString>
            </Placemark>
            <Placemark>
              <name>300.0</name>
              <LineString>
                <coordinates>10.0,20.0 10.1,20.1 10.2,20.0</coordinates>
              </LineString>
            </Placemark>
        """)
        result = parse_upload(kml, "test.kml")
        assert len(result.contour_lines) == 1
        assert any(f.name == "river" for f in result.other_features)

    def test_polygon_goes_to_other_features(self):
        kml = _make_minimal_kml("""
            <Placemark>
              <name>land</name>
              <Polygon>
                <outerBoundaryIs>
                  <LinearRing>
                    <coordinates>10.0,20.0 11.0,20.0 11.0,21.0 10.0,21.0 10.0,20.0</coordinates>
                  </LinearRing>
                </outerBoundaryIs>
              </Polygon>
            </Placemark>
            <Placemark>
              <name>100.0</name>
              <LineString>
                <coordinates>10.2,20.2 10.3,20.3 10.4,20.2</coordinates>
              </LineString>
            </Placemark>
        """)
        result = parse_upload(kml, "test.kml")
        assert any(f.geometry_type == "Polygon" for f in result.other_features)


# ── Tests: KMZ ───────────────────────────────────────────────────────────────

class TestKMZ:
    def test_valid_kmz_parses(self):
        kml = _load_synthetic_kml()
        kmz = _make_kmz(kml)
        result = parse_upload(kmz, "test.kmz")
        assert len(result.contour_lines) == 6

    def test_kmz_elevation_same_as_kml(self):
        kml = _load_synthetic_kml()
        kmz = _make_kmz(kml)
        r_kml = parse_upload(kml, "test.kml")
        r_kmz = parse_upload(kmz, "test.kmz")
        assert r_kml.elevation_range == r_kmz.elevation_range
        assert len(r_kml.contour_lines) == len(r_kmz.contour_lines)


# ── Tests: error cases ────────────────────────────────────────────────────────

class TestErrors:
    def test_unsupported_extension_raises(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            parse_upload(b"data", "map.shp")

    def test_malformed_kml_raises(self):
        with pytest.raises(ValueError, match="Malformed KML"):
            parse_upload(b"<not valid xml>>><<", "bad.kml")

    def test_no_contours_raises(self):
        kml = _make_minimal_kml("""
            <Placemark>
              <name>some_label</name>
              <Point><coordinates>10,20</coordinates></Point>
            </Placemark>
        """)
        with pytest.raises(ValueError, match="No contour features"):
            parse_upload(kml, "no_contours.kml")

    def test_bad_kmz_raises(self):
        with pytest.raises(ValueError, match="not a valid KMZ"):
            parse_upload(b"this is not a zip file", "fake.kmz")
