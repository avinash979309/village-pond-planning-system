# AI-based Village Pond Planning System

A backend API that analyzes contour/elevation data (KML/KMZ) to identify optimal pond locations using D8 flow analysis, catchment delineation, and real river-exclusion via OpenStreetMap.

**Course:** Computer System Design  
**Status:** Phase 2 (Backend API) ✅

---

## Project Structure

```
Assignment_1/
├── backend/                   → FastAPI backend service
│   ├── app/
│   │   ├── main.py            → App entry point + /analyzeContour route
│   │   ├── api/v1/contour.py  → Advanced analysis routes
│   │   ├── services/          → Analysis orchestration
│   │   └── geo/               → KML parser, DEM builder, hydrology engine,
│   │                              OSM fetcher, catchment delineator
│   └── requirements.txt
├── maps/
│   └── sample_contour_map.kml → Sample input (Shivnath river area, ~1 km²)
├── generate_results.sh        → Helper: generates result.geojson from CLI
├── result.geojson             → Latest analysis output (drag into geojson.io)
└── phase2_testing_guide.md    → Detailed testing guide
```

---

## Quick Start

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

---

## Test the API

### Option 1 — Simple curl command

```bash
curl -X POST http://localhost:8000/analyzeContour \
  -F "file=@maps/sample_contour_map.kml"
```

Clean, structured JSON response — no extra parameters needed.

### Option 2 — Helper script (saves result.geojson)

```bash
./generate_results.sh maps/sample_contour_map.kml 3
```

Waits ~60-90 seconds. Saves `result.geojson` — drag into [geojson.io](https://geojson.io) to visualize.

### Option 3 — Interactive Swagger UI

Open `http://localhost:8000/docs` → click `POST /analyzeContour` → upload KML → Execute.

---

## API Response Format

`POST /analyzeContour` returns:

```json
{
  "status": "success",
  "pond_location": {
    "longitude": 81.2944,
    "latitude": 21.2439,
    "elevation_m": 282.0,
    "suitability_score": 0.8822
  },
  "pour_point": {
    "longitude": 81.2951,
    "latitude": 21.2441
  },
  "catchment": {
    "area_km2": 0.0139,
    "area_m2": 13851.0,
    "avg_elevation_m": 290.4,
    "boundary_geojson": { "type": "Polygon", "coordinates": ["..."] }
  },
  "all_candidates": [
    { "rank": 1, "longitude": 81.2944, "latitude": 21.2439, "suitability_score": 0.8822, "catchment_area_km2": 0.0139 },
    { "rank": 2, "longitude": 81.2823, "latitude": 21.2527, "suitability_score": 0.8800, "catchment_area_km2": 0.0004 }
  ],
  "osm_water_exclusion": {
    "water_bodies_found": true,
    "water_body_count": 11,
    "water_body_names": ["Shivnath", "sivnath river", "canal"]
  }
}
```

---

## How It Works

1. **Parse** KML/KMZ — extract contour lines with elevation values
2. **Interpolate** contour vertices — build regular elevation grid (DEM)
3. **Condition** DEM — fill pits, resolve flats (pysheds)
4. **D8 flow direction** — compute flow accumulation across grid
5. **OSM exclusion** — fetch real river/lake polygons from OpenStreetMap; exclude from candidate selection
6. **Terrain exclusion** — detect floodplains and river corridors from elevation + flow data
7. **Select pond sites** — score cells by elevation, slope, flow accumulation; pick top 3 spatially-separated candidates
8. **Delineate catchment** — trace upstream contributing area for each candidate; return polygon + area

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Geo parsing | lxml, Shapely |
| Interpolation | NumPy, SciPy |
| Hydrology | pysheds (D8 flow, catchment delineation) |
| OSM data | Overpass API (multi-mirror fallback) |
| HTTP client | httpx |

---

## Visualize Results

After running `./generate_results.sh`, open [geojson.io](https://geojson.io) and drag `result.geojson` onto the map.

Legend:
- 🟢 **Green** — Rank 1 pond candidate + catchment
- 🟠 **Orange** — Rank 2 candidate
- 🟣 **Purple** — Rank 3 candidate
- Darker pin = pour point (catchment outlet)
