# Student Learning Reference

## AI-based Village Pond Planning System

**Version:** 1.0 — Updated 2026-08-29
**Purpose:** Quick-reference study guide and viva preparation

---

## HLD Preparation: Must-Study Before Implementation Begins

> After submitting the HLD, use the time before implementation to study these core topics. Your professor may ask about any of these during the HLD review or prototype demo.

### A. Hydrology Fundamentals (CRITICAL)
Study these before any implementation:
- **What is a catchment/watershed?** — the area of land where all rainfall drains to a single outlet point
- **SCS Curve Number method** — memorize the three equations (Q, S, Ia) and understand what CN means
- **What is runoff?** — the portion of rainfall that flows over the surface and does NOT infiltrate into the soil
- **What is a pour point?** — the point at the outlet of a catchment where all drainage converges

### B. Digital Elevation Models (CRITICAL)
- **What is a DEM?** — a grid of elevation values; each pixel = ground height
- **What is SRTM?** — NASA's Shuttle Radar Topography Mission (2000); provides ~30m global coverage
- **What does 30m resolution mean?** — each pixel represents a 30×30 metre area on the ground
- **What is sink filling?** — removing artificial depressions in the DEM so water can flow correctly
- **What is the D8 algorithm?** — each cell flows to its steepest downslope neighbour (1 of 8 options)
- **What is flow accumulation?** — counting how many upstream cells drain through each cell

### C. Geospatial Data Formats
- **GeoTIFF** — raster format for DEM files (elevation grids with geographic metadata)
- **GeoJSON** — JSON format for vector geographic features (points, lines, polygons)
- **WGS84 (EPSG:4326)** — the coordinate system used by GPS (latitude/longitude in degrees)
- **Raster vs Vector** — raster = grid of pixels; vector = points, lines, polygons

### D. Web Architecture Basics
- **REST API** — HTTP methods (GET, POST), status codes (200, 404, 422, 500), JSON bodies
- **CORS** — Cross-Origin Resource Sharing; needed because frontend and backend run on different ports
- **Client-server model** — frontend (browser) sends requests → backend (server) processes → returns JSON

### E. Key Questions You Should Be Able to Answer for HLD Review
1. Draw the system architecture block diagram and explain each component.
2. What external data sources does the system use, and what does each provide?
3. Explain the SCS Curve Number formula. What does CN represent?
4. How does the D8 flow direction algorithm work?
5. What is the difference between flow direction and flow accumulation?
6. How is a catchment boundary determined?
7. Why can't satellite imagery determine land ownership?
8. What is the difference between physical suitability and land availability?
9. How does the suitability scoring work? Why these specific weights?
10. What are the limitations of this system? (SRTM resolution, simplified CN, reanalysis rainfall, etc.)

---

## Pre-Implementation: Concepts to Learn Before Starting

### 1. REST API Architecture
**Why it matters:** The entire frontend-backend communication uses REST.
**What to learn:**
- What is a REST API? (Resources, HTTP methods, status codes)
- JSON request/response format
- API versioning (`/api/v1/`)
- What is CORS and why do we need it?

**Questions you should be able to answer:**
- What HTTP method do you use to create a new analysis? (POST)
- What does a 422 status code mean? (Validation error)
- Why do we version our API?
- What happens if CORS is not configured?

---

### 2. Geospatial Fundamentals
**Why it matters:** The entire domain is built on geospatial data.
**What to learn:**
- Coordinate systems: WGS84 (EPSG:4326), what latitude/longitude represent
- What a GeoTIFF file is
- What GeoJSON is (and how it differs from regular JSON)
- What raster vs. vector data means

**Questions you should be able to answer:**
- What coordinate system does GPS use?
- What is the difference between raster and vector data?
- Why do we use GeoTIFF for DEM files?
- What are the components of a GeoJSON Feature?

---

### 3. Digital Elevation Model (DEM)
**Why it matters:** The DEM is the foundation for all terrain analysis.
**What to learn:**
- What SRTM is (NASA Shuttle Radar Topography Mission, 2000)
- Resolution: 30m means each pixel represents a 30×30m area
- What elevation values represent
- What "NoData" values mean in a DEM

**Questions you should be able to answer:**
- What is the resolution of SRTM data? What does it mean?
- If a DEM pixel value is 450, what does that mean?
- Why might a DEM have holes (NoData values)?

---

## Phase 0: Project Setup

### 4. Build Tools & Frameworks
**What to learn:**
- What Vite does (build tool, dev server, HMR)
- What React is (component-based UI library)
- What TypeScript adds over JavaScript (type safety)
- What FastAPI is (Python web framework for APIs)
- What Pydantic does (data validation using Python types)

**Questions you should be able to answer:**
- Why use Vite instead of Create React App?
- What is JSX/TSX?
- What is a Pydantic model?
- What is async/await in Python?

---

## Phase 1: Backend Foundation

### 5. FastAPI & Database
**What to learn:**
- FastAPI routing (decorators, path parameters, query parameters)
- Dependency injection in FastAPI
- MongoDB document model (vs. relational tables)
- Motor: async MongoDB driver for Python
- Environment variables with `python-dotenv`

**Code it uses:** `backend/app/main.py`, `backend/app/api/v1/villages.py`, `backend/app/db/connection.py`

**Questions you should be able to answer:**
- How does FastAPI auto-generate API documentation?
- What is the difference between a path parameter and a query parameter?
- Why use MongoDB instead of PostgreSQL for this project?
- What is an async function and why is FastAPI async?

---

## Phase 2: Frontend & Map

### 6. React-Leaflet & Map Concepts
**What to learn:**
- Leaflet tile layers (how web maps work with tiles)
- What tile servers are (Esri, OpenStreetMap)
- React-Leaflet: `MapContainer`, `TileLayer`, `GeoJSON`, `Marker`
- React component lifecycle and state management
- React hooks: `useState`, `useEffect`

**Code it uses:** `frontend/src/components/Map/MapContainer.tsx`

**Questions you should be able to answer:**
- How do web map tile layers work? (zoom levels, x/y tiles)
- What is the difference between raster tiles and vector tiles?
- Why does the map need different tile sources for satellite vs street view?
- How does React re-render when state changes?

---

## Phase 3: DEM Acquisition & Processing

### 7. DEM Processing Pipeline
**What to learn:**
- Rasterio: reading GeoTIFF, accessing metadata, coordinate transforms
- Sink filling: why depressions must be filled before flow analysis
- NumPy: how DEM data is stored as a 2D array
- Bounding box calculations for a location

**Code it uses:** `backend/app/geo/dem_processor.py`, `backend/app/external/dem_fetcher.py`

**Questions you should be able to answer:**
- Why do we fill sinks in a DEM? What would happen if we didn't?
- How does rasterio convert between pixel coordinates and geographic coordinates?
- What is the purpose of caching DEM files?
- How do you calculate a bounding box given a center point and radius?

---

## Phase 4: Contours & Slope

### 8. Terrain Analysis
**What to learn:**
- Contour lines: what they represent, how they're extracted
- Marching squares algorithm (conceptually)
- Slope calculation: partial derivatives of elevation surface
- How slope relates to pond suitability

**Code it uses:** `backend/app/geo/contour_generator.py`, `backend/app/geo/slope_analyzer.py`

**Questions you should be able to answer:**
- What does it mean when contour lines are close together?
- How do you calculate slope from a DEM grid? (gradient formula)
- What slope range is suitable for pond construction? Why?
- How do you convert a slope grid into GeoJSON for display?

---

## Phase 5: Catchment Delineation

### 9. Hydrology: Flow & Catchments
**Why it matters:** This is the most important hydrological concept in the project.
**What to learn:**
- D8 flow direction algorithm
- Flow accumulation and what it reveals
- Watershed/catchment: definition and how it's delineated
- Pour point: what it is and why we snap to the nearest stream
- How pysheds performs these calculations

**Code it uses:** `backend/app/geo/catchment_analyzer.py`

**Questions you should be able to answer:**
- Explain the D8 algorithm. How many possible flow directions?
- If a cell has a flow accumulation value of 500, what does that mean?
- What is a pour point? Why must we snap it to a stream?
- How is a catchment boundary determined from a flow direction grid?
- Why does catchment area matter for pond planning?

---

## Phase 6: Rainfall Integration

### 10. Rainfall Data
**What to learn:**
- Open-Meteo API: how to query, parameters, response format
- ERA5 reanalysis data: what it is and its limitations
- Rainfall patterns in India (monsoon seasons)
- Data aggregation: daily → monthly → annual
- API client design: error handling, retries, caching

**Code it uses:** `backend/app/external/open_meteo.py`, `backend/app/services/rainfall_service.py`

**Questions you should be able to answer:**
- What is the difference between reanalysis data and ground-station observations?
- How does the Open-Meteo API work? What parameters do you pass?
- Why do we cache rainfall data?
- What is a typical annual rainfall for a semi-arid Indian village?

---

## Phase 7: Runoff & Pond Sizing

### 11. SCS Curve Number Method
**Why it matters:** This is the core hydrological algorithm.
**What to learn:**
- The SCS-CN equations (Q, S, Ia — memorize them)
- What Curve Number represents and what affects it
- Hydrologic soil groups (A, B, C, D)
- How to go from runoff depth (mm) to volume (m³)
- Pond sizing: depth, surface area, storage capacity relationships

**Code it uses:** `backend/app/geo/runoff_estimator.py`, `backend/app/geo/pond_sizer.py`

**Questions you should be able to answer:**
- Write the SCS-CN runoff equation. Explain each variable.
- What does a Curve Number of 80 mean? What about 40?
- If rainfall is 800mm/year and CN=75, approximately how much is runoff?
- How do you convert runoff depth to volume? (multiply by catchment area)
- How do you estimate pond storage capacity from depth and area?
- What assumptions does the SCS method make? What are its limitations?

---

## Phase 8: Suitability Scoring

### 12. Multi-Criteria Decision Analysis
**What to learn:**
- Weighted scoring methodology
- Factor normalization (converting different units to 0-1 scale)
- How to choose and justify weights
- Why land ownership is a separate concern from terrain suitability

**Code it uses:** `backend/app/geo/land_suitability.py`

**Questions you should be able to answer:**
- How does the suitability score combine multiple factors?
- Why is slope the highest-weighted factor?
- Can satellite imagery determine land ownership? Why or why not?
- How would you validate the suitability scoring results?

---

## Phase 9: Integration & Documentation

### 13. System Integration
**What to learn:**
- End-to-end data flow (from user click to analysis result)
- Error handling patterns
- API documentation (Swagger/OpenAPI)
- How to write a technical report

**Questions you should be able to answer:**
- Walk through the complete analysis pipeline step by step.
- What could go wrong at each step and how does the system handle it?
- How would you add a new analysis factor (e.g., soil type)?
- What are the limitations of this system?
- How would you improve the system if you had more time?

---

## Viva Preparation: Must-Know Topics

> **These are the topics you should be extremely comfortable with:**

1. **System Architecture:** Draw the complete system diagram. Explain each component.
2. **DEM Processing:** Explain what a DEM is, how you get it, how you process it.
3. **Catchment Delineation:** Explain D8, flow accumulation, watershed delineation.
4. **SCS-CN Method:** Write the formulas. Explain inputs, outputs, assumptions.
5. **Suitability Scoring:** Explain factors, weights, and how candidates are ranked.
6. **API Design:** Explain your REST API structure, why you chose it.
7. **Technology Choices:** Why FastAPI? Why MongoDB? Why Leaflet?
8. **Limitations:** What can't this system do? What assumptions did you make?
9. **Data Sources:** Where does elevation data come from? Rainfall? Map tiles?
10. **Error Handling:** What happens when an API fails? When data is missing?

---

## Phase 2: Contour → Terrain → Catchment — Concepts & Viva Questions (Added 2026-08-29)

### Geospatial File Formats

**KML (Keyhole Markup Language)**
- XML-based geographic data format, originally developed for Google Earth.
- Stores features (Placemark), geometries (Point, LineString, Polygon), styles, and folders.
- Elevation for contour features stored in the `<name>` field as a numeric string.
- Does NOT store elevation as Z coordinates on LineStrings (in contour maps).

**KMZ**
- ZIP-compressed KML. The inner KML file is conventionally named `doc.kml`.
- Must be decompressed (Python: `zipfile`) before XML parsing.

**GeoJSON**
- JSON-based geographic format. Types: Point, LineString, Polygon, MultiPolygon, Feature, FeatureCollection.
- Used for all API geographic outputs in this system.
- Every geographic output is a GeoJSON `Feature` with `geometry` + `properties`.

### GIS Concepts

**CRS (Coordinate Reference System)**
- Defines how coordinates map to real Earth locations.
- WGS84 (EPSG:4326): global lat/lon in degrees. Used in KML, GeoJSON.
- UTM (e.g., EPSG:32644 for central India): projected coordinates in metres. Used for area calculation.
- **Never compute area in lat/lon degrees** — one degree longitude ≠ same distance at every latitude.

**Raster vs Vector**
- Vector: discrete features (points, lines, polygons). KML contours are vector.
- Raster: regular grid of values. DEM and elevation grids are raster.
- Contour-to-DEM conversion = vector-to-raster (interpolation).

**DEM (Digital Elevation Model)**
- Raster grid where each cell holds an elevation value.
- SRTM: ~30m resolution, freely available via OpenTopography.
- In Phase 2, we build a synthetic DEM from KML contour lines.

### Contour Interpolation

**Why we need it:**
Contour lines give elevation at specific isolines only. Hydrological analysis needs elevation at every grid cell.

**Algorithm used: Delaunay triangulation (scipy.griddata linear)**
1. Sample points along each contour polyline.
2. Build point cloud: (lon, lat, elevation).
3. Triangulate the point cloud (Delaunay triangulation).
4. For each grid cell, find which triangle contains it and linearly interpolate elevation.
5. Cells outside the triangulation convex hull: filled by nearest-neighbour.

**Limitations:**
- Bounded by contour interval accuracy.
- Assumes linear slope between contours.
- Edge artifacts at grid boundary (handled by nearest-fill).

### D8 Flow Direction

**Concept:** Each grid cell drains to the one of its 8 neighbours with the steepest descent.
Uses power-of-2 encoding: E=1, SE=2, S=4, SW=8, W=16, NW=32, N=64, NE=128.

**DEM conditioning (why required before D8):**
- Pit filling: removes single-cell sinks (artifacts).
- Depression filling: removes enclosed basins that would trap flow.
- Flat resolution: adds tiny gradients to flat areas so flow continues.

### Flow Accumulation

**Concept:** For each cell, count the total number of upstream cells that drain to it.
High accumulation = convergent drainage = probable stream channel.

**Drainage threshold:** Top N% of accumulation values → drainage channel cells.

### Watershed / Catchment

**Catchment (watershed):** The area of land that drains to a single outlet (pour point).
All precipitation falling within the catchment eventually flows to that point.

**Pour point:** The outlet/exit of a catchment. In this system: the pond location, snapped to a drainage cell.

**D8 upstream tracing:** Given a pour point, walk upstream along flow directions, collecting all cells that drain to it.

### Spatial Buffers

**What:** A zone of specified width around a geometry.
**Why:** Safety margin; uncertainty zone; exclusion zone.
**In this system:** Drainage channel cells are buffered by N cells to create the pond exclusion zone.
**Implementation:** `scipy.ndimage.binary_dilation` on the drainage mask.

### Projected Area Calculation

**Why:** Lat/lon degrees are not uniform distance units.
**Correct method:**
1. Get catchment polygon in WGS84 (EPSG:4326).
2. Project to UTM (local projected CRS, e.g. EPSG:32644).
3. Compute polygon area in projected metres.
4. Convert m² to km².

**Never:** Compute area directly from lat/lon degree coordinates.

---

### Phase 2 Viva Questions

1. What is the difference between a KML and a KMZ file?
2. How is elevation stored in a contour KML file? (In the `<name>` field, not Z coordinates)
3. What is Delaunay triangulation and why is it used here?
4. What is the difference between "nearest" and "linear" scipy.griddata methods?
5. Why must DEM pits and depressions be filled before D8?
6. What does D8 stand for? What are the 8 directions?
7. What is flow accumulation? How is it computed?
8. What is a pour point? Why is it snapped to a drainage cell?
9. What is the difference between the pond candidate and the pour point?
10. Why can't we compute catchment area in latitude/longitude degrees?
11. What is UTM? Why is EPSG:32644 appropriate for central India?
12. Why is the drainage channel excluded from pond candidate selection?
13. What are the 4 scoring factors for pond candidate selection?
14. What does the term "terrain-derived drainage" mean in the API response? Why is it not called a "river"?
15. If a KML contains an explicit river polygon, how does Case A differ from Case B?
16. What is binary dilation? How is it used for the exclusion buffer?
17. What does a flow accumulation grid look like visually?
18. Why does the system use pysheds instead of implementing D8 from scratch?
19. What happens if all grid cells fall within the exclusion zone?
20. How does the system ensure no sample-specific hardcoding?

