# System Architecture

## AI-based Village Pond Planning System

**Version:** 1.0  
**Date:** 2026-08-10  
**Status:** Draft — Awaiting Review  

---

## 1. System Architecture Overview

The system follows a **modular monolithic** architecture with clear separation between frontend, backend API, geospatial processing, and data storage.

```
┌──────────────────────────────────────────────┐
│                   Browser                     │
│  ┌──────────────────────────────────────────┐ │
│  │         React + TypeScript Frontend       │ │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────┐ │ │
│  │  │ Map     │  │ Analysis │  │ Village │ │ │
│  │  │ (Leaflet│  │ Panel    │  │ Selector│ │ │
│  │  │ + React │  │          │  │         │ │ │
│  │  │ Leaflet)│  │          │  │         │ │ │
│  │  └─────────┘  └──────────┘  └─────────┘ │ │
│  └──────────────────────────────────────────┘ │
└──────────────────┬───────────────────────────┘
                   │ REST/JSON (HTTP)
                   ▼
┌──────────────────────────────────────────────┐
│            FastAPI Backend (Python)            │
│  ┌──────────────────────────────────────────┐ │
│  │              API Router Layer              │ │
│  │  /api/v1/villages  /api/v1/analysis       │ │
│  └─────────────┬────────────────────────────┘ │
│                │                               │
│  ┌─────────────▼────────────────────────────┐ │
│  │           Service Layer                    │ │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────┐ │ │
│  │  │ Village  │ │ Analysis  │ │ External │ │ │
│  │  │ Service  │ │ Service   │ │ API Svc  │ │ │
│  │  └──────────┘ └───────────┘ └──────────┘ │ │
│  └─────────────┬────────────────────────────┘ │
│                │                               │
│  ┌─────────────▼────────────────────────────┐ │
│  │      Geospatial Processing Engine          │ │
│  │  ┌──────┐ ┌────────┐ ┌────────┐          │ │
│  │  │ DEM  │ │Catchmnt│ │Runoff  │          │ │
│  │  │Procsr│ │Analysr │ │Estimtr │          │ │
│  │  └──────┘ └────────┘ └────────┘          │ │
│  │  ┌──────┐ ┌────────┐ ┌────────┐          │ │
│  │  │Contour││ Slope  │ │ Pond   │          │ │
│  │  │Genratr││Analysr │ │ Sizer  │          │ │
│  │  └──────┘ └────────┘ └────────┘          │ │
│  └──────────────────────────────────────────┘ │
└──────┬───────────────────┬───────────────────┘
       │                   │
       ▼                   ▼
┌──────────────┐   ┌───────────────────────────┐
│   MongoDB    │   │    External APIs / Data    │
│  ┌────────┐  │   │  ┌─────────────────────┐  │
│  │Villages│  │   │  │Open-Meteo (Rainfall)│  │
│  │Analyses│  │   │  │OpenTopography (DEM) │  │
│  │Results │  │   │  │Esri/OSM (Map Tiles) │  │
│  └────────┘  │   │  └─────────────────────┘  │
└──────────────┘   └───────────────────────────┘
       │
┌──────▼───────┐
│  Filesystem  │
│  ┌────────┐  │
│  │DEM     │  │
│  │Rasters │  │
│  │GeoJSON │  │
│  └────────┘  │
└──────────────┘
```

---

## 2. Component Architecture

### 2.1 Frontend Architecture

**Framework:** React + TypeScript + Vite  
**Map Library:** React-Leaflet / Leaflet  
**Styling:** Tailwind CSS  

```
frontend/
├── src/
│   ├── components/
│   │   ├── Map/
│   │   │   ├── MapContainer.tsx          # Main map wrapper
│   │   │   ├── SatelliteLayer.tsx        # Esri satellite tile layer
│   │   │   ├── ContourLayer.tsx          # Elevation contour overlay
│   │   │   ├── CatchmentLayer.tsx        # Catchment area polygon
│   │   │   ├── PondLocationMarker.tsx    # Candidate pond marker
│   │   │   ├── LandAvailabilityLayer.tsx # Land suitability overlay
│   │   │   └── AnalysisOverlay.tsx       # Combined analysis overlay
│   │   ├── VillageSelector/
│   │   │   ├── VillageSearch.tsx         # Search/select village
│   │   │   └── CoordinateInput.tsx       # Manual coordinate entry
│   │   ├── Analysis/
│   │   │   ├── AnalysisPanel.tsx         # Main analysis controls
│   │   │   ├── AnalysisResults.tsx       # Results display
│   │   │   ├── TerrainMetrics.tsx        # Elevation/slope stats
│   │   │   ├── RainfallChart.tsx         # Rainfall data viz
│   │   │   ├── RunoffSummary.tsx         # Runoff estimation display
│   │   │   └── PondRecommendation.tsx    # Pond sizing results
│   │   └── Layout/
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── Footer.tsx
│   ├── services/
│   │   └── api.ts                        # API client functions
│   ├── types/
│   │   └── index.ts                      # TypeScript interfaces
│   ├── hooks/
│   │   ├── useAnalysis.ts
│   │   └── useVillage.ts
│   ├── utils/
│   │   └── formatters.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

### 2.2 Backend Architecture

**Framework:** FastAPI + Uvicorn  
**Validation:** Pydantic v2  
**Database:** Motor (async MongoDB driver)  

```
backend/
├── app/
│   ├── main.py                          # FastAPI application entry
│   ├── config.py                        # Environment & configuration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py               # API router aggregation
│   │   │   ├── villages.py             # Village endpoints
│   │   │   └── analysis.py            # Analysis endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── village.py                   # Village Pydantic models
│   │   ├── analysis.py                  # Analysis Pydantic models
│   │   ├── terrain.py                   # Terrain data models
│   │   └── rainfall.py                  # Rainfall data models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── village_service.py           # Village CRUD operations
│   │   ├── analysis_service.py          # Analysis orchestration
│   │   ├── rainfall_service.py          # Open-Meteo API integration
│   │   └── dem_service.py               # DEM data acquisition
│   ├── geo/
│   │   ├── __init__.py
│   │   ├── dem_processor.py             # DEM loading, preprocessing
│   │   ├── contour_generator.py         # Elevation contour extraction
│   │   ├── slope_analyzer.py            # Slope calculation
│   │   ├── catchment_analyzer.py        # Watershed delineation
│   │   ├── runoff_estimator.py          # SCS-CN runoff estimation
│   │   ├── pond_sizer.py               # Pond depth & capacity estimation
│   │   ├── land_suitability.py          # Land suitability scoring
│   │   └── utils.py                     # Geospatial utility functions
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py                # MongoDB connection
│   │   └── repositories.py             # Data access layer
│   └── external/
│       ├── __init__.py
│       ├── open_meteo.py                # Open-Meteo API client
│       └── dem_fetcher.py               # DEM tile fetcher
├── data/
│   ├── dem/                             # Cached DEM raster files
│   ├── geojson/                         # Land/parcel GeoJSON layers
│   └── sample/                          # Sample/demo data
├── tests/
│   ├── test_dem_processor.py
│   ├── test_catchment.py
│   ├── test_runoff.py
│   └── test_api.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 3. Data Flow

### 3.1 Analysis Pipeline Data Flow

```
User selects village/location
        │
        ▼
┌─ Frontend ──────────────────────────────────┐
│ POST /api/v1/analysis                        │
│ Body: { lat, lng, radius, land_geojson? }    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─ Backend: Analysis Service ─────────────────┐
│                                              │
│  1. Validate input coordinates               │
│  2. Create analysis record in MongoDB        │
│  3. Fetch DEM data (OpenTopography / cached) │
│  4. Process DEM:                             │
│     a. Fill sinks                            │
│     b. Calculate flow direction              │
│     c. Calculate flow accumulation           │
│     d. Generate contours                     │
│     e. Calculate slope                       │
│  5. Identify land suitability                │
│  6. Delineate catchment area                 │
│  7. Fetch rainfall data (Open-Meteo)         │
│  8. Estimate runoff (SCS-CN method)          │
│  9. Size pond (depth, capacity)              │
│ 10. Score and rank candidate locations       │
│ 11. Store results in MongoDB                 │
│ 12. Return analysis ID + results             │
│                                              │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─ Frontend ──────────────────────────────────┐
│ Display results on map:                      │
│  - Contour lines                             │
│  - Catchment boundary (polygon)              │
│  - Candidate pond locations (markers)        │
│  - Land availability overlay                 │
│  - Analysis metrics panel                    │
└─────────────────────────────────────────────┘
```

### 3.2 External API Data Flow

```
┌─ DEM Acquisition ──────────────────────────┐
│                                             │
│  Check cache (filesystem) → if cached, use  │
│                            → if not:        │
│     OpenTopography API                      │
│       GET /globaldem?demtype=SRTMGL1        │
│       &south=X&north=X&west=X&east=X       │
│     → Download GeoTIFF to data/dem/         │
│     → Return file path                      │
│                                             │
└─────────────────────────────────────────────┘

┌─ Rainfall Acquisition ─────────────────────┐
│                                             │
│  Open-Meteo Historical Weather API          │
│  GET /v1/archive                            │
│    ?latitude=X&longitude=X                  │
│    &start_date=YYYY-MM-DD                   │
│    &end_date=YYYY-MM-DD                     │
│    &daily=precipitation_sum                 │
│  → Parse JSON response                      │
│  → Aggregate annual statistics              │
│  → Cache in MongoDB                         │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 4. Database Design

### 4.1 MongoDB Collections

#### `villages`
```json
{
  "_id": "ObjectId",
  "name": "string",
  "state": "string",
  "district": "string",
  "latitude": "float",
  "longitude": "float",
  "boundary": "GeoJSON Polygon (optional)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `analyses`
```json
{
  "_id": "ObjectId",
  "village_id": "ObjectId (optional)",
  "location": {
    "latitude": "float",
    "longitude": "float"
  },
  "radius_km": "float",
  "status": "string (pending|processing|completed|failed)",
  "created_at": "datetime",
  "completed_at": "datetime",
  
  "terrain": {
    "dem_source": "string",
    "resolution_m": "float",
    "elevation_range": { "min": "float", "max": "float" },
    "avg_slope_degrees": "float",
    "contours_geojson": "string (file path)",
    "slope_stats": {}
  },
  
  "catchment": {
    "area_sq_km": "float",
    "boundary_geojson": "GeoJSON Polygon",
    "pour_point": { "lat": "float", "lng": "float" },
    "avg_elevation_m": "float"
  },
  
  "rainfall": {
    "source": "Open-Meteo",
    "period": { "start": "date", "end": "date" },
    "annual_avg_mm": "float",
    "monthly_avg_mm": ["float"],
    "annual_totals": {}
  },
  
  "runoff": {
    "method": "SCS-CN",
    "curve_number": "float",
    "annual_runoff_volume_m3": "float",
    "runoff_coefficient": "float",
    "assumptions": {}
  },
  
  "pond_recommendation": {
    "location": { "lat": "float", "lng": "float" },
    "recommended_depth_m": "float",
    "surface_area_sq_m": "float",
    "storage_capacity_m3": "float",
    "shape": "string",
    "suitability_score": "float",
    "factors": {}
  },
  
  "land_suitability": {
    "suitable_areas_geojson": "GeoJSON",
    "criteria": {},
    "source_description": "string"
  }
}
```

#### `rainfall_cache`
```json
{
  "_id": "ObjectId",
  "latitude": "float",
  "longitude": "float",
  "period_start": "date",
  "period_end": "date",
  "daily_data": [],
  "fetched_at": "datetime"
}
```

### 4.2 Storage Strategy

| Data Type | Storage | Reason |
|-----------|---------|--------|
| Village metadata | MongoDB | Small structured data, query-friendly |
| Analysis results | MongoDB | Structured, linked to villages |
| Rainfall cache | MongoDB | Query by coordinates, moderate size |
| DEM raster files | Filesystem (`data/dem/`) | Large binary files, rasterio reads from disk |
| Contour GeoJSON | Filesystem (`data/geojson/`) | Can be large, referenced by path |
| Land GeoJSON input | Filesystem (`data/geojson/`) | User-supplied, variable size |

---

## 5. External APIs

| API | Purpose | Auth | Rate Limit | Fallback |
|-----|---------|------|------------|----------|
| Open-Meteo Historical Weather | Rainfall data | None (free) | ~10,000/day | Cache aggressively |
| OpenTopography Global DEM | SRTM elevation data | Free API key | 200/day academic | Cache DEM tiles |
| Open-Meteo Elevation API | Point elevation queries | None (free) | High | OpenTopography |
| Esri World Imagery | Satellite map tiles | None (attribution req.) | Standard tile limits | OpenStreetMap tiles |
| OpenStreetMap/Carto | Base map tiles | None | Standard tile limits | — |

---

## 6. Geospatial Processing Architecture

### 6.1 Processing Modules

```
geo/
├── dem_processor.py
│   ├── load_dem(filepath) → numpy array
│   ├── fill_sinks(dem) → filled DEM
│   ├── get_elevation_at(dem, lat, lng) → float
│   └── clip_to_bounds(dem, bbox) → clipped DEM
│
├── contour_generator.py
│   ├── generate_contours(dem, interval) → GeoJSON
│   └── contour_to_geojson(contours) → FeatureCollection
│
├── slope_analyzer.py
│   ├── calculate_slope(dem) → slope array
│   ├── classify_slope(slope) → categories
│   └── slope_statistics(slope, mask) → stats dict
│
├── catchment_analyzer.py
│   ├── compute_flow_direction(dem) → flow dir grid
│   ├── compute_flow_accumulation(flow_dir) → accumulation grid
│   ├── delineate_catchment(flow_dir, pour_point) → catchment mask
│   ├── catchment_to_polygon(mask) → GeoJSON Polygon
│   └── calculate_catchment_area(polygon) → float (km²)
│
├── runoff_estimator.py
│   ├── estimate_curve_number(land_use, soil_type) → CN
│   ├── calculate_runoff_depth(rainfall_mm, CN) → mm
│   ├── calculate_runoff_volume(depth, area) → m³
│   └── annual_runoff(monthly_rainfall, CN, area) → m³
│
├── pond_sizer.py
│   ├── recommend_depth(terrain_slope, soil_type) → m
│   ├── calculate_storage(depth, area) → m³
│   ├── optimal_dimensions(volume, depth) → dict
│   └── estimate_surface_area(volume, depth, shape) → m²
│
└── land_suitability.py
    ├── score_terrain(slope, elevation) → 0-1
    ├── score_drainage(flow_accum, distance_to_stream) → 0-1
    ├── check_land_availability(geojson_layer, point) → bool
    ├── composite_score(terrain, drainage, land) → 0-1
    └── identify_candidate_sites(scores, threshold) → list
```

### 6.2 Key Libraries and Their Roles

| Library | Role |
|---------|------|
| **rasterio** | Read/write GeoTIFF DEM files, coordinate transforms |
| **numpy** | Array operations on DEM grids, slope calculations |
| **pysheds** | Flow direction, flow accumulation, watershed delineation |
| **scipy** | Contour generation (ndimage), interpolation |
| **shapely** | Geometric operations (polygons, areas, intersections) |
| **geopandas** | GeoJSON handling, spatial joins, area calculations |
| **pyproj** | Coordinate system transformations |
| **opencv-python** | Image processing for DEM visualization (if needed) |

---

## 7. API Communication

### 7.1 REST API Structure

All APIs under `/api/v1/` prefix. JSON request/response format.

### 7.2 Response Format

```json
{
  "status": "success | error",
  "data": { ... },
  "message": "Human-readable message",
  "errors": []
}
```

### 7.3 Error Response Format

```json
{
  "status": "error",
  "data": null,
  "message": "Descriptive error message",
  "errors": [
    {
      "field": "latitude",
      "message": "Must be between -90 and 90"
    }
  ]
}
```

---

## 8. Error Handling Architecture

### 8.1 Error Categories

| Category | HTTP Code | Example |
|----------|-----------|---------|
| Validation Error | 422 | Invalid coordinates |
| Not Found | 404 | Village/analysis not found |
| External API Error | 502 | Open-Meteo unavailable |
| Processing Error | 500 | DEM processing failure |
| Timeout | 504 | Analysis took too long |
| Rate Limited | 429 | Too many API requests |

### 8.2 Error Handling Strategy

```
Request → Validation (Pydantic) → Service → Processing → Response
             ↓ fail                  ↓ fail      ↓ fail
          ValidationError        ServiceError  ProcessingError
             ↓                      ↓              ↓
          422 response           appropriate     500 response
                                 HTTP code        + logged
```

---

## 9. Security Considerations

1. **Environment variables** for all sensitive configuration (`.env` + `python-dotenv`)
2. **Pydantic validation** on all incoming data
3. **CORS** configured for specific frontend origin only
4. **No secrets in Git** — `.gitignore` includes `.env`, `data/`, `__pycache__/`
5. **Input sanitization** — validate coordinates, file types, sizes
6. **Rate limiting** (optional for prototype)

---

## 10. Scalability Considerations

For this academic prototype:

1. **Caching:** DEM tiles and rainfall data cached to reduce external API calls
2. **Async processing:** FastAPI async endpoints for non-blocking I/O
3. **Analysis by area:** Limit max analysis area to prevent excessive processing
4. **Result persistence:** Store analysis results in MongoDB for retrieval without recomputation

Production-scale considerations (documented but not implemented):
- Task queue (Celery/Redis) for long-running analyses
- Object storage (S3) for DEM files
- CDN for map tiles
- Horizontal scaling of processing workers

---

## 11. Technology Stack Summary

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend Framework | React | 18.x |
| Frontend Language | TypeScript | 5.x |
| Build Tool | Vite | 5.x |
| Map Library | Leaflet + React-Leaflet | 1.9 / 4.x |
| CSS Framework | Tailwind CSS | 3.x |
| Backend Framework | FastAPI | 0.110+ |
| Backend Language | Python | 3.11+ |
| ASGI Server | Uvicorn | 0.30+ |
| Database | MongoDB | 7.x |
| MongoDB Driver | Motor (async) | 3.x |
| DEM Processing | rasterio | 1.3+ |
| Watershed Analysis | pysheds | 0.4+ |
| Geospatial | geopandas, shapely, pyproj | Latest stable |
| Numerical | numpy, scipy | Latest stable |
| Image Processing | opencv-python | 4.x |
| Validation | Pydantic | 2.x |
| HTTP Client | httpx | 0.27+ |
