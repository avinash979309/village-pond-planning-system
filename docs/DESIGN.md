# Design Document

## AI-based Village Pond Planning System

**Version:** 1.0  
**Date:** 2026-08-10  

---

## 1. Core Domain Concepts

### 1.1 Digital Elevation Model (DEM)

A DEM is a gridded representation of terrain elevation. Each cell (pixel) represents the ground elevation at that point.

- **Source:** SRTM (Shuttle Radar Topography Mission)
- **Resolution:** ~30 meters (1 arc-second)
- **Format:** GeoTIFF
- **Coordinate System:** WGS84 (EPSG:4326)

### 1.2 Contour Lines

Contour lines connect points of equal elevation. They provide a visual representation of terrain shape.

- **Generation:** Extracted from DEM grid using marching squares algorithm
- **Interval:** Configurable (e.g., 5m, 10m) depending on terrain relief
- **Output:** GeoJSON LineString features with elevation attribute

### 1.3 Slope

Slope is the gradient of the elevation surface, representing how steep the terrain is.

- **Calculation:** `slope = arctan(√(dz/dx² + dz/dy²))` where dz/dx and dz/dy are partial derivatives
- **Units:** Degrees (0° = flat, 90° = vertical cliff)
- **Relevance:** Flat to gently sloping areas (0-5°) are most suitable for ponds

### 1.4 Flow Direction (D8 Algorithm)

The D8 (Deterministic 8-neighbor) algorithm assigns each DEM cell a flow direction toward its steepest downslope neighbor.

```
32 | 64 | 128
---+----+---
16 |  X |  1
---+----+---
 8 |  4 |  2
```

Each cell gets one of 8 direction values. This creates a drainage network.

### 1.5 Flow Accumulation

Flow accumulation counts how many upstream cells drain through each cell. High values indicate stream channels.

### 1.6 Catchment (Watershed) Area

A catchment is the area of land where all rainfall drains to a single point (the "pour point" or "outlet"). It is delineated by tracing flow direction upstream from the pour point.

- **Algorithm:** Starting from pour point, recursively find all cells whose flow direction points toward cells already in the catchment.
- **Library:** pysheds handles this efficiently.

### 1.7 SCS Curve Number Method

The SCS-CN method estimates direct surface runoff from rainfall.

**Core equations (SI units, mm):**

```
Q = (P - Ia)² / (P - Ia + S)      when P > Ia, else Q = 0

S = (25400 / CN) - 254             potential maximum retention (mm)

Ia = 0.2 × S                       initial abstraction (mm)
```

**Parameters:**
- `P` = rainfall depth (mm)
- `Q` = runoff depth (mm)  
- `CN` = Curve Number (0-100)
- `S` = potential maximum retention (mm)
- `Ia` = initial abstraction (mm)

**Curve Number selection:**

| Land Use | Soil Group A | Soil Group B | Soil Group C | Soil Group D |
|----------|:----------:|:----------:|:----------:|:----------:|
| Forest | 25 | 55 | 70 | 77 |
| Grassland/Pasture | 39 | 61 | 74 | 80 |
| Agricultural (row crops) | 67 | 78 | 85 | 89 |
| Residential (low density) | 51 | 68 | 79 | 84 |
| Barren/Wasteland | 77 | 86 | 91 | 94 |
| Water/Wetland | 100 | 100 | 100 | 100 |

For this prototype, a default CN will be assumed based on typical Indian rural land use, with the option for the user to adjust it.

### 1.8 Pond Sizing

**Depth estimation:**
- Consider: available runoff, terrain slope, typical pond depths
- Typical range: 2-5 meters for village ponds
- Steeper slopes → shallower ponds, flatter areas → deeper ponds

**Storage capacity:**
- Simplified: V = A × d × f
  - V = volume (m³)
  - A = surface area (m²)
  - d = depth (m)
  - f = shape factor (0.33 for conical, 0.5 for trapezoidal, 1.0 for rectangular)
- More accurate: trapezoidal cross-section with side slopes

**Surface area estimation:**
- Given target volume and depth: A = V / (d × f)

### 1.9 Suitability Scoring

Multi-criteria weighted scoring:

```
Score = w₁·f₁(slope) + w₂·f₂(drainage) + w₃·f₃(elevation) + w₄·f₄(land) + w₅·f₅(catchment)
```

| Factor | Weight | Score Function | Ideal |
|--------|--------|----------------|-------|
| Slope | 0.30 | 1.0 if <3°, linear decrease to 0 at 15° | Flat |
| Drainage position | 0.25 | Based on flow accumulation (normalized) | High flow accumulation |
| Relative elevation | 0.15 | Low-lying areas score higher | Valley, not ridge |
| Land availability | 0.20 | 1.0 if available, 0.0 if not | Available |
| Catchment area | 0.10 | Larger catchment → more runoff → higher score | Large catchment |

---

## 2. API Design

### 2.1 Village Endpoints

```
GET    /api/v1/villages
  Response: { villages: [{ id, name, state, district, lat, lng }] }

GET    /api/v1/villages/{id}
  Response: { village: { id, name, state, district, lat, lng, boundary? } }
```

### 2.2 Analysis Endpoints

```
POST   /api/v1/analysis
  Body: {
    latitude: float,
    longitude: float,
    radius_km: float (default: 2.0),
    curve_number: float (optional, default: 75),
    land_geojson: GeoJSON (optional)
  }
  Response: { analysis_id: string, status: "processing" }

GET    /api/v1/analysis/{id}
  Response: { analysis: { id, status, location, results... } }

GET    /api/v1/analysis/{id}/terrain
  Response: { 
    elevation: { min, max, mean, range },
    slope: { mean, max, distribution },
    contours_geojson: GeoJSON FeatureCollection
  }

GET    /api/v1/analysis/{id}/catchment
  Response: {
    boundary_geojson: GeoJSON Polygon,
    area_sq_km: float,
    pour_point: { lat, lng },
    avg_elevation: float
  }

GET    /api/v1/analysis/{id}/rainfall
  Response: {
    annual_avg_mm: float,
    monthly_avg_mm: [float × 12],
    period: { start, end },
    source: "Open-Meteo"
  }

GET    /api/v1/analysis/{id}/runoff
  Response: {
    method: "SCS-CN",
    curve_number: float,
    annual_runoff_mm: float,
    annual_runoff_volume_m3: float,
    runoff_coefficient: float
  }

GET    /api/v1/analysis/{id}/recommendation
  Response: {
    candidates: [{
      location: { lat, lng },
      suitability_score: float,
      score_breakdown: { slope, drainage, elevation, land, catchment },
      pond: {
        depth_m: float,
        surface_area_m2: float,
        storage_capacity_m3: float,
        shape: string
      },
      catchment_area_km2: float,
      annual_runoff_m3: float,
      rainfall_mm: float
    }]
  }
```

---

## 3. Frontend Component Design

### 3.1 Layout Structure

```
┌────────────────────────────────────────────────────────┐
│                    HEADER                               │
│  🌊 Village Pond Planning System                       │
├──────────────┬─────────────────────────────────────────┤
│              │                                         │
│  SIDEBAR     │            MAP AREA                     │
│              │                                         │
│  ┌────────┐  │   ┌─────────────────────────────────┐   │
│  │Village │  │   │                                 │   │
│  │Selector│  │   │       Interactive Map            │   │
│  └────────┘  │   │       (Leaflet + Overlays)       │   │
│              │   │                                 │   │
│  ┌────────┐  │   │  [Satellite] [Street] [Terrain]  │   │
│  │Analysis│  │   │                                 │   │
│  │Controls│  │   │  Contours ✓  Catchment ✓        │   │
│  └────────┘  │   │  Candidates ✓  Land ✓           │   │
│              │   │                                 │   │
│  ┌────────┐  │   └─────────────────────────────────┘   │
│  │Results │  │                                         │
│  │Panel   │  ├─────────────────────────────────────────┤
│  │        │  │         ANALYSIS SUMMARY                │
│  │Terrain │  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌───────┐  │
│  │Rainfall│  │  │Elev. │ │Rain  │ │Runoff│ │Pond   │  │
│  │Runoff  │  │  │Stats │ │Chart │ │Est.  │ │Sizing │  │
│  │Pond    │  │  └──────┘ └──────┘ └──────┘ └───────┘  │
│  │Sizing  │  │                                         │
│  └────────┘  │                                         │
├──────────────┴─────────────────────────────────────────┤
│                    FOOTER                               │
└────────────────────────────────────────────────────────┘
```

### 3.2 Component Hierarchy

```
App
├── Header
├── MainLayout
│   ├── Sidebar
│   │   ├── VillageSearch
│   │   ├── CoordinateInput
│   │   ├── AnalysisPanel (controls)
│   │   └── AnalysisResults
│   │       ├── TerrainMetrics
│   │       ├── RainfallChart
│   │       ├── RunoffSummary
│   │       └── PondRecommendation
│   ├── MapContainer
│   │   ├── SatelliteLayer
│   │   ├── ContourLayer
│   │   ├── CatchmentLayer
│   │   ├── LandAvailabilityLayer
│   │   ├── PondLocationMarker(s)
│   │   └── AnalysisOverlay
│   └── AnalysisSummaryBar
└── Footer
```

### 3.3 State Management

For this prototype, React's built-in state management (useState, useContext) is sufficient.

**Key state:**
- `selectedVillage: Village | null`
- `selectedLocation: { lat, lng } | null`
- `analysisId: string | null`
- `analysisStatus: 'idle' | 'loading' | 'completed' | 'error'`
- `analysisResults: AnalysisResults | null`
- `mapLayers: { contours: boolean, catchment: boolean, land: boolean, candidates: boolean }`

---

## 4. Folder Structure (Complete)

```
Assignment_1/
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── RULES.md
│   ├── PHASES.md
│   ├── DESIGN.md
│   ├── MEMORY.md
│   ├── LEARN.md
│   └── DECISIONS.md
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py
│   │   │       ├── villages.py
│   │   │       └── analysis.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── village.py
│   │   │   ├── analysis.py
│   │   │   ├── terrain.py
│   │   │   └── rainfall.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── village_service.py
│   │   │   ├── analysis_service.py
│   │   │   ├── rainfall_service.py
│   │   │   └── dem_service.py
│   │   ├── geo/
│   │   │   ├── __init__.py
│   │   │   ├── dem_processor.py
│   │   │   ├── contour_generator.py
│   │   │   ├── slope_analyzer.py
│   │   │   ├── catchment_analyzer.py
│   │   │   ├── runoff_estimator.py
│   │   │   ├── pond_sizer.py
│   │   │   ├── land_suitability.py
│   │   │   └── utils.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py
│   │   │   └── repositories.py
│   │   └── external/
│   │       ├── __init__.py
│   │       ├── open_meteo.py
│   │       └── dem_fetcher.py
│   ├── data/
│   │   ├── dem/
│   │   ├── geojson/
│   │   └── sample/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_dem_processor.py
│   │   ├── test_contour.py
│   │   ├── test_catchment.py
│   │   ├── test_runoff.py
│   │   ├── test_pond_sizer.py
│   │   └── test_api.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   ├── VillageSelector/
│   │   │   ├── Analysis/
│   │   │   └── Layout/
│   │   ├── services/
│   │   ├── types/
│   │   ├── hooks/
│   │   ├── utils/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── .gitignore
├── README.md
└── CSD_Assignment_1.pdf
```

---

## 5. Demo Data Strategy

For demonstration, the system will include pre-configured data for 2-3 sample Indian villages:

| Village | State | ~Lat | ~Lng | Notes |
|---------|-------|------|------|-------|
| Ralegan Siddhi | Maharashtra | 18.91 | 74.25 | Famous for water conservation (Anna Hazare) |
| Hiware Bazar | Maharashtra | 19.45 | 75.32 | Water harvesting success story |
| Custom | Any | User input | User input | User can enter any coordinates |

These are selected because:
1. They are real villages with known water conservation relevance
2. They have varying terrain (semi-arid, hilly)
3. SRTM DEM coverage is available
4. They tell a meaningful story for the project's purpose

Sample land availability GeoJSON files will be created for these villages, clearly documented as **demo data, not verified government records**.

---

## 6. Key Algorithms Summary

| Algorithm | Module | Input | Output | Method |
|-----------|--------|-------|--------|--------|
| Sink Filling | dem_processor | Raw DEM | Hydrologically conditioned DEM | Priority-flood (pysheds) |
| Contour Generation | contour_generator | DEM grid | GeoJSON lines | Marching squares |
| Slope Calculation | slope_analyzer | DEM grid | Slope grid (degrees) | Gradient magnitude |
| Flow Direction | catchment_analyzer | Conditioned DEM | Flow direction grid | D8 algorithm |
| Flow Accumulation | catchment_analyzer | Flow direction grid | Accumulation grid | Upstream cell counting |
| Catchment Delineation | catchment_analyzer | Flow dir + pour point | Catchment mask | Recursive upstream trace |
| Runoff Estimation | runoff_estimator | Rainfall + CN | Runoff depth (mm) | SCS Curve Number |
| Pond Sizing | pond_sizer | Runoff vol + terrain | Depth, area, volume | Geometric formulas |
| Suitability Scoring | land_suitability | Multiple factors | Score (0-1) | Weighted MCDA |
