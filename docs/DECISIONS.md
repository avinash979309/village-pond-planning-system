# Architecture Decision Records

## AI-based Village Pond Planning System

**Version:** 1.0  
**Date:** 2026-08-10  

---

## Decision Log

| ID | Decision | Status |
|----|----------|--------|
| ADR-001 | Monolithic architecture | 🔒 LOCKED |
| ADR-002 | FastAPI backend framework | 🔒 LOCKED |
| ADR-003 | React + TypeScript + Vite frontend | 🔒 LOCKED |
| ADR-004 | MongoDB for metadata/results storage | 🔒 LOCKED |
| ADR-005 | Filesystem for raster/DEM storage | 🔒 LOCKED |
| ADR-006 | Open-Meteo for rainfall data | 🔒 LOCKED |
| ADR-007 | OpenTopography for DEM data | APPROVED |
| ADR-008 | SCS Curve Number for runoff estimation | 🔒 LOCKED |
| ADR-009 | Pysheds for watershed delineation | APPROVED |
| ADR-010 | Suitability scoring over ML models | 🔒 LOCKED |
| ADR-011 | Land availability as input layer | 🔒 LOCKED |
| ADR-012 | Leaflet for map visualization | 🔒 LOCKED |
| ADR-013 | Tailwind CSS for styling | 🔒 LOCKED |

---

## ADR-001: Monolithic Architecture

**Decision:** Use a modular monolithic architecture (single FastAPI backend, single React frontend).

**Reason:** The system is an academic prototype with a single development team (one student). Microservices would add deployment complexity without benefit.

**Alternatives Considered:**
- Microservices (rejected: unnecessary complexity for a prototype)
- Serverless functions (rejected: cold start latency, harder to debug)

**Consequences:** All backend logic lives in one deployable unit. Modules must be well-separated via Python packages.

**Status:** 🔒 LOCKED

---

## ADR-002: FastAPI Backend Framework

**Decision:** Use FastAPI as the backend framework.

**Reason:** 
- Assignment suggests Flask or FastAPI
- FastAPI provides: automatic API docs (Swagger), Pydantic validation, async support, modern Python typing
- Better developer experience than Flask for API-centric applications

**Alternatives Considered:**
- Flask (rejected: lacks built-in validation, no auto-docs, no native async)
- Django (rejected: too heavyweight for an API-focused application)

**Consequences:** Backend requires Python 3.11+. Team must understand Pydantic, async/await, and dependency injection.

**Status:** 🔒 LOCKED

---

## ADR-003: React + TypeScript + Vite Frontend

**Decision:** Use React with TypeScript, built with Vite.

**Reason:**
- React is the most popular frontend framework with extensive ecosystem
- TypeScript adds type safety, crucial for complex geospatial data
- Vite provides fast development builds and HMR
- React-Leaflet integrates map capabilities seamlessly

**Alternatives Considered:**
- Plain HTML/JS (rejected: insufficient for interactive map application)
- Vue.js (viable but less ecosystem for geospatial)
- Next.js (rejected: SSR not needed, adds complexity)

**Consequences:** Student must learn React, TypeScript, and component-based architecture.

**Status:** 🔒 LOCKED

---

## ADR-004: MongoDB for Metadata/Results Storage

**Decision:** Use MongoDB for storing village data, analysis results, and cached API responses.

**Reason:**
- Assignment suggests MongoDB/PostgreSQL
- MongoDB's flexible schema suits evolving analysis result structures
- GeoJSON support built-in (geospatial queries)
- Easy setup for prototype (local or Atlas free tier)

**Alternatives Considered:**
- PostgreSQL + PostGIS (strong alternative, but adds schema migration complexity)
- SQLite (too limited for geospatial data)

**Consequences:** Schema is flexible but must be documented. Data integrity is application-enforced via Pydantic.

**Status:** 🔒 LOCKED

---

## ADR-005: Filesystem for Raster/DEM Storage

**Decision:** Store DEM GeoTIFF files and large GeoJSON on the filesystem, not in MongoDB.

**Reason:** 
- DEM files can be 10-100+ MB per tile
- Rasterio reads directly from filesystem (GeoTIFF format)
- GridFS (MongoDB) adds complexity without benefit for this use case
- Filesystem storage is simpler for a prototype

**Alternatives Considered:**
- MongoDB GridFS (rejected: unnecessary abstraction layer)
- S3/object storage (rejected: overkill for prototype)

**Consequences:** Must manage file paths in the database. Must implement a consistent directory structure.

**Status:** 🔒 LOCKED

---

## ADR-006: Open-Meteo for Rainfall Data

**Decision:** Use Open-Meteo Historical Weather API for historical rainfall data.

**Reason:**
- Free, no API key required for non-commercial use
- Global coverage including India
- Historical data from 1940+
- Simple REST API with daily/hourly precipitation
- Assignment lists it as a suggested API

**Alternatives Considered:**
- IMD (India Meteorological Department) — authoritative but no free API
- NASA POWER — free but more complex API
- Custom datasets — not scalable

**Consequences:** Data is reanalysis-based (ERA5), not ground-station observations. Must document this limitation.

**Status:** 🔒 LOCKED

---

## ADR-007: OpenTopography for DEM Data

**Decision:** Use OpenTopography API to fetch SRTM 30m DEM data as GeoTIFF.

**Reason:**
- Provides SRTM GL1 (30m) data via REST API
- Returns GeoTIFF format directly (compatible with rasterio)
- Free API key for academic use
- Well-documented API

**Alternatives Considered:**
- NASA Earthdata + earthaccess (more complex auth)
- USGS EarthExplorer (manual download steps)
- Open-Elevation API (point queries only, not full raster)
- Local pre-downloaded SRTM tiles (less dynamic but viable fallback)

**Consequences:** Requires free API key registration. Rate limited to ~200 calls/day. Must cache aggressively.

**Status:** APPROVED (may switch to pre-downloaded SRTM tiles if API proves unreliable)

---

## ADR-008: SCS Curve Number for Runoff Estimation

**Decision:** Use the SCS (NRCS) Curve Number method for estimating surface runoff from rainfall.

**Reason:**
- Industry-standard method used worldwide
- Simple, well-documented, explainable
- Requires only rainfall depth and curve number (which depends on land use + soil type)
- Appropriate for the academic level of this project
- Transparent and deterministic (no black-box ML)

**Formula:**
```
Q = (P - Ia)² / (P - Ia + S)     where P > Ia
S = (25400 / CN) - 254            (SI units, mm)
Ia = 0.2 × S                      (initial abstraction)
```

**Alternatives Considered:**
- Rational Method (too simplistic, only for peak flow)
- SWAT model (too complex for this prototype)
- ML-based runoff prediction (not transparent, violates explainability principle)

**Consequences:** Must assume or derive Curve Number values. Must document CN assumptions clearly.

**Status:** 🔒 LOCKED

---

## ADR-009: Pysheds for Watershed Delineation

**Decision:** Use the pysheds library for DEM-based flow direction, flow accumulation, and catchment delineation.

**Reason:**
- Purpose-built Python library for watershed/catchment analysis
- Integrates with rasterio, numpy (our existing stack)
- Handles: sink filling, flow direction (D8), flow accumulation, catchment masking
- Well-documented with tutorials
- Performant on raster data

**Alternatives Considered:**
- Manual implementation with numpy/scipy (error-prone, reinventing the wheel)
- GRASS GIS via Python bindings (heavy dependency)
- WhiteboxTools (viable alternative, larger binary)

**Consequences:** Adds a dependency. Student must understand D8 flow direction algorithm.

**Status:** APPROVED

---

## ADR-010: Suitability Scoring over ML Models

**Decision:** Use a transparent, weighted suitability scoring methodology instead of machine learning for pond site recommendation.

**Reason:**
- The assignment values explainability
- A scoring model is fully transparent and deterministic
- Factors are measurable: slope, elevation position, catchment area, land availability, proximity to drainage
- ML would require training data that doesn't exist for this specific domain
- The professor's instructions warn against using vague "AI" terminology

**Scoring approach:**
```
Suitability Score = w1 × f(slope) + w2 × f(drainage_position) + w3 × f(catchment_area) + w4 × f(land_available) + w5 × f(elevation_relative)
```

**Alternatives Considered:**
- Random Forest classifier (rejected: no labeled training data)
- Neural network (rejected: overkill, not explainable)
- k-means clustering (rejected: clustering ≠ suitability)

**Consequences:** Must clearly define and document each factor, weight, and scoring function. Weights may need tuning during testing.

**Status:** 🔒 LOCKED

---

## ADR-011: Land Availability as Input Layer

**Decision:** Treat land availability/ownership data as an input layer (GeoJSON), not as data derived from satellite imagery.

**Reason:**
- Satellite imagery cannot establish legal land ownership
- Authoritative government land databases are not available via free public API
- The system must be honest about data provenance
- A GeoJSON input allows flexibility for any region

**Consequences:** 
- The system must clearly label land data as "user-provided" or "reference data"
- For demonstration, sample GeoJSON land data can be created with clear documentation
- The UI must allow users to upload or reference land parcel layers

**Status:** 🔒 LOCKED

---

## ADR-012: Leaflet for Map Visualization

**Decision:** Use Leaflet (via React-Leaflet) for all map visualization.

**Reason:**
- Open source, free
- Lightweight (~40KB)
- Excellent plugin ecosystem
- Supports GeoJSON overlays, tile layers, markers, custom controls
- React-Leaflet provides React-idiomatic API
- Widely used in academic and government applications

**Alternatives Considered:**
- Mapbox GL JS (requires paid API key for significant use)
- Google Maps (requires API key, usage fees)
- OpenLayers (more powerful but steeper learning curve)

**Consequences:** All map overlays must be in GeoJSON or compatible format. Student must learn Leaflet concepts.

**Status:** 🔒 LOCKED

---

## ADR-013: Tailwind CSS for Styling

**Decision:** Use Tailwind CSS for frontend styling.

**Reason:**
- Utility-first approach enables rapid UI development
- Consistent design without custom CSS complexity
- Great for component-based React architecture
- Responsive by default
- Assignment does not mandate a specific CSS approach, and the master prompt specifies Tailwind CSS

**Alternatives Considered:**
- Vanilla CSS (more flexible but slower development)
- Material UI (heavy dependency)
- Bootstrap (outdated feel)

**Consequences:** Student must learn Tailwind utility class conventions.

**Status:** 🔒 LOCKED

---

## ADR-014: Multiple Terrain Input Adapters (Added 2026-08-29)

**Decision:** Separate the KML/KMZ parsing adapter from the generic hydrology engine. Future DEM-based input will bypass `kml_parser.py` entirely and produce an `ElevationGrid` directly, feeding into the same downstream pipeline.

**Reason:**
- Phase 2 requires KML/KMZ contour input.
- Future phases require SRTM DEM (GeoTIFF) input.
- The hydrological analysis (slope, D8, catchment) is identical regardless of input source.
- Tight coupling of parsing to hydrology would prevent reuse.

**Architecture:**
```
KML/KMZ → kml_parser → terrain_builder → ElevationGrid → [shared pipeline]
DEM/GeoTIFF → dem_processor → ElevationGrid → [shared pipeline]
```

**Consequences:** All modules from `terrain_conditioner.py` onwards must accept `numpy.ndarray`, not KML-specific types.

**Status:** 🔒 LOCKED

---

## ADR-015: Linear Interpolation for Contour-to-Elevation Grid (Added 2026-08-29)

**Decision:** Use `scipy.griddata` with `method='linear'` (Delaunay triangulation) as the primary interpolation method. NaN boundary cells filled with `method='nearest'`.

**Reason:**
- Contour lines are irregularly spaced — grid-based methods cannot apply directly.
- Linear interpolation honours exact contour elevation values.
- No oscillation risk between close 1m-interval contours (unlike cubic).
- Nearest-fill for boundary cells is simpler and safer than extrapolation.

**Alternatives rejected:**
- Cubic: can overshoot between tightly spaced contours.
- Nearest only: produces staircase surface, unacceptable for slope/flow analysis.
- Kriging: computationally expensive, overkill for this resolution.

**Limitations:** Accuracy bounded by contour interval; linear slope assumption between contours.

**Status:** APPROVED

---

## ADR-016: Terrain-Derived Drainage (Case B) for Sample KML (Added 2026-08-29)

**Decision:** For contour maps that do not explicitly encode water/river features, derive drainage channels from D8 flow accumulation threshold. Do not attempt to infer river location from contour shape alone.

**Reason:**
- The sample KML contains only contour LineStrings and a bounding Polygon — no river geometry.
- Flow accumulation naturally identifies convergent drainage pathways.
- The threshold is configurable; not tied to any specific map.
- Result is labelled "terrain-derived" in the API response to prevent misuse.

**Consequence:** Derived drainage is NOT verified geographic river data. Must be explicitly documented in API response.

**Status:** 🔒 LOCKED

---

## ADR-017: Configurable Drainage Exclusion Zone (Added 2026-08-29)

**Decision:** Pond candidates must not overlap the drainage channel or its configurable buffer. The exclusion zone is constructed by binary dilation of the drainage mask.

**Reason:**
- Instructor requirement: do not recommend pond on a river/drainage channel.
- Buffer accounts for measurement uncertainty and safe setback from channel.
- Configurable (`drainage_buffer_cells`, default=2) to accommodate different terrain scales.

**Applies to both Case A (explicit water) and Case B (terrain-derived).**

**Status:** 🔒 LOCKED

---

## ADR-018: Pond Candidate vs Pour Point Distinction (Added 2026-08-29)

**Decision:** Maintain a conceptual and implementation distinction between:
1. **Pond candidate**: selected by multi-factor suitability scoring (may not be on drainage).
2. **Pour point**: the pond candidate snapped to the nearest high-accumulation drainage cell, used as the hydrological input to `pysheds.catchment()`.

**Reason:**
- Placing the pond directly on the channel cell is not always hydrologically or physically appropriate.
- Snapping the pour point ensures the catchment delineation uses a well-defined flow path.
- Both locations are returned in the API response for transparency.

**Status:** APPROVED

