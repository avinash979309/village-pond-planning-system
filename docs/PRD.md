# Product Requirements Document (PRD)

## AI-based Village Pond Planning System

**Version:** 1.0  
**Date:** 2026-08-10  
**Author:** Avinash (with AI assistance)  
**Status:** Draft — Awaiting Review

---

## 1. Problem Statement

Water conservation is a major challenge in rural India. One effective and historically proven solution is the construction of ponds at suitable locations to harvest rainwater. However, selecting optimal locations for pond construction requires analysis of multiple geospatial and hydrological factors:

- Terrain elevation and slope
- Catchment area delineation
- Government/available land identification
- Historical rainfall patterns
- Runoff estimation
- Storage capacity calculation

Village administrators currently lack accessible, integrated tools that combine these analyses. This project aims to fill that gap with a web-based decision-support system.

---

## 2. Target Users

| User | Role | Needs |
|------|------|-------|
| Village Administrator | Primary end user | Simple interface to explore locations, view recommendations, understand analysis |
| Academic Evaluator | Professor/TA | Technically sound implementation, explainable algorithms, clean documentation |
| Student Developer | Builder | Understanding of every component for viva/demo |

---

## 3. Objectives

1. Build a web application that helps village administrators identify suitable locations for pond construction.
2. Use real terrain data (DEM), real rainfall data, and sound hydrological methods.
3. Provide interactive map-based visualization of all analysis results.
4. Present analysis results clearly enough for non-technical users and technically enough for academic evaluation.
5. Ensure the student can explain every component during demonstration.

---

## 4. Functional Requirements

These are extracted directly from the assignment specification:

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Display satellite imagery for a selected village/location | Must |
| FR-02 | Visualize contour maps (elevation contours) | Must |
| FR-03 | Identify available land suitable for pond excavation | Must |
| FR-04 | Estimate the catchment area contributing runoff to a selected location | Must |
| FR-05 | Query historical rainfall data using publicly available APIs | Must |
| FR-06 | Estimate runoff volume using rainfall and catchment information | Must |
| FR-07 | Recommend an appropriate pond depth and approximate storage capacity | Must |
| FR-08 | Overlay all results on an interactive map | Must |

### FR-08 Map Overlay Details

The overlay must display:
- Selected pond location
- Catchment area boundary
- Annual rainfall statistics
- Estimated runoff volume
- Recommended pond dimensions
- Supporting maps and visualizations

---

## 5. Non-Functional Requirements

| ID | Requirement | Details |
|----|-------------|---------|
| NFR-01 | Performance | Analysis for a single village should complete within reasonable time (~30-60 seconds) |
| NFR-02 | Usability | Interface must be understandable by a village administrator |
| NFR-03 | Reliability | Graceful error handling for API failures, missing data |
| NFR-04 | Maintainability | Modular code, clear separation of concerns |
| NFR-05 | Explainability | Every algorithm and formula must be documented |
| NFR-06 | Portability | Should run on a standard development machine |
| NFR-07 | Security | No secrets in code, input validation, CORS configured |

---

## 6. User Workflow

```
1. User opens the application
2. User selects a village or enters coordinates
3. System displays satellite/map imagery for the area
4. System fetches and processes DEM data
5. System displays elevation contours on the map
6. System identifies land suitable for pond construction
7. User selects (or system suggests) a candidate pond location
8. System delineates the catchment area for that location
9. System retrieves historical rainfall data
10. System estimates runoff volume (using rainfall + catchment)
11. System recommends pond depth and storage capacity
12. System overlays all results on the interactive map
13. System displays analysis summary with metrics
14. User can adjust location and re-run analysis
```

---

## 7. Scope

### In Scope

- Village/location selection (coordinate-based or search)
- Satellite/map tile display via Leaflet
- DEM data acquisition and processing
- Elevation contour generation and display
- Slope analysis
- Land suitability identification (based on terrain + optional ownership layer)
- Catchment area delineation using DEM-derived flow analysis
- Historical rainfall data retrieval via Open-Meteo API
- Runoff volume estimation using SCS Curve Number method
- Pond depth and storage capacity estimation
- Interactive map overlays for all results
- Analysis result summary/report
- MongoDB storage for analysis metadata and results
- REST API backend
- Responsive web frontend

### Out of Scope

- Real-time rainfall monitoring
- Legal land ownership verification (system accepts input layers)
- Construction-grade engineering calculations
- Multi-user authentication system
- Mobile native application
- Real-time satellite imagery processing
- Groundwater analysis
- Soil composition testing
- Cost estimation for construction
- Integration with government databases (beyond public APIs)

---

## 8. Success Criteria

| Criterion | Measure |
|-----------|---------|
| System functionality (35 marks) | All 8 functional requirements working end-to-end |
| Terrain and catchment analysis (20 marks) | Correct DEM processing, contour generation, slope analysis, catchment delineation |
| Frontend and visualization (5 marks) | Interactive map with all overlays, clean UI |
| Software design and code quality (15 marks) | Modular architecture, clean code, proper error handling |
| System design and management (15 marks) | HLD, architecture docs, phase management |
| Documentation and report (10 marks) | Complete documentation, API docs, installation guide |

---

## 9. Assumptions

1. Internet connectivity is available for accessing external APIs (Open-Meteo, DEM tiles, map tiles).
2. The demonstration area will be a village in India with SRTM DEM coverage (global 30m resolution).
3. Land availability data will be provided as a GeoJSON input layer (since authoritative government ownership data is not reliably available via public API).
4. The SCS Curve Number method is an acceptable approximation for runoff estimation at this academic level.
5. MongoDB is available locally or via a free cloud tier (MongoDB Atlas).
6. The system is a prototype/academic project, not a production-grade engineering tool.
7. The student's development machine can run Python, Node.js, and MongoDB.

---

## 10. Constraints

1. **Timeline:** HLD due August 10, prototype during lab hours, final submission September 5.
2. **Technology:** Must use the approved stack (Python/FastAPI, React/Vite, MongoDB).
3. **Data availability:** DEM resolution limited to publicly available data (~30m SRTM).
4. **Academic integrity:** Student must understand and explain all code during viva.
5. **API limits:** Open-Meteo and elevation APIs have rate limits on free tiers.
6. **No real-world guarantees:** All estimates are approximate; system must not claim engineering accuracy.

---

## 11. Deliverables (Per Assignment)

1. Complete source code
2. Installation guide
3. API documentation
4. Accessible frontend for users
5. Final technical report

---

## 12. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| External API downtime | Cannot fetch DEM/rainfall | Implement caching, fallback to cached data, clear error messages |
| DEM data gaps | Incomplete terrain analysis | Validate data coverage before analysis, handle NoData values |
| Large DEM processing time | Slow user experience | Limit area size, cache processed results, show progress indicators |
| Open-Meteo rate limiting | Cannot fetch rainfall | Cache rainfall data, batch requests |
| Student cannot explain code | Academic penalty | LEARN.md maintained, explain-as-you-build approach |
| Scope creep | Missed deadline | Strict phase management, locked decisions |
