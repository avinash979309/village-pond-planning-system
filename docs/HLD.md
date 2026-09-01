# HIGH-LEVEL DESIGN (HLD)

## AI-based Village Pond Planning System

**Course:** CSD Lab  
**Assignment:** 1  
**Student:** Avinash  
**Date:** August 10, 2026  
**Version:** 1.0  

---

## 1. Problem Statement and Objectives

### 1.1 Problem Statement

Water conservation is a critical challenge in rural India. Constructing rainwater harvesting ponds at suitable locations is an effective solution, but selecting the right location requires simultaneous analysis of:

- Terrain elevation and slope
- Catchment area and drainage patterns
- Historical rainfall patterns
- Surface runoff volume
- Available government/community land
- Required storage capacity

Currently, village administrators have no accessible tool that integrates these analyses. Manual site selection relies on experience and intuition, which can result in suboptimal placement — ponds built on slopes too steep for water retention, in areas with insufficient catchment, or on land that collects minimal runoff.

### 1.2 Objectives

1. Build a web application that assists village administrators in identifying suitable locations for pond construction.
2. Use publicly available terrain data (SRTM Digital Elevation Model at 30m resolution) for terrain analysis.
3. Use publicly available historical rainfall data (Open-Meteo API) for rainfall estimation.
4. Implement standard hydrological methods (SCS Curve Number) for runoff estimation.
5. Provide interactive map-based visualization with satellite imagery, contour overlays, catchment boundaries, and analysis results.
6. Present analysis clearly enough for a non-technical user and technically enough for academic review.
7. Estimate appropriate pond depth and storage capacity based on available runoff volume.
8. All algorithms and data sources must be transparent and explainable.

---

## 2. System Architecture

### 2.1 Architecture Style

**Modular Monolithic Web Application** — a single backend server, a single frontend application, and one database, with internal modularization by concern.

**Why monolithic:** This is an academic prototype with a single developer. Microservices would add deployment and inter-service communication complexity without any benefit at this scale.

### 2.2 Block Diagram

*This diagram is designed for hand-drawing in a notebook. Draw it as labeled rectangular blocks with directed arrows showing data flow.*

```
                    ┌──────────────────────────────┐
                    │        USER (Browser)         │
                    └──────────────┬───────────────┘
                                   │
                                   │ User interactions
                                   │ (select village, click map,
                                   │  trigger analysis)
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    FRONTEND (React + TypeScript)                  │
│                                                                  │
│  ┌────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │  Village    │  │  Interactive Map  │  │  Analysis Results   │  │
│  │  Selector   │  │  (Leaflet)       │  │  Panel              │  │
│  │            │  │                  │  │                     │  │
│  │ - Search    │  │ - Satellite tiles │  │ - Terrain stats     │  │
│  │ - Coord.   │  │ - Contours       │  │ - Rainfall chart    │  │
│  │   input    │  │ - Catchment      │  │ - Runoff estimate   │  │
│  │            │  │ - Pond markers   │  │ - Pond sizing       │  │
│  │            │  │ - Land overlay   │  │ - Suitability score │  │
│  └────────────┘  └──────────────────┘  └─────────────────────┘  │
│                                                                  │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            │ REST API calls (JSON over HTTP)
                            │ e.g., POST /api/v1/analysis
                            │      GET  /api/v1/analysis/{id}/terrain
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│               BACKEND SERVER (Python + FastAPI)                  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   API LAYER                               │   │
│  │    /api/v1/villages    /api/v1/analysis                   │   │
│  │    Input validation via Pydantic schemas                  │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                  SERVICE LAYER                            │   │
│  │   Village Service ─ Analysis Service ─ Rainfall Service   │   │
│  │                    (orchestration)                         │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │            GEOSPATIAL PROCESSING ENGINE                   │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌───────────────┐  ┌───────────────┐  │   │
│  │  │ DEM         │  │ Catchment     │  │ Runoff        │  │   │
│  │  │ Processor   │  │ Analyzer      │  │ Estimator     │  │   │
│  │  │             │  │               │  │ (SCS-CN)      │  │   │
│  │  │ - load DEM  │  │ - flow dir.   │  │               │  │   │
│  │  │ - fill sinks│  │ - flow accum. │  │ - calc. Q     │  │   │
│  │  │ - clip area │  │ - delineate   │  │ - annual vol. │  │   │
│  │  └─────────────┘  └───────────────┘  └───────────────┘  │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌───────────────┐  ┌───────────────┐  │   │
│  │  │ Contour     │  │ Slope         │  │ Pond          │  │   │
│  │  │ Generator   │  │ Analyzer      │  │ Sizer         │  │   │
│  │  │             │  │               │  │               │  │   │
│  │  │ - extract   │  │ - gradient    │  │ - depth       │  │   │
│  │  │ - to GeoJSON│  │ - classify    │  │ - area        │  │   │
│  │  └─────────────┘  └───────────────┘  │ - capacity    │  │   │
│  │                                       └───────────────┘  │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │ Land Suitability Scorer (Weighted MCDA)             │ │   │
│  │  │ - score terrain, drainage, elevation, land, catchmt │ │   │
│  │  │ - rank candidate sites                              │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└────────┬──────────────────────────────┬──────────────────────────┘
         │                              │
         │                              │  HTTP requests to
         │ Read/Write                   │  external APIs
         ▼                              ▼
┌───────────────────┐    ┌───────────────────────────────────────┐
│                   │    │        EXTERNAL DATA SOURCES          │
│    DATA LAYER     │    │                                       │
│                   │    │  ┌─────────────────────────────────┐  │
│  ┌─────────────┐  │    │  │ Open-Meteo Historical Weather   │  │
│  │  MongoDB    │  │    │  │ API (Rainfall data)              │  │
│  │             │  │    │  │ - Free, no API key               │  │
│  │ - villages  │  │    │  │ - ERA5 reanalysis, 1940+         │  │
│  │ - analyses  │  │    │  └─────────────────────────────────┘  │
│  │ - rainfall  │  │    │                                       │
│  │   cache     │  │    │  ┌─────────────────────────────────┐  │
│  └─────────────┘  │    │  │ OpenTopography API               │  │
│                   │    │  │ (SRTM DEM - elevation data)      │  │
│  ┌─────────────┐  │    │  │ - Free academic API key          │  │
│  │ Filesystem  │  │    │  │ - 30m GeoTIFF tiles              │  │
│  │             │  │    │  └─────────────────────────────────┘  │
│  │ - DEM files │  │    │                                       │
│  │   (GeoTIFF) │  │    │  ┌─────────────────────────────────┐  │
│  │ - Contour   │  │    │  │ Esri World Imagery / OSM         │  │
│  │   GeoJSON   │  │    │  │ (Map tiles - satellite + street) │  │
│  │ - Land      │  │    │  │ - Free with attribution          │  │
│  │   GeoJSON   │  │    │  └─────────────────────────────────┘  │
│  └─────────────┘  │    │                                       │
│                   │    │  ┌─────────────────────────────────┐  │
└───────────────────┘    │  │ Land Availability Data           │  │
                         │  │ (User-supplied GeoJSON)          │  │
                         │  │ - NOT from satellite imagery     │  │
                         │  │ - Input dataset, not derived     │  │
                         │  └─────────────────────────────────┘  │
                         └───────────────────────────────────────┘
```

### 2.3 Simplified Hand-Drawing Guide

To draw the block diagram in your notebook, draw these 5 main blocks connected by arrows:

```
    [1. User / Browser]
           │
           ▼
    [2. Frontend (React + Leaflet)]
           │  REST API (HTTP/JSON)
           ▼
    [3. Backend (FastAPI + Geo Engine)]
          / \
         /   \
        ▼     ▼
 [4. Data]   [5. External APIs]
 MongoDB     Open-Meteo (Rain)
 Filesystem  OpenTopography (DEM)
             Esri/OSM (Map Tiles)
             Land GeoJSON (Input)
```

Inside Block 3 (Backend), show three internal layers:
```
┌─ API Layer (routing + validation) ─┐
├─ Service Layer (orchestration) ─────┤
├─ Geo Processing Engine ────────────┤
│  DEM Processor │ Contour Generator  │
│  Slope Analyzer│ Catchment Analyzer │
│  Runoff Estimator │ Pond Sizer      │
│  Suitability Scorer                 │
└─────────────────────────────────────┘
```

---

## 3. Functional Requirements and Project Workflow

### 3.1 Functional Requirements

*(Extracted directly from the assignment specification)*

| # | Requirement | Implementation Approach |
|---|-------------|------------------------|
| FR-1 | Display satellite imagery for a selected village | Leaflet map with Esri World Imagery tile layer |
| FR-2 | Visualize contour maps | Extract contours from DEM, render as GeoJSON on Leaflet |
| FR-3 | Identify available land suitable for pond excavation | Terrain suitability scoring + land availability GeoJSON input |
| FR-4 | Estimate catchment area contributing runoff | D8 flow direction + watershed delineation using pysheds |
| FR-5 | Query historical rainfall data using public APIs | Open-Meteo Historical Weather API (daily precipitation) |
| FR-6 | Estimate runoff volume using rainfall and catchment | SCS Curve Number method |
| FR-7 | Recommend pond depth and approximate storage capacity | Geometric estimation from runoff volume and terrain |
| FR-8 | Overlay all results on interactive map | Leaflet with multiple GeoJSON overlay layers |

### 3.2 Project Workflow (End-to-End Pipeline)

```
Step 1:  User selects a village or enters coordinates (lat, lng)
             │
Step 2:  System displays satellite/map imagery (Leaflet + Esri tiles)
             │
Step 3:  System fetches DEM data from OpenTopography (or cache)
             │
Step 4:  DEM preprocessing
             ├── Fill sinks (remove artificial depressions)
             ├── Calculate slope (gradient of elevation surface)
             └── Generate contour lines → display on map
             │
Step 5:  User selects (or system suggests) a candidate pond location
             │
Step 6:  Catchment delineation for the selected point
             ├── Compute flow direction (D8 algorithm)
             ├── Compute flow accumulation
             ├── Snap pour point to nearest drainage channel
             └── Delineate upstream catchment area → display boundary on map
             │
Step 7:  Fetch historical rainfall data from Open-Meteo API
             └── Compute annual average and monthly distribution
             │
Step 8:  Estimate runoff volume
             ├── Apply SCS Curve Number method
             ├── Runoff depth (mm) = f(rainfall, CN)
             └── Runoff volume (m³) = runoff depth × catchment area
             │
Step 9:  Estimate pond dimensions
             ├── Recommend depth (based on terrain slope and runoff)
             ├── Calculate surface area (from volume and depth)
             └── Calculate storage capacity (trapezoidal geometry)
             │
Step 10: Score and rank candidate locations
             ├── Suitability score = weighted combination of:
             │   slope, drainage position, relative elevation,
             │   land availability, catchment size
             └── Display ranked candidates on map
             │
Step 11: Display complete analysis overlay on map
             ├── Contour lines
             ├── Catchment boundary polygon
             ├── Candidate pond markers with scores
             ├── Land availability overlay
             └── Analysis summary panel with all metrics
```

### 3.3 Data Classification

It is important to distinguish where each piece of data comes from:

| Data | Source | How Obtained |
|------|--------|--------------|
| Satellite map tiles | Esri World Imagery / OpenStreetMap | Loaded directly by Leaflet in browser (tile server) |
| Elevation (DEM) | SRTM via OpenTopography API | Fetched by backend, cached as GeoTIFF on filesystem |
| Contour lines | Calculated by our system | Extracted from DEM grid using marching squares algorithm |
| Slope | Calculated by our system | Gradient magnitude of DEM surface |
| Flow direction/accumulation | Calculated by our system | D8 algorithm on conditioned DEM (pysheds) |
| Catchment boundary | Calculated by our system | Upstream trace from pour point (pysheds) |
| Rainfall data | Open-Meteo Historical Weather API | Fetched by backend, cached in MongoDB |
| Runoff estimate | Calculated by our system | SCS Curve Number method applied to rainfall + catchment |
| Pond dimensions | Calculated by our system | Geometric formulas applied to runoff volume + terrain |
| Suitability score | Calculated by our system | Weighted multi-criteria scoring |
| Land availability | User-supplied input (GeoJSON) | Uploaded or pre-loaded, NOT derived from satellite imagery |
| Village metadata | Stored in MongoDB | Pre-seeded demo data or user-entered |
| Analysis results | Stored in MongoDB | Persisted after computation |

**Critical distinction:** Satellite imagery does NOT establish land ownership. The system accepts land availability as an external input dataset. For demo purposes, sample GeoJSON data is provided, clearly labeled as demo data.

---

## 4. Technology Stack

### 4.1 Frontend

| Technology | Purpose | Justification |
|-----------|---------|---------------|
| **React 18** | UI framework | Component-based architecture suitable for complex interactive UI; large ecosystem; React-Leaflet integration |
| **TypeScript** | Type-safe JavaScript | Catches type errors at compile time; essential when handling complex geospatial data structures (GeoJSON, coordinates) |
| **Vite** | Build tool & dev server | Faster than Create React App; instant Hot Module Replacement during development |
| **Leaflet** + **React-Leaflet** | Interactive map | Open source; lightweight (~40KB); supports GeoJSON overlays, multiple tile layers, markers, and custom controls |
| **Tailwind CSS** | Styling framework | Utility-first approach enables rapid UI development; responsive by default |

### 4.2 Backend

| Technology | Purpose | Justification |
|-----------|---------|---------------|
| **Python 3.11+** | Backend language | Rich ecosystem for scientific/geospatial computing (numpy, rasterio, scipy); assignment requirement |
| **FastAPI** | Web framework | Automatic API documentation (Swagger); built-in Pydantic validation; async support; modern Python typing |
| **Pydantic v2** | Data validation | Type-safe request/response validation for all API endpoints; prevents invalid data from reaching processing |
| **Uvicorn** | ASGI server | Lightweight async server for FastAPI; suitable for development and prototype deployment |
| **Motor** | MongoDB async driver | Allows non-blocking database operations; integrates with FastAPI's async architecture |
| **httpx** | HTTP client | Async HTTP client for calling external APIs (Open-Meteo, OpenTopography) |

### 4.3 Database

| Technology | Purpose | Justification |
|-----------|---------|---------------|
| **MongoDB** | Document database | Flexible schema suits evolving analysis results; native GeoJSON support for geospatial queries; assignment recommendation |

### 4.4 Geospatial / Scientific Libraries

| Technology | Purpose | Justification |
|-----------|---------|---------------|
| **rasterio** | Read/write GeoTIFF DEM files | Industry standard for raster geospatial data I/O in Python |
| **numpy** | Array operations on DEM grids | Foundation for all numerical operations on elevation data |
| **pysheds** | Watershed delineation | Purpose-built library for D8 flow direction, flow accumulation, and catchment analysis |
| **scipy** | Scientific computing | Contour extraction, interpolation, numerical methods |
| **shapely** | 2D geometric operations | Polygon area calculations, intersection tests, buffering |
| **geopandas** | GeoJSON / vector data handling | Read/write GeoJSON; spatial joins; integrates with shapely |
| **pyproj** | Coordinate transformations | Convert between WGS84 (lat/lng) and projected coordinates (metres) for area calculations |
| **OpenCV** | Image processing | Optional: DEM visualization, morphological operations |

### 4.5 External Data Sources

| Source | Data Provided | Access Method | Authentication |
|--------|--------------|---------------|----------------|
| **Open-Meteo Historical Weather API** | Daily precipitation (mm), 1940–present | REST API: `GET /v1/archive?latitude=X&longitude=X&daily=precipitation_sum&start_date=...&end_date=...` | None (free, no key needed) |
| **OpenTopography** | SRTM GL1 30m DEM (GeoTIFF) | REST API: `GET /globaldem?demtype=SRTMGL1&south=X&north=X&west=X&east=X` | Free API key (academic registration) |
| **Esri World Imagery** | Satellite map tiles | Tile URL: `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` | None (attribution required) |
| **OpenStreetMap** | Street/base map tiles | Tile URL: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` | None |

---

## 5. API Design

### 5.1 API Principles

- All endpoints under `/api/v1/` prefix (versioned)
- JSON request and response bodies
- Input validation via Pydantic schemas
- Standard response envelope: `{ "status": "success|error", "data": {...}, "message": "..." }`
- Appropriate HTTP status codes (200, 201, 404, 422, 500, 502)

### 5.2 Endpoint Table

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| GET | `/api/v1/health` | Server health check | — | `{ status: "ok" }` |
| GET | `/api/v1/villages` | List all villages | — | Array of village objects (name, lat, lng, state, district) |
| GET | `/api/v1/villages/{id}` | Get village details | — | Village object with optional boundary GeoJSON |
| POST | `/api/v1/analysis` | Start a new analysis | `{ latitude, longitude, radius_km, curve_number?, land_geojson? }` | `{ analysis_id, status: "processing" }` |
| GET | `/api/v1/analysis/{id}` | Get analysis status and results | — | Full analysis object with status |
| GET | `/api/v1/analysis/{id}/terrain` | Get terrain analysis | — | Elevation stats, slope stats, contours GeoJSON |
| GET | `/api/v1/analysis/{id}/catchment` | Get catchment data | — | Catchment polygon GeoJSON, area (km²), pour point |
| GET | `/api/v1/analysis/{id}/rainfall` | Get rainfall data | — | Annual avg (mm), monthly distribution, source |
| GET | `/api/v1/analysis/{id}/runoff` | Get runoff estimation | — | Method, CN, annual runoff (mm & m³), coefficient |
| GET | `/api/v1/analysis/{id}/recommendation` | Get pond recommendations | — | Ranked candidates with scores, pond specs, catchment details |

### 5.3 Analysis Request Parameters

```
POST /api/v1/analysis
{
    "latitude": 18.91,              // Required. Center point latitude.
    "longitude": 74.25,             // Required. Center point longitude.
    "radius_km": 2.0,              // Optional. Analysis area radius (default: 2.0, max: 5.0).
    "curve_number": 75,            // Optional. SCS Curve Number (default: 75).
    "land_geojson": { ... }        // Optional. GeoJSON FeatureCollection of available land parcels.
}
```

---

## 6. Algorithms and Methodology

### Algorithm 1: Sink Filling (DEM Conditioning)

| | |
|---|---|
| **Purpose** | Remove artificial depressions (sinks) in the DEM that would trap water flow and produce incorrect drainage patterns |
| **Input** | Raw DEM raster grid (elevation values as 2D NumPy array) |
| **Output** | Hydrologically conditioned DEM (sinks filled to the level of their lowest pour point) |
| **Methodology** | Priority-flood algorithm: iteratively raise the elevation of sink cells until water can flow toward the boundary. Uses a min-heap priority queue starting from the grid edges. Implemented by the pysheds library. |
| **Why appropriate** | Standard preprocessing step in all hydrological DEM analysis. Without sink filling, flow direction computation would create disconnected drainage that fails to reach the boundary. |
| **Assumptions** | All sinks in ~30m SRTM are assumed to be artifacts, not real closed basins. This is generally valid at 30m resolution. |

---

### Algorithm 2: Contour Generation (Marching Squares)

| | |
|---|---|
| **Purpose** | Extract lines of equal elevation from the DEM for visualization |
| **Input** | DEM raster grid + contour interval (e.g., 10 metres) |
| **Output** | Set of contour line geometries (GeoJSON LineString features) with elevation attributes |
| **Methodology** | Marching squares algorithm: for each 2×2 block of DEM cells, determine which edges of the block are crossed by the target elevation value, then connect those crossings into line segments. Combine segments into continuous contour lines. Uses matplotlib.contour or scipy internally. |
| **Why appropriate** | Standard, well-understood algorithm for contour extraction from regular grids. Produces smooth, correct contour lines. |
| **Assumptions** | Linear interpolation between adjacent DEM cells. Contour interval chosen to suit terrain relief. |

---

### Algorithm 3: Slope Calculation

| | |
|---|---|
| **Purpose** | Calculate terrain steepness at every DEM cell, which affects pond suitability |
| **Input** | DEM raster grid |
| **Output** | Slope raster grid (values in degrees, 0° = flat, 90° = vertical) |
| **Methodology** | For each cell, compute partial derivatives using a 3×3 neighbourhood: dz/dx = (z_right − z_left) / (2 × cell_size), dz/dy = (z_above − z_below) / (2 × cell_size). Then slope = arctan(√(dz/dx² + dz/dy²)). This is the Horn (1981) method. |
| **Why appropriate** | Standard method used in GIS software (ArcGIS, QGIS). Robust against noise due to 3×3 averaging. |
| **Assumptions** | Cell size converted from degrees to metres using local scale factor at the latitude of the study area. |

---

### Algorithm 4: Flow Direction (D8)

| | |
|---|---|
| **Purpose** | Determine the drainage direction at every DEM cell — which way water flows |
| **Input** | Hydrologically conditioned DEM (sinks filled) |
| **Output** | Flow direction grid where each cell contains a code (1, 2, 4, 8, 16, 32, 64, 128) indicating the direction toward its steepest downslope neighbour |
| **Methodology** | D8 (Deterministic Eight-Neighbour): for each cell, calculate the slope toward all 8 neighbouring cells. The cell drains toward the neighbour with the steepest downhill slope. Diagonal distances are multiplied by √2 for correct slope comparison. |
| **Why appropriate** | The most widely used flow direction algorithm. Simple, efficient, and produces realistic drainage networks. Good enough for 30m DEM resolution. |
| **Assumptions** | Each cell has exactly one flow direction (no bifurcation). Flat areas are resolved by preferring flow toward the nearest edge. |

```
Direction codes:
  32 | 64 | 128
  ---+----+----
  16 | ×  |  1
  ---+----+----
   8 |  4 |  2
```

---

### Algorithm 5: Flow Accumulation

| | |
|---|---|
| **Purpose** | Count how many upstream cells drain through each cell — identifies stream channels |
| **Input** | Flow direction grid |
| **Output** | Accumulation grid where each cell value = number of upstream cells |
| **Methodology** | Start from cells with no inflow (ridges/edges). Traverse downstream following flow direction, incrementing each cell's count by the sum of all cells that drain into it. |
| **Why appropriate** | River/stream networks are found where accumulation exceeds a threshold. High accumulation areas near a candidate pond mean the pond will receive water efficiently. |
| **Assumptions** | Uniform cell size (each cell contributes equally). No consideration of infiltration or evaporation at this stage. |

---

### Algorithm 6: Catchment Delineation

| | |
|---|---|
| **Purpose** | Identify the area of land that drains to a specific pond location (pour point) |
| **Input** | Flow direction grid + pour point coordinates |
| **Output** | Catchment mask (boolean raster) → converted to GeoJSON polygon + area (km²) |
| **Methodology** | (a) Snap the pour point to the nearest high-accumulation cell (stream channel) within a tolerance. (b) Starting from the pour point, recursively trace upstream: find all cells whose flow direction points to the current cell. Mark them as part of the catchment. (c) Convert the resulting binary mask to a polygon boundary. |
| **Why appropriate** | Catchment area directly determines how much rainfall becomes available runoff for the pond. Without knowing the catchment, runoff volume cannot be estimated. |
| **Assumptions** | The flow direction grid correctly represents drainage. Pour point snapping ensures it is on a drainage channel. |

---

### Algorithm 7: Runoff Estimation — SCS Curve Number Method

| | |
|---|---|
| **Purpose** | Estimate how much rainfall becomes surface runoff (available for pond filling) |
| **Input** | Rainfall depth P (mm) + Curve Number CN (dimensionless, 0–100) |
| **Output** | Runoff depth Q (mm) → Runoff volume V (m³) = Q × catchment area |
| **Methodology** | The SCS (Soil Conservation Service, now NRCS) Curve Number method, a widely used empirical formula: |

**Equations (SI units, all in mm):**

```
If P > Ia:
    Q = (P - Ia)² / (P - Ia + S)

If P ≤ Ia:
    Q = 0

Where:
    S  = (25400 / CN) - 254     ... potential maximum retention (mm)
    Ia = 0.2 × S                 ... initial abstraction (mm)
    P  = rainfall depth (mm)
    Q  = runoff depth (mm)
    CN = Curve Number (0-100)
```

**Runoff volume:**
```
V (m³) = Q (mm) × A (m²) / 1000
       = Q (mm) × A (km²) × 1000
```

**Curve Number interpretation:**
- CN = 100 → all rainfall becomes runoff (impervious surface)
- CN = 0 → no runoff (all rainfall absorbed)
- Typical rural India: CN = 65–85 depending on land use and soil type

| Land Use | Soil Group B | Soil Group C |
|----------|:----------:|:----------:|
| Forest | 55 | 70 |
| Grassland | 61 | 74 |
| Agriculture | 78 | 85 |
| Barren/Waste | 86 | 91 |

| | |
|---|---|
| **Why appropriate** | Industry-standard method used worldwide for small watershed hydrology. Simple, well-documented, explainable. Requires only rainfall and a single parameter (CN). Appropriate for academic-level estimation. |
| **Assumptions** | (1) CN is uniform across catchment (simplification). (2) Ia = 0.2S (empirical ratio). (3) Single-event storm model applied to monthly/annual totals. (4) No baseflow or groundwater contribution. |
| **Limitations** | Does not account for rainfall intensity or timing. Does not model evapotranspiration explicitly. Accuracy depends on correct CN selection. |

---

### Algorithm 8: Pond Depth and Storage Estimation

| | |
|---|---|
| **Purpose** | Recommend pond dimensions based on available runoff volume and terrain |
| **Input** | Annual runoff volume (m³), terrain slope at location, typical pond depth guidelines |
| **Output** | Recommended depth (m), surface area (m²), storage capacity (m³) |
| **Methodology** | (a) Depth is constrained between 2–5m based on terrain slope (flatter → deeper, steeper → shallower). (b) Assume trapezoidal cross-section with side slopes of 1.5:1 to 2:1. (c) Storage capacity V = (A_top + A_bottom + √(A_top × A_bottom)) × depth / 3 (prismoidal formula). (d) Surface area estimated from target volume and depth. |
| **Why appropriate** | Standard engineering approximations for small earth-dam ponds. Trapezoidal geometry is realistic for excavated ponds. |
| **Assumptions** | Uniform depth. Symmetric side slopes. Homogeneous soil allowing excavation. No seepage loss modeled. These are estimates, not construction-grade calculations. |

---

### Algorithm 9: Suitability Scoring — Weighted Multi-Criteria Decision Analysis (MCDA)

| | |
|---|---|
| **Purpose** | Rank candidate pond locations by combining multiple physical and practical factors |
| **Input** | Slope grid, flow accumulation grid, elevation grid, land availability GeoJSON, catchment area |
| **Output** | Suitability score (0.0 to 1.0) for each candidate location |
| **Methodology** | Weighted linear combination of normalized factor scores: |

```
Score = w₁·f(slope) + w₂·f(drainage) + w₃·f(elevation) + w₄·f(land) + w₅·f(catchment)

Where:
    f(slope)     = 1.0 if slope < 3°, linearly decreasing to 0 at 15°
    f(drainage)  = normalized flow accumulation (log scale)
    f(elevation) = higher score for relatively low-lying areas
    f(land)      = 1.0 if within available land polygon, 0.0 otherwise
    f(catchment) = normalized upstream catchment area

Weights:
    w₁ = 0.30 (slope — most critical physical factor)
    w₂ = 0.25 (drainage position — water availability)
    w₃ = 0.15 (relative elevation)
    w₄ = 0.20 (land availability — practical constraint)
    w₅ = 0.10 (catchment area)
```

| | |
|---|---|
| **Why appropriate** | Transparent, deterministic, explainable. Each factor is physically meaningful. No black-box ML model. The professor's guidelines emphasize explainability over complexity. Weights can be justified individually. |
| **Why not ML** | No labeled training data exists for "good pond locations." ML would be a black box. Suitability factors are well-understood and measurable — a scoring model is the correct approach. |
| **Assumptions** | Linear score functions. Weights chosen based on hydrological reasoning. Land availability is binary (available or not). |

---

## 7. Expected Challenges and Proposed Solutions

### Challenge 1: External API Rate Limits and Downtime

**Problem:** OpenTopography limits free academic users to ~200 DEM requests/day. Open-Meteo may be temporarily unavailable.

**Solution:**
- Cache all DEM tiles on the filesystem after first download. Check cache before making API calls.
- Cache rainfall data in MongoDB with a timestamp. Reuse cached data if less than 7 days old.
- For demo/presentation, pre-download DEM and rainfall data for all demo villages.
- Display clear error messages when APIs are unavailable, rather than failing silently.

### Challenge 2: DEM Data Gaps and NoData Values

**Problem:** SRTM DEM has occasional NoData pixels (voids), especially in mountainous areas or near water bodies.

**Solution:**
- Explicitly detect NoData values when loading the DEM.
- Fill small NoData gaps using interpolation from surrounding valid cells.
- If the analysis area has too many NoData pixels (>10%), reject the analysis with a descriptive error.

### Challenge 3: Large DEM Processing Time

**Problem:** Processing a 5km radius area at 30m resolution produces a grid of ~167×167 = ~28,000 cells. Flow direction and catchment computation on this grid takes noticeable time.

**Solution:**
- Limit maximum analysis radius to 5 km.
- Show a progress indicator on the frontend during analysis.
- Cache processed results (contours, catchment) so repeat requests are instant.
- Use efficient libraries (pysheds is optimized for this workload).

### Challenge 4: Curve Number Selection Accuracy

**Problem:** The SCS-CN method requires knowing the land use and soil type of the catchment, which may not be precisely available.

**Solution:**
- Use a configurable default CN (75 = mixed rural land use on moderate soil).
- Allow the user to adjust CN via the UI with guidance on typical values.
- Provide a reference table of CN values for different land use types.
- Clearly document that this is an estimate, not an engineering guarantee.

### Challenge 5: Land Ownership Data Unavailability

**Problem:** Authoritative government land ownership data is not available via free public APIs. Satellite imagery cannot determine legal ownership.

**Solution:**
- Design the system to accept land availability as a GeoJSON input layer.
- For demo purposes, create sample GeoJSON polygons clearly labeled as demo data.
- The UI and reports must state that land availability data is user-provided/reference only.
- Physical terrain suitability and legal land availability are evaluated as separate factors.

### Challenge 6: Coordinate System Conversions for Area Calculations

**Problem:** DEM data is in WGS84 (degrees). Area calculations require projected coordinates (metres).

**Solution:**
- Use pyproj to convert from WGS84 to an appropriate UTM zone for the location.
- Apply the conversion when calculating catchment area (km²), pond surface area (m²), etc.
- Store coordinates in WGS84 (standard for GeoJSON) but compute distances/areas in projected metres.

### Challenge 7: Student Must Explain the System During Viva

**Problem:** AI-assisted code must be fully understood by the student.

**Solution:**
- Maintain LEARN.md with ordered topics, explanations, and viva questions for every phase.
- Explain each algorithm before implementing it: purpose, input, output, intuition, steps.
- The student should be able to: draw the architecture diagram, write the SCS-CN formula, explain D8 flow direction, and walk through the full pipeline — all without reference material.

---

## 8. Database Design Summary

### Collections

| Collection | Purpose | Key Fields |
|-----------|---------|------------|
| `villages` | Store village metadata | name, state, district, latitude, longitude, boundary (GeoJSON) |
| `analyses` | Store analysis runs and results | location, status, terrain results, catchment results, rainfall results, runoff results, pond recommendation |
| `rainfall_cache` | Cache API rainfall data | latitude, longitude, period, daily_data, fetched_at |

### Storage Strategy

| Data Type | Where | Why |
|-----------|-------|-----|
| Village metadata | MongoDB | Structured, small, queryable |
| Analysis results | MongoDB | Structured, linked to village, queryable |
| Rainfall cache | MongoDB | Query by coordinates, moderate size |
| DEM files (GeoTIFF) | Filesystem `data/dem/` | Large binary rasters; rasterio reads from disk |
| Contour GeoJSON | Filesystem `data/geojson/` | Can be large; referenced by path |
| Land GeoJSON input | Filesystem `data/geojson/` | User-supplied; variable size |

---

## 9. Implementation Phases (Summary)

| Phase | Name | Key Deliverable | Est. Duration |
|-------|------|-----------------|---------------|
| 0 | Project Setup & Scaffolding | Working dev environment (frontend, backend, database connected) | 1 day |
| 1 | Backend Foundation | Village API, Pydantic models, MongoDB CRUD | 1 day |
| 2 | Frontend Foundation & Map | Interactive Leaflet map with satellite imagery, village selector | 2 days |
| 3 | DEM Acquisition & Processing | Fetch SRTM DEM, cache, sink filling, elevation stats | 3 days |
| 4 | Contour & Slope Analysis | Contour extraction, slope calculation, display on map | 2 days |
| 5 | Catchment Delineation | D8 flow direction, flow accumulation, watershed boundary | 2 days |
| 6 | Rainfall Integration | Open-Meteo client, annual/monthly stats, caching | 1 day |
| 7 | Runoff & Pond Sizing | SCS-CN implementation, pond depth/area/capacity estimation | 2 days |
| 8 | Suitability Engine | Weighted scoring, candidate ranking, land layer | 2 days |
| 9 | Integration, Polish & Testing | End-to-end pipeline, UI polish, documentation, demo prep | 3 days |

**Schedule:**
- Week 1 (Aug 10–16): Phases 0, 1, 2
- Week 2 (Aug 17–23): Phases 3, 4
- Week 3 (Aug 24–30): Phases 5, 6, 7
- Week 4 (Aug 31–Sep 5): Phases 8, 9, final submission

---

## 10. Disclaimers and Limitations

1. All pond size estimates are approximate and are NOT suitable for construction engineering.
2. The SCS-CN method is an empirical approximation — not a substitute for detailed hydrological modelling.
3. SRTM DEM has ~30m resolution — individual buildings and small features are not visible.
4. Open-Meteo rainfall data is reanalysis (ERA5), not ground-station observations. It provides a reasonable approximation for regional rainfall patterns.
5. Land availability data is user-supplied. The system does not verify legal ownership and must not be used as proof of government ownership.
6. The suitability scoring weights are chosen based on hydrological reasoning and may need field calibration.
7. This is an academic prototype — not a production system.
