# Implementation Phases

## AI-based Village Pond Planning System

**Version:** 1.0  
**Date:** 2026-08-10  
**Total Phases:** 10  
**Timeline:** August 10 → September 5, 2026  

---

## Phase Overview

| Phase | Name | Est. Duration | Dependencies |
|-------|------|--------------|--------------|
| 0 | Project Setup & Scaffolding | 1 day | None |
| 1 | Backend Foundation | 1 day | Phase 0 |
| 2 | Frontend Foundation & Map | 1-2 days | Phase 0 |
| 3 | DEM Acquisition & Terrain Processing | 2-3 days | Phase 1 |
| 4 | Contour Generation & Slope Analysis | 1-2 days | Phase 3 |
| 5 | Catchment Delineation | 2 days | Phase 3 |
| 6 | Rainfall Data Integration | 1 day | Phase 1 |
| 7 | Runoff Estimation & Pond Sizing | 2 days | Phase 5, 6 |
| 8 | Land Suitability & Recommendation Engine | 2 days | Phase 4, 7 |
| 9 | Full Integration, UI Polish & Testing | 2-3 days | All phases |

```
Week 1 (Aug 10-16)  →  Phases 0, 1, 2
Week 2 (Aug 17-23)  →  Phases 3, 4
Week 3 (Aug 24-30)  →  Phases 5, 6, 7
Week 4 (Aug 31-Sep 5) →  Phases 8, 9 + Final testing
```

---

## Phase 0: Project Setup & Scaffolding

### Objective
Set up the complete project structure, install dependencies, configure development tools, and verify that frontend, backend, and database can all start and communicate.

### Prerequisites
- Node.js 18+ installed
- Python 3.11+ installed
- MongoDB installed or Atlas account created
- Git initialized

### Files Involved
```
Assignment_1/
├── frontend/          (Vite + React + TypeScript scaffold)
├── backend/           (FastAPI scaffold)
├── docs/              (already created)
├── .gitignore
├── README.md
└── docker-compose.yml (optional, for MongoDB)
```

### Technical Work
1. Initialize React+TypeScript project with Vite
2. Install frontend dependencies (react-leaflet, tailwind, etc.)
3. Create FastAPI project structure
4. Install backend dependencies (fastapi, uvicorn, rasterio, pysheds, etc.)
5. Configure Tailwind CSS
6. Set up MongoDB connection
7. Create `.env.example` files
8. Create `.gitignore`
9. Verify: frontend starts, backend starts, MongoDB connects

### Expected Output
- Frontend loads in browser with placeholder map
- Backend returns `{"status": "ok"}` at `/api/v1/health`
- MongoDB connection established

### Testing Requirements
- `npm run dev` starts frontend without errors
- `uvicorn app.main:app --reload` starts backend
- Health endpoint returns 200

### Acceptance Criteria
- [ ] Frontend builds and runs
- [ ] Backend builds and runs
- [ ] MongoDB connection works
- [ ] CORS configured for frontend-backend communication
- [ ] All dependencies installed without conflicts

### Student Learning Requirements
- How Vite scaffolds a React project
- How FastAPI creates an application
- What CORS is and why it's needed
- Basic MongoDB connection concepts

---

## Phase 1: Backend Foundation

### Objective
Build the core backend structure: configuration management, Pydantic models, database layer, API router structure, and basic village CRUD endpoints.

### Prerequisites
Phase 0 complete (project scaffolded, dependencies installed)

### Files Involved
```
backend/app/
├── main.py              # CORS, router mounting
├── config.py            # Environment configuration
├── api/v1/
│   ├── router.py        # API router
│   ├── villages.py      # Village endpoints
│   └── analysis.py      # Analysis endpoints (stubs)
├── models/
│   ├── village.py       # Village Pydantic schemas
│   └── analysis.py      # Analysis schemas (initial)
├── db/
│   ├── connection.py    # MongoDB async connection
│   └── repositories.py  # Data access layer
└── services/
    └── village_service.py
```

### Technical Work
1. Implement config with pydantic-settings (env vars)
2. Create MongoDB async connection (Motor)
3. Define Village Pydantic models (request/response)
4. Implement village CRUD endpoints
5. Set up API router with versioned prefix
6. Add standard error handling middleware
7. Seed sample village data (clearly labeled as demo)

### Expected Output
- `GET /api/v1/villages` returns list of sample villages
- `GET /api/v1/villages/{id}` returns village details
- `POST /api/v1/analysis` stub returns 501 (not yet implemented)
- Auto-generated API docs at `/docs`

### Testing Requirements
- API endpoints respond correctly
- Pydantic validation rejects invalid input
- MongoDB operations succeed

### Acceptance Criteria
- [ ] Village CRUD endpoints work
- [ ] Pydantic validates all inputs
- [ ] MongoDB read/write works
- [ ] API docs auto-generated
- [ ] Error responses follow standard format

### Student Learning Requirements
- FastAPI routing and dependency injection
- Pydantic model validation
- Async/await in Python
- MongoDB document structure
- REST API design principles

---

## Phase 2: Frontend Foundation & Map

### Objective
Build the core frontend with interactive map, village selector, and the basic layout structure.

### Prerequisites
Phase 0 complete

### Files Involved
```
frontend/src/
├── App.tsx
├── main.tsx
├── index.css
├── components/
│   ├── Map/MapContainer.tsx
│   ├── Map/SatelliteLayer.tsx
│   ├── VillageSelector/VillageSearch.tsx
│   ├── VillageSelector/CoordinateInput.tsx
│   └── Layout/Header.tsx
├── services/api.ts
└── types/index.ts
```

### Technical Work
1. Create responsive layout (header, sidebar, main map area)
2. Implement Leaflet map with satellite tile layer (Esri World Imagery)
3. Add OpenStreetMap as base layer option
4. Implement village selector (dropdown + search)
5. Implement coordinate input (latitude/longitude)
6. Connect to backend API for village list
7. Map navigates to selected village location
8. Add layer control for switching base maps

### Expected Output
- Full-screen map with satellite imagery
- Village dropdown populates from backend API
- Selecting a village centers the map on that location
- Manual coordinate entry works
- Responsive layout on different screen sizes

### Testing Requirements
- Map renders without errors
- Village selector populates from API
- Map centers correctly on selection
- Coordinates validate within valid ranges

### Acceptance Criteria
- [ ] Map displays satellite imagery
- [ ] Village selector works with backend API
- [ ] Coordinate input validates and centers map
- [ ] Responsive layout
- [ ] Layer control works (satellite / street map)

### Student Learning Requirements
- React component architecture
- React-Leaflet usage and map layers
- TypeScript interfaces for API data
- Fetching data from REST API (useEffect, fetch/axios)
- Tailwind CSS utility classes

---

## Phase 3: DEM Acquisition & Terrain Processing

### Objective
Implement the ability to fetch DEM data for a given location, process it (fill sinks, compute basic terrain metrics), and store/cache it.

### Prerequisites
Phase 1 complete (backend foundation)

### Files Involved
```
backend/app/
├── external/
│   └── dem_fetcher.py       # OpenTopography API client
├── geo/
│   ├── dem_processor.py     # DEM loading, sink filling
│   └── utils.py             # Geospatial utilities
├── services/
│   └── dem_service.py       # DEM acquisition orchestration
└── data/
    └── dem/                 # Cached DEM files
```

### Technical Work
1. Implement OpenTopography API client to fetch SRTM DEM
2. Implement DEM caching (check before re-downloading)
3. Load DEM with rasterio into numpy arrays
4. Implement sink filling (using pysheds or scipy)
5. Extract elevation statistics (min, max, mean, range)
6. Clip DEM to bounding box around location
7. Handle NoData values properly
8. Add `/api/v1/analysis/{id}/terrain` endpoint
9. API endpoint triggers DEM fetch + basic processing

### Expected Output
- Given coordinates, system fetches DEM tile from OpenTopography
- DEM is cached as GeoTIFF on filesystem
- Elevation statistics returned via API
- DEM can be loaded and processed without errors

### Testing Requirements
- DEM fetcher returns valid GeoTIFF
- Rasterio can read the fetched file
- Elevation values are sensible for test area
- NoData handling works
- Cache prevents duplicate downloads

### Acceptance Criteria
- [ ] DEM fetcher successfully downloads SRTM data
- [ ] DEM loads into numpy array correctly
- [ ] Sink filling produces valid output
- [ ] Elevation statistics are reasonable
- [ ] Caching works (no redundant downloads)
- [ ] Error handling for API failures

### Student Learning Requirements
- What a DEM is and why it matters
- SRTM data: source, resolution (30m), coverage
- GeoTIFF format basics
- Rasterio: reading raster data, coordinate transforms
- Why sink filling is necessary for hydrological analysis
- Coordinate systems (WGS84, UTM)

---

## Phase 4: Contour Generation & Slope Analysis

### Objective
Generate elevation contour lines from DEM data and compute slope/terrain analysis. Display contours on the frontend map.

### Prerequisites
Phase 3 complete (DEM acquisition working)

### Files Involved
```
backend/app/geo/
├── contour_generator.py    # Contour extraction
├── slope_analyzer.py       # Slope calculation
frontend/src/components/Map/
└── ContourLayer.tsx         # Contour overlay
```

### Technical Work
1. Generate contour lines from DEM using matplotlib.contour or scipy
2. Convert contours to GeoJSON format
3. Calculate slope from DEM (gradient magnitude)
4. Classify slope into categories (flat, gentle, moderate, steep)
5. Generate slope statistics
6. API endpoints to return contour GeoJSON and slope data
7. Frontend component to render contour lines on Leaflet map
8. Color-code contours by elevation

### Expected Output
- Contour lines displayed on the map at configurable intervals
- Slope map data available
- Elevation profile information

### Testing Requirements
- Contour lines are closed or clip to boundary correctly
- Slope values are in valid range (0-90 degrees)
- GeoJSON is valid and renders on Leaflet
- Contour intervals are sensible for the terrain

### Acceptance Criteria
- [ ] Contour lines generated from DEM
- [ ] Contours display correctly on frontend map
- [ ] Slope calculated and classified
- [ ] Terrain statistics endpoint works
- [ ] Contour interval is configurable

### Student Learning Requirements
- What contour lines represent
- How contours are extracted from gridded elevation data
- Slope calculation: gradient of elevation surface
- How slope affects pond site suitability
- GeoJSON format for lines and polygons

---

## Phase 5: Catchment Delineation

### Objective
Implement watershed/catchment area delineation using DEM-derived flow analysis. For a selected pour point, determine the area that drains to it.

### Prerequisites
Phase 3 complete (DEM processed, sinks filled)

### Files Involved
```
backend/app/geo/
├── catchment_analyzer.py   # Flow direction, accumulation, catchment
frontend/src/components/Map/
└── CatchmentLayer.tsx       # Catchment polygon overlay
```

### Technical Work
1. Compute flow direction grid (D8 algorithm) using pysheds
2. Compute flow accumulation grid
3. For a given pour point, delineate catchment area
4. Snap pour point to nearest drainage channel
5. Convert catchment mask to GeoJSON polygon
6. Calculate catchment area (km²)
7. API endpoint: `GET /api/v1/analysis/{id}/catchment`
8. Frontend: display catchment boundary polygon on map
9. Show catchment statistics in analysis panel

### Expected Output
- Catchment boundary polygon displayed on map
- Catchment area (km²) calculated
- Pour point and drainage network visible

### Testing Requirements
- Flow direction produces valid grid (all values are valid directions)
- Flow accumulation highlights stream channels
- Catchment is contiguous and contains the pour point
- Area calculation is reasonable for the terrain
- Edge cases: pour point on ridge, at boundary

### Acceptance Criteria
- [ ] Flow direction computed correctly
- [ ] Flow accumulation grid generated
- [ ] Catchment delineated for a pour point
- [ ] Catchment boundary displayed on frontend map
- [ ] Catchment area calculated in km²
- [ ] Pour point snapping works

### Student Learning Requirements
- D8 flow direction algorithm
- Flow accumulation concept
- Watershed/catchment: what they are, why they matter
- Why pour point snapping is needed
- How catchment area relates to runoff volume
- Pysheds library API and workflow

---

## Phase 6: Rainfall Data Integration

### Objective
Fetch historical rainfall data from Open-Meteo API, compute annual/monthly statistics, and present the data.

### Prerequisites
Phase 1 complete (backend foundation)

### Files Involved
```
backend/app/
├── external/open_meteo.py       # Open-Meteo API client
├── services/rainfall_service.py # Rainfall data service
├── models/rainfall.py           # Rainfall data models
frontend/src/components/Analysis/
└── RainfallChart.tsx             # Rainfall visualization
```

### Technical Work
1. Implement Open-Meteo API client (historical weather endpoint)
2. Fetch daily precipitation data for configurable date range
3. Aggregate: annual totals, monthly averages, seasonal patterns
4. Cache rainfall data in MongoDB
5. Handle API failures gracefully
6. API endpoint: `GET /api/v1/analysis/{id}/rainfall` (or include in analysis)
7. Frontend: bar chart or table showing monthly/annual rainfall
8. Display rainfall statistics in analysis panel

### Expected Output
- Historical rainfall data fetched for any Indian location
- Monthly and annual statistics computed
- Rainfall chart displayed in frontend
- Data cached to prevent repeated API calls

### Testing Requirements
- API client handles valid coordinates
- Handles API timeout/failure gracefully
- Monthly averages sum to approximately annual total
- Data for known Indian locations is reasonable (500-3000mm/year)

### Acceptance Criteria
- [ ] Open-Meteo API client fetches rainfall data
- [ ] Annual and monthly statistics computed
- [ ] Data cached in MongoDB
- [ ] API failures handled gracefully
- [ ] Frontend displays rainfall chart
- [ ] Values are reasonable for test locations

### Student Learning Requirements
- How Open-Meteo API works (REST, query parameters)
- Rainfall patterns in India (monsoon, regional variation)
- Data aggregation (daily → monthly → annual)
- API client design (error handling, retries, caching)
- Why historical rainfall matters for runoff estimation

---

## Phase 7: Runoff Estimation & Pond Sizing

### Objective
Implement the SCS Curve Number runoff estimation method and pond depth/storage capacity calculation.

### Prerequisites
Phase 5 complete (catchment area known)
Phase 6 complete (rainfall data available)

### Files Involved
```
backend/app/geo/
├── runoff_estimator.py     # SCS-CN implementation
├── pond_sizer.py           # Pond depth & volume estimation
frontend/src/components/Analysis/
├── RunoffSummary.tsx        # Runoff results display
└── PondRecommendation.tsx   # Pond sizing results
```

### Technical Work
1. Implement SCS Curve Number method:
   - Q = (P - Ia)² / (P - Ia + S) where P > Ia
   - S = (25400/CN) - 254
   - Ia = 0.2 × S
2. Allow configurable Curve Number (with reasonable defaults based on land use)
3. Calculate annual runoff volume = runoff depth × catchment area
4. Implement pond depth recommendation based on:
   - Available runoff volume
   - Terrain constraints (slope)
   - Typical pond depth guidelines (2-5m range)
5. Calculate storage capacity: V = f(depth, surface_area, side_slopes)
6. API endpoints for runoff and pond recommendation
7. Frontend panels showing runoff estimation and pond specs

### Expected Output
- Annual runoff volume estimated (m³)
- Runoff coefficient calculated
- Recommended pond depth (m)
- Recommended pond surface area (m²)
- Estimated storage capacity (m³)

### Testing Requirements
- SCS formula produces correct results for known inputs
- Runoff with CN=100 ≈ rainfall (fully impervious)
- Runoff with CN=0 ≈ 0 (fully permeable)
- Pond dimensions are physically reasonable
- Storage capacity is self-consistent (V ≈ depth × area × shape_factor)

### Acceptance Criteria
- [ ] SCS-CN formula implemented correctly
- [ ] Runoff volume calculated from rainfall + catchment
- [ ] Pond depth recommended
- [ ] Storage capacity estimated
- [ ] All formulas documented with assumptions
- [ ] Frontend displays all runoff and pond metrics

### Student Learning Requirements
- SCS Curve Number method: derivation, inputs, assumptions
- What Curve Number represents (land use + soil type)
- Runoff coefficient concept
- Pond geometry: depth, surface area, side slopes
- Storage capacity estimation methods
- Limitations of simplified runoff models

---

## Phase 8: Land Suitability & Recommendation Engine

### Objective
Implement the suitability scoring system that combines terrain, drainage, and land availability factors to identify and rank candidate pond locations.

### Prerequisites
Phase 4 complete (slope analysis)
Phase 7 complete (runoff estimation)

### Files Involved
```
backend/app/geo/
├── land_suitability.py     # Suitability scoring engine
frontend/src/components/Map/
├── LandAvailabilityLayer.tsx
├── PondLocationMarker.tsx
frontend/src/components/Analysis/
└── AnalysisResults.tsx      # Combined results
```

### Technical Work
1. Define suitability factors and scoring functions:
   - Slope score: flat areas score higher
   - Drainage position: areas receiving more upstream flow score higher
   - Elevation relative position: lower areas (but not flood-prone) score higher
   - Land availability: available land scores 1, unavailable scores 0
2. Implement composite weighted scoring
3. Accept land availability GeoJSON layer (user input)
4. Identify top-N candidate locations
5. For each candidate, run the full analysis pipeline
6. Rank candidates by suitability score
7. Display scored areas and candidates on map
8. Show results in analysis panel with explanatory text

### Expected Output
- Suitability heat map or scored areas on map
- Ranked list of candidate pond sites
- Each candidate includes: score breakdown, runoff estimate, recommended dimensions
- Land availability overlay (if provided)

### Testing Requirements
- Scoring ranges are 0-1 for each factor
- Composite score is 0-1
- Flat areas near drainage channels score higher
- Steep areas score lower
- Areas without available land are excluded

### Acceptance Criteria
- [ ] Suitability scoring engine works
- [ ] Multiple candidate sites identified and ranked
- [ ] Land availability layer can be loaded
- [ ] Candidates displayed on map with scores
- [ ] Score breakdown explained in UI
- [ ] All assumptions documented

### Student Learning Requirements
- Multi-criteria decision analysis (MCDA) basics
- Weighted scoring methodology
- How terrain factors influence pond suitability
- Why land ownership/availability is a separate concern
- How to interpret and explain suitability scores

---

## Phase 9: Full Integration, UI Polish & Testing

### Objective
Integrate all components into a seamless end-to-end workflow. Polish the UI, add complete map overlays, write tests, create documentation.

### Prerequisites
All previous phases complete

### Files Involved
All frontend and backend files

### Technical Work
1. End-to-end analysis pipeline:
   - Select location → Fetch DEM → Process terrain → Delineate catchment → Fetch rainfall → Estimate runoff → Size pond → Score suitability → Display results
2. Complete map overlays (all results visible together)
3. Analysis summary panel with all metrics
4. Loading states and progress indicators
5. Error states and user-friendly messages
6. Responsive design polish
7. Write API documentation
8. Write installation guide
9. Create README.md
10. Run comprehensive tests
11. Fix bugs and edge cases
12. Prepare demo data for presentation

### Expected Output
- Complete working application
- All 8 functional requirements satisfied
- Clean, polished UI
- Complete documentation
- Installation guide
- Demo-ready with sample village(s)

### Testing Requirements
- End-to-end test for at least 2-3 different locations
- All API endpoints return valid responses
- Frontend handles loading and error states
- Map overlays render correctly
- Analysis results are reasonable and self-consistent

### Acceptance Criteria
- [ ] End-to-end workflow works for at least 2 demo locations
- [ ] All 8 functional requirements met
- [ ] Map displays all overlays correctly
- [ ] Analysis summary is clear and complete
- [ ] API documentation complete
- [ ] Installation guide works from scratch
- [ ] Error handling for all failure modes
- [ ] Student can explain every component

### Student Learning Requirements
- End-to-end integration testing
- UI/UX polish techniques
- API documentation best practices
- How to demo and explain the complete system
- Viva preparation: be able to answer questions about every component

---

## Assignment Phase 2: Contour Map → Terrain → Catchment API

> **Note:** This phase was released by the instructor separately from the original project plan.
> It does NOT replace the original Phase 2 (Frontend Foundation) — that phase will follow during implementation.
> This section maps the instructor's released Phase 2 requirements to the implementation.

### Objective

Build a backend API endpoint (`POST /api/v1/contour/analyze-contour`) that:
- Accepts a KML or KMZ contour map as a file upload.
- Derives an elevation surface from the contour lines.
- Performs D8 hydrological analysis.
- Derives drainage channels from terrain (or detects explicit water features if encoded).
- Selects an algorithmically justified pond candidate location.
- Delineates the contributing catchment area.
- Returns structured JSON with GeoJSON geometries.

### Pipeline Components (all reusable for DEM phases)

```
POST /api/v1/contour/analyze-contour
        ↓
[kml_parser.py]           Parse KML/KMZ → contour lines + other features
        ↓
[water_feature_detector.py]  Detect explicit water features (Case A / Case B)
        ↓
[terrain_builder.py]      Contour lines → regular elevation grid (scipy interpolation)
        ↓
[terrain_conditioner.py]  Compute slope from elevation grid
        ↓
[hydrology_engine.py]     Fill sinks → D8 flow direction → flow accumulation → drainage mask
        ↓
[pond_candidate_selector.py]  Weighted multi-factor scoring → best candidate
        ↓
[catchment_delineator.py]     Snap pour point → delineate catchment → UTM area
        ↓
[contour_analysis_service.py] Orchestrate → assemble response dict
        ↓
[contour.py route]        Format → return API envelope
```

### Key Design Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Elevation interpolation | scipy.griddata linear | Smooth, honours contour values, no oscillation at 1m interval |
| Flow direction | D8 (pysheds, ADR-009) | Industry standard, well-tested |
| Drainage derivation | Flow accumulation threshold | No explicit water feature in sample KML |
| Pond candidate selection | Weighted multi-factor scoring | Deterministic, explainable (ADR-010) |
| Area calculation | UTM projected (EPSG auto-selected) | Must not use degree-squared units |
| No hardcoding | All results derived from input | Critical instructor requirement |

### Acceptance Criteria

- [x] KML upload works
- [x] KMZ upload works
- [x] Contours actually parsed
- [x] Elevation extracted from input
- [x] Elevation surface/grid generated
- [x] Slope computed
- [x] D8 flow direction works (pysheds)
- [x] Flow accumulation works
- [x] Drainage derived from terrain
- [x] Explicit water feature detection implemented (Case A)
- [x] Terrain-derived drainage implemented (Case B)
- [x] Drainage exclusion zone applied
- [x] Pond candidate derived algorithmically (not hardcoded)
- [x] Pond candidate does not overlap drainage
- [x] Pour point snapped to drainage
- [x] Catchment delineated (pysheds upstream trace)
- [x] Catchment returned as GeoJSON Polygon
- [x] Catchment area calculated in m² and km² (UTM projected)
- [x] No sample-specific hardcoding
- [x] Different valid KML produces different results
- [x] Invalid input → meaningful errors
- [x] Code is modular: geo/ modules reusable for DEM phases
- [x] Tests pass (unit + integration)
- [x] API documentation in README.md
- [x] MEMORY.md updated
- [x] LEARN.md updated

### Reusability Note

The modules `terrain_conditioner.py`, `hydrology_engine.py`,
`pond_candidate_selector.py`, and `catchment_delineator.py` operate on
a plain `numpy.ndarray` elevation grid. They do not import from `kml_parser.py`.

Future DEM-based phases (original Phase 3) can produce an `ElevationGrid`
directly from a GeoTIFF (via rasterio) and feed it into the same pipeline
from `terrain_conditioner.py` onwards — no code changes required downstream.
