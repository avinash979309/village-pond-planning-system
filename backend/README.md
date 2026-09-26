# Village Pond Planning System — Backend

## Phase 2: Contour Map → Terrain → Catchment API

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
# .\venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env as needed (MongoDB optional for Phase 2)

# 4. Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

---

## Phase 2 API Endpoint

### `POST /api/v1/contour/analyze-contour`

Accepts a KML or KMZ contour map and returns catchment analysis.

**Request:** `multipart/form-data`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | file | ✅ | — | `.kml` or `.kmz` contour map |
| `grid_resolution` | int | ❌ | 200 | Grid cells per axis for interpolation (50–1000) |
| `drainage_threshold_pct` | float | ❌ | 2.0 | Top N% flow accumulation = drainage channel |
| `drainage_buffer_cells` | int | ❌ | 2 | Exclusion buffer around drainage (grid cells) |
| `snap_radius_cells` | int | ❌ | 5 | Pour-point snap search radius (grid cells) |

**Example with curl:**

```bash
curl -X POST http://localhost:8000/api/v1/contour/analyze-contour \
  -F "file=@../maps/sample_contour_map.kml" \
  -F "grid_resolution=200" \
  -F "drainage_threshold_pct=2.0"
```

**Response 200:**

```json
{
  "status": "success",
  "data": {
    "input_summary": {
      "filename": "sample_contour_map.kml",
      "file_format": "kml",
      "contour_line_count": 1355,
      "elevation_range_m": { "min_m": 267.0, "max_m": 298.0 },
      "spatial_extent": { "west": 81.281, "east": 81.313, "south": 21.240, "north": 21.264 },
      "contour_interval_m": 1.0,
      "explicit_water_features_found": false,
      "explicit_water_feature_count": 0
    },
    "terrain": {
      "grid_resolution": 200,
      "grid_shape": [200, 200],
      "interpolation_method": "linear+nearest_fill",
      "cell_size_approx_m": [16.2, 13.2],
      "elevation_stats": { "min": 267.0, "max": 298.0, "mean": 282.3, "std": 6.1 }
    },
    "drainage": {
      "method": "terrain_derived",
      "drainage_threshold_pct": 2.0,
      "drainage_cells_count": 80,
      "exclusion_buffer_cells": 2,
      "note": "Drainage network derived from D8 flow accumulation. Not verified river data."
    },
    "pond_candidate": {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [81.294, 21.251] },
      "properties": {
        "elevation_m": 270.5,
        "slope_degrees": 1.2,
        "flow_accumulation": 320.0,
        "suitability_score": 0.74,
        "score_breakdown": {
          "elevation_score": 0.81,
          "slope_score": 0.90,
          "accumulation_score": 0.65,
          "proximity_score": 0.60
        },
        "on_drainage_channel": false,
        "exclusion_zone_respected": true
      }
    },
    "pour_point": {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [81.295, 21.250] },
      "properties": {
        "snap_distance_m": 120.0,
        "flow_accumulation": 510.0,
        "note": "Snapped to nearest drainage cell within search radius."
      }
    },
    "catchment": {
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [[[...]]]} ,
      "properties": {
        "area_sq_km": 1.45,
        "area_sq_m": 1450000.0,
        "avg_elevation_m": 283.1,
        "cell_count": 960,
        "projection_used": "EPSG:32644"
      }
    },
    "methodology": {
      "contour_interpolation": "scipy.griddata — linear triangulation + nearest-neighbour boundary fill",
      "flow_direction_algorithm": "D8 (deterministic 8-direction, pysheds)",
      "catchment_delineation": "pysheds upstream tracing from pour point",
      "area_calculation_projection": "UTM EPSG:32644 (projected, not lat/lon)",
      "drainage_derivation": "terrain_derived",
      "candidate_scoring": "weighted multi-factor: elevation + slope + flow_accumulation + proximity_to_drainage",
      "weights": { "elevation": 0.2, "slope": 0.3, "accumulation": 0.3, "proximity": 0.2 }
    }
  },
  "message": "Contour analysis complete.",
  "errors": []
}
```

**Error Response (400):**
```json
{
  "detail": {
    "status": "error",
    "data": null,
    "message": "Unsupported file type '.shp'. Upload a .kml or .kmz file.",
    "errors": [{ "field": "file", "message": "Unsupported file type '.shp'. Upload a .kml or .kmz file." }]
  }
}
```

---

## Running Tests

```bash
cd backend
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_kml_parser.py -v
pytest tests/test_terrain_builder.py -v
pytest tests/test_hydrology.py -v
pytest tests/test_contour_api.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI application
│   ├── config.py                        # Environment configuration
│   ├── api/v1/
│   │   ├── router.py                    # Route aggregation
│   │   └── contour.py                   # POST /analyze-contour route
│   ├── models/
│   │   └── contour.py                   # Pydantic schemas
│   ├── services/
│   │   └── contour_analysis_service.py  # Pipeline orchestration
│   └── geo/                             # Geospatial processing modules
│       ├── utils.py                     # Shared utilities (BBox, UTM, etc.)
│       ├── kml_parser.py                # KML/KMZ → structured features
│       ├── water_feature_detector.py    # Explicit water feature detection
│       ├── terrain_builder.py           # Contour lines → elevation grid
│       ├── terrain_conditioner.py       # Slope analysis
│       ├── hydrology_engine.py          # D8 flow direction + accumulation
│       ├── pond_candidate_selector.py   # Weighted suitability scoring
│       └── catchment_delineator.py      # Pour point snap + catchment polygon
├── tests/
│   ├── data/
│   │   └── synthetic_contour.kml        # Synthetic bowl terrain (unit test only)
│   ├── test_kml_parser.py
│   ├── test_terrain_builder.py
│   ├── test_hydrology.py
│   └── test_contour_api.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## Methodology

### Contour → Elevation Grid

1. Parse contour `LineString` features from KML; elevation = numeric `<name>` value.
2. Sample up to 50 points per contour polyline (arc-length uniform sampling).
3. Build irregular point cloud `(lon, lat, elevation)`.
4. `scipy.griddata(points, elevations, grid, method='linear')` — Delaunay triangulation.
5. NaN boundary cells filled with `method='nearest'`.

### Drainage Derivation

**Case B (this sample):** No explicit water geometry in KML.
- D8 flow direction (pysheds, after pit/depression fill + flat resolution).
- Flow accumulation grid.
- Top 2% cells by accumulation = drainage channel.
- Buffer = 2 cells (configurable).

**Case A:** If explicit water/river features detected by name, folder, or blue style colour.

### Pond Candidate Selection

Weighted scoring (all values derived from input — no hardcoding):

| Factor | Weight | Direction |
|--------|--------|-----------|
| Relative elevation | 0.20 | Lower = better |
| Slope | 0.30 | Flatter = better |
| Flow accumulation | 0.30 | Higher = better (95th-pct capped) |
| Proximity to drainage | 0.20 | Near channel = better |

Drainage + buffer cells → score set to 0 → never selected.

### Catchment Delineation

1. Snap pond candidate to nearest high-accumulation drainage cell (pour point).
2. `pysheds.grid.catchment(x=pour_lon, y=pour_lat, fdir=fdir, xytype='coordinate')`.
3. `rasterio.features.shapes` → GeoJSON Polygon.
4. Project to UTM (auto-selected) → area in m²/km².

---

## Limitations

- Elevation accuracy bounded by contour interval (1m for sample).
- Terrain assumes linear slope between contours.
- Derived drainage ≠ verified river boundaries.
- Grid at 200×200 ≈ 17m/cell resolution for sample map.
- No MongoDB persistence in Phase 2 (results returned in response only).

---

## Technology

FastAPI + pysheds + scipy + rasterio + shapely + pyproj + lxml
