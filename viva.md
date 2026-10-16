# 🎓 Viva Preparation — Village Pond Planning System

> **Course:** CSD (Concurrent & Systems Design) Lab  
> **Project:** AI-based Village Pond Planning System  
> **Stack:** FastAPI · React · Leaflet · pysheds · NumPy/SciPy · Redis · Python LB  
> **Deployment:** 4 lab machines (sys1–sys4), 2 active (sys1+sys2)

---

## Table of Contents

1. [Project Overview — The 30-Second Pitch](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Complete Algorithm Pipeline (Step-by-Step)](#3-algorithm-pipeline)
4. [CSD Themes — Concurrency & Systems Design](#4-csd-themes)
5. [Frontend Architecture](#5-frontend)
6. [API Endpoints](#6-api-endpoints)
7. [Deployment & Infrastructure](#7-deployment)
8. [Libraries & Why Each is Used](#8-libraries)
9. [Key Code Files — What Each Does](#9-code-files)
10. [Viva Q&A — Expected Questions & Answers](#10-viva-qa)

---

## 1. Project Overview

### What Does This System Do?

It helps village administrators find the **best location to build a rainwater harvesting pond** using real satellite terrain data.

**Input:** User either uploads a KML contour map OR draws a rectangle on an interactive map.  
**Output:** Top 3 ranked pond candidate sites with:
- GPS coordinates (lat/lon) and elevation
- Suitability score (0–1)
- Upstream catchment area polygon (km²)
- Estimated annual water harvest volume (m³)
- Pour point (hydrological outlet)

### Why Is It Useful?

Traditional pond site selection uses manual surveys, gut feeling, and local experience. This system uses **quantitative terrain analysis** — DEM data, flow direction algorithms, and multi-criteria scoring — to produce scientifically justified recommendations in under 2 minutes.

### What Kind of "AI" Is Used?

> ⚠️ **Critical Viva Point**  
> **No neural networks or ML models.** The "AI" is **Multi-Criteria Decision Analysis (MCDA)** — a deterministic, transparent, weighted scoring system based on physical terrain properties.

**Why not ML?**
1. **No training data** — there's no labeled dataset of "good vs bad pond sites"
2. **Explainability** — village officials need to understand WHY a site was chosen (slope, elevation, water flow), not trust a black box
3. **Deterministic repeatability** — same input always produces same output

---

## 2. System Architecture

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    User's Browser                        │
│   React 19 + Leaflet Map + Draw Rectangle / Upload KML   │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP POST (JSON or multipart)
                        ▼
┌─────────────────────────────────────────────────────────┐
│          Python Load Balancer (sys1, port 5100)          │
│   Round-robin → sys1:5000, sys2:5000                     │
│   Auto health-check every 10s, auto-failover             │
└───────┬───────────────────────────────────┬─────────────┘
        │                                   │
        ▼                                   ▼
┌───────────────────┐               ┌───────────────────┐
│ FastAPI (sys1)    │               │ FastAPI (sys2)    │
│ Port 5000         │               │ Port 5000         │
│ uvicorn ASGI      │               │ uvicorn ASGI      │
│ + Thread Worker   │               │ + Thread Worker   │
└───────┬───────────┘               └───────────────────┘
        │
        ▼
┌───────────────────┐       ┌───────────────────┐
│  Redis Cache      │       │ Local SRTM .hgt   │
│  sys1:6379        │       │ Tiles (per node)   │
│  24h TTL, bbox key│       │ 30m resolution     │
└───────────────────┘       └───────────────────┘
```

### Architecture Pattern: Distributed Monolith

- Each node runs the **complete application** (API + frontend + all geo modules)
- **No inter-node communication** needed during computation — fully stateless
- Redis is shared (on sys1) for caching only — if Redis dies, nodes compute normally
- SRTM tiles are replicated to each node via `rsync`

---

## 3. Algorithm Pipeline

When a user draws a rectangle or uploads KML, here is **exactly** what happens, step by step:

### Step 1: Input Parsing

**For KML Upload** (`kml_parser.py`):
- Parses XML using `lxml.etree`
- Extracts contour polylines with elevation from `<Placemark>` names
- Extracts bounding box from coordinates
- Detects water features by checking placemark names against keywords ("river", "lake", "nala", "talab") and checking KML color codes for blue

**For Map Rectangle** (`area_analysis_service.py`):
- Receives JSON: `{"west": 81.25, "south": 21.20, "east": 81.35, "north": 21.30}`
- Loads local NASA SRTM `.hgt` binary files (1-arcsecond / ~30m resolution)
- Each `.hgt` file = 3601×3601 grid of signed 16-bit integers (elevations in meters)
- File naming: `N21E081.hgt` = tile starting at 21°N, 81°E

### Step 2: DEM Grid Construction

**For KML** (`terrain_builder.py`):

Contour lines are irregular vectors → need to convert to a regular raster grid.

1. **Arc-length sampling** — Each contour polyline is sampled at 50 evenly-spaced points along its length (not at vertices, which may cluster). This avoids oversampling dense regions.

2. **Delaunay triangulation + linear interpolation** — `scipy.interpolate.griddata(method='linear')`:
   - Constructs a Delaunay triangulation over the (x,y) point cloud
   - For each grid cell inside the convex hull, interpolates elevation using barycentric coordinates of the enclosing triangle
   - **Why linear, not cubic?** Cubic splines oscillate wildly between tightly-spaced 1m contours (Runge's phenomenon)

3. **Nearest-neighbor gap fill** — Cells outside the convex hull get NaN from linear interpolation. A second pass with `method='nearest'` fills these boundary cells.

**For Map Rectangle**: Direct array extraction from SRTM binary → no interpolation needed.

### Step 3: Slope Calculation (`terrain_conditioner.py`)

Uses **central finite differences** via `numpy.gradient`:

```
∂Z/∂x = (Z[r, c+1] − Z[r, c−1]) / (2 × Δx_meters)
∂Z/∂y = (Z[r+1, c] − Z[r−1, c]) / (2 × Δy_meters)

slope_degrees = arctan(√((∂Z/∂x)² + (∂Z/∂y)²)) × (180/π)
```

**Important:** Coordinates are in WGS84 degrees, but slope needs meters. Conversion:
- `Δy_m = (N−S)/rows × 110,540` m/deg (meridional)
- `Δx_m = (E−W)/cols × 111,320 × cos(lat_center)` m/deg (zonal, shrinks toward poles)

### Step 4: Hydrological DEM Conditioning (`hydrology_engine.py` + pysheds)

Raw DEMs have **spurious pits** (cells lower than all 8 neighbors) caused by interpolation artifacts or radar noise. Water entering these pits gets "trapped" and breaks drainage tracing.

Three correction steps using **pysheds** library:

1. **`grid.fill_pits()`** — Raises single-cell sinks to the elevation of their lowest neighbor.

2. **`grid.fill_depressions()`** — Handles multi-cell enclosed depressions using a **priority-flood algorithm**:
   - Start from grid borders (guaranteed outlets)
   - Use a min-heap to process cells in order of ascending elevation
   - Any interior cell reached whose elevation is below the current flood level gets raised to the flood level
   - Result: a "hydrologically enforced" DEM where water always flows downhill to an edge

3. **`grid.resolve_flats()`** — After filling, some areas are perfectly flat (same elevation). Adds a tiny gradient across flat areas directing flow toward the nearest outlet.

### Step 5: D8 Flow Direction (`hydrology_engine.py`)

The **Deterministic Eight-Neighbor (D8)** algorithm assigns each cell a single flow direction:

```
For each cell (r, c):
  For each of 8 neighbors:
    slope_to_neighbor = (Z_cell − Z_neighbor) / distance
    (distance = 1 for cardinal, √2 for diagonal)
  Flow direction = neighbor with STEEPEST downhill slope
```

**Encoding (power-of-2 bit flags):**
```
 NW=32  N=64  NE=128
  W=16   ●    E=1
 SW=8   S=4   SE=2
```

Each cell stores one of: 1, 2, 4, 8, 16, 32, 64, 128.

### Step 6: Flow Accumulation

Counts **total upstream contributing cells** for each cell:

```
A(cell) = 1 + Σ A(upstream neighbors that flow into this cell)
```

- Evaluated in **topological order** from ridgelines (A=0) downstream
- High accumulation = river/stream channel
- Low accumulation = ridgeline or hilltop

**Drainage network extraction:**
- Threshold = 98th percentile of accumulation values (data-driven, not hardcoded)
- Cells with accumulation ≥ threshold = drainage channel
- Apply **binary morphological dilation** (2-cell radius) to buffer the channel

### Step 7: Water Body Exclusion

Three independent exclusion layers combined via logical OR:

**Layer A — Terrain-based water detection** (`terrain_water_detector.py`):
1. **Low elevation zone:** Bottom 15% of elevation range → likely valley floor
2. **River corridor:** Top 2% accumulation, dilated by 8 cells (~120m buffer)
3. **Floodplain:** Bottom 20th percentile elevation AND slope ≤ 1° (flat + low = floodplain)
4. Safety: if combined exclusion > 65% of grid, roll back to high-accumulation channel only

**Layer B — OSM water bodies** (`osm_water_fetcher.py`):
- Queries OpenStreetMap Overpass API for `natural=water`, `waterway=river|stream`, `landuse=reservoir`
- Rasterizes polygon and line geometries onto the grid
- Graceful fallback if network unavailable — returns empty mask

**Layer C — KML water features** (`water_feature_detector.py`):
- Checks placemark names for water keywords
- Checks KML colors for blue (AABBGGRR format)

### Step 8: Pond Candidate Scoring (`pond_candidate_selector.py`)

**Multi-Criteria Weighted Suitability Score** for every non-excluded cell:

```
Score = 0.20 × Elevation_Score
      + 0.30 × Slope_Score
      + 0.30 × Accumulation_Score
      + 0.20 × Proximity_Score
```

#### Each Factor Explained:

**Elevation Score (weight 0.20):**
- Peaks at 20th–40th percentile of elevation distribution (score = 1.0)
- Linearly decays to 0 at grid minimum (too low = river bed) and maximum (too high = hilltop)
- **Why?** Ideal ponds are on hillside depressions — above the floodplain, below the watershed divide

**Slope Score (weight 0.30):**
- Inverted normalized slope: `1 − normalize(slope)`
- Flat land → score ≈ 1.0; steep terrain → score ≈ 0.0
- **Why?** Flat land is cheaper to excavate, retains water better, easier to dam

**Flow Accumulation Score (weight 0.30):**
- Normalized accumulation, **capped at 80th percentile**
- `A_capped = min(A, percentile(A, 80))`
- **Why cap?** Without capping, extreme river-channel values would pull candidates INTO the river bed. Cap ensures moderate-accumulation cells (getting good water supply but not in the channel) score highest.

**Proximity-to-Drainage Score (weight 0.20):**
- Uses `scipy.ndimage.distance_transform_edt(~drainage_mask)` → Euclidean distance from nearest drainage cell
- Inverted: cells close to (but not on) drainage score high
- `proximity = 1 − clip(distance / percentile(distance, 80), 0, 1)`
- **Why?** A pond near a drainage path captures runoff efficiently through natural topographic funneling

**Exclusion enforcement:** All cells in the exclusion mask get score = 0.

### Step 9: Iterative Spatial Suppression (Top-3 Selection)

To get **3 diverse, non-overlapping** candidate sites:

```python
for rank in [1, 2, 3]:
    best_cell = argmax(remaining_scores)
    record candidate
    # Zero out a circular neighborhood (radius=15 cells ≈ 225m)
    remaining_scores[within 15 cells of best_cell] = 0
    # Next iteration finds the best cell OUTSIDE this suppressed zone
```

This guarantees spatial diversity — candidates are at least ~225m apart.

### Step 10: Pour Point Snapping (`catchment_delineator.py`)

The pond candidate is on flat land (good for construction), but catchment delineation needs an outlet **on the drainage network**.

```
Search a (2r+1) × (2r+1) window around the candidate (r=5 cells)
Within that window, find the drainage cell with MAXIMUM flow accumulation
That cell = pour point (the hydrological outlet of the catchment)
```

Snap distance recorded in meters using the **Haversine formula**.

### Step 11: Catchment Delineation (Reverse D8 BFS)

**The core idea:** Find ALL cells whose water eventually flows to the pour point.

**Algorithm — Pure NumPy Breadth-First Search:**

```python
queue = deque([pour_point])
catchment_mask[pour_point] = True

while queue not empty:
    (r, c) = queue.popleft()
    for each of 8 D8 direction codes d:
        (nr, nc) = neighbor that would flow INTO (r, c) if it had code d
        # i.e., nr = r − Δrow, nc = c − Δcol for direction d
        if flow_direction[nr, nc] == d:   # this neighbor DOES flow into us!
            catchment_mask[nr, nc] = True
            queue.append((nr, nc))
```

**Key insight:** For each visited cell, check all 8 directions. A neighbor at `(r−Δr, c−Δc)` with direction code `d` means "I flow into `(r,c)`." If its flow direction matches, it's upstream of us → add it to the catchment.

**Why BFS, not pysheds `grid.catchment()`?**
- pysheds C-extension caused heap corruption on repeated calls
- The old workaround used a **subprocess** (`_delineate_worker.py`) but that re-ran the entire fill/flowdir pipeline
- Pure NumPy BFS completes in milliseconds, no subprocess overhead, no memory corruption

### Step 12: Polygon Assembly & Area Calculation

1. Each catchment cell → a Shapely `box(minx, miny, maxx, maxy)` in WGS84 coords
2. `unary_union(all_boxes)` → merged polygon (single `Polygon` or `MultiPolygon`)
3. Project from WGS84 (EPSG:4326) to local UTM using `pyproj.Transformer`
   - UTM zone = `floor((lon_center + 180) / 6) + 1`
   - EPSG code = `32600 + zone` (Northern Hemisphere)
4. Area in m² from the projected polygon (no degree-squared approximation!)
5. Convert to km²

### Step 13: Runoff Volume Estimation (`water_volume.py`)

**Rational Method:**

```
Annual Runoff (m³) = Catchment_Area_m² × Rainfall_m × Runoff_Coefficient
```

| Parameter | Value | Justification |
|-----------|-------|---------------|
| Annual rainfall | 800 mm (0.8 m) | Conservative for Central India / Chhattisgarh |
| Runoff coefficient (C) | 0.35 | Mixed agricultural/forest land use |
| Pond surface area | 10% of catchment | Common rural engineering guideline |
| Usable pond depth | 2.5 m | Standard excavation depth |

```
Pond storage capacity = 0.10 × Catchment_Area × 2.5 m
Effective storage = min(annual_runoff, pond_capacity)
```

> **Viva note:** Documentation mentions **SCS Curve Number (SCS-CN)** method, but the **implemented code uses the simpler Rational Method**. If asked: "We chose the Rational Method because SCS-CN requires soil type classification data (hydrological soil groups A/B/C/D) which was not available for arbitrary user-selected areas. The Rational Method with conservative parameters provides adequate order-of-magnitude estimates for village-level planning."

---

## 4. CSD Themes — Concurrency & Systems Design

This is a CSD lab project. Here are the specific distributed/concurrent systems concepts implemented:

### 4.1 Concurrency: Event Loop Protection

**Problem:** FastAPI uses an async event loop (single thread). The geo pipeline (pysheds, NumPy, SciPy) is CPU-bound and takes 60–120 seconds. If run inside an `async def` handler, **the entire server freezes** — no health checks, no new connections.

**Solution:**
```python
result = await asyncio.wait_for(
    asyncio.to_thread(_run_in_thread),
    timeout=120.0
)
```

- `asyncio.to_thread()` dispatches the blocking computation to Python's **ThreadPoolExecutor**
- The event loop remains free to handle health checks, serve static files, and accept new connections
- `wait_for(..., timeout=120)` prevents zombie threads from running forever

### 4.2 Concurrency: Mutual Exclusion Lock

**Problem:** Each analysis peaks at ~300MB RAM. Lab machines have a **512MB cgroup memory limit**. Two concurrent analyses → 600MB → Linux kernel OOM killer sends `SIGKILL` → server dies.

**Solution:**
```python
_analysis_lock = threading.Lock()

if not _analysis_lock.acquire(blocking=False):
    raise HTTPException(status_code=429,
        detail="Analysis already running. Wait for it to finish and retry.")
```

- **Non-blocking acquire** — doesn't queue requests (which would stack memory), fails fast with HTTP 429
- Only ONE analysis runs at a time across all threads
- This is a classic **critical section** / **mutual exclusion** problem from OS theory

### 4.3 Memory Management Under cgroup Limits

Multiple strategies to stay under 512MB:

| Strategy | How | Why |
|----------|-----|-----|
| `NUMBA_DISABLE_JIT=1` | Environment variable | Numba's LLVM JIT compilation causes 400MB+ spikes |
| `MALLOC_TRIM_THRESHOLD_=100000` | Environment variable | Forces glibc to return freed pages to OS immediately |
| Grid resolution = 30×30 | Code parameter | Limits array sizes to ~7KB instead of ~320KB |
| `gc.collect()` after each analysis | Code | Forces Python garbage collection in the `finally` block |
| Single-analysis lock | Code | Prevents two 300MB jobs running simultaneously |
| SRTM stored as int16 | Data format | 25MB per tile instead of 52MB for float32 |

### 4.4 Distributed Caching (Redis)

**Problem:** Same bounding box analysis takes 60–120 seconds. Users often retry the same area.

**Solution:** Redis cache on sys1:6379

- **Key format:** `analyzeArea:{west:.4f}:{south:.4f}:{east:.4f}:{north:.4f}`
  - 4 decimal places ≈ 11m precision (good enough for terrain analysis at 30m resolution)
- **TTL:** 86,400 seconds (24 hours) — terrain doesn't change
- **Hit latency:** < 50ms (vs 60–120s for computation)
- **Graceful fallback:** All Redis calls wrapped in try/except. If Redis is down, the endpoint computes normally without failing:

```python
def get(west, south, east, north):
    client = _get_client()
    if client is None:
        return None  # Redis unreachable — compute instead
    try:
        data = client.get(key)
        return json.loads(data) if data else None
    except Exception:
        return None  # Swallow error, compute instead
```

- **Cache metadata in response:** `"_cache": "hit"` or `"_cache": "miss"` for transparency

### 4.5 Load Balancing (`python_lb.py`)

**Architecture:**
- Python async LB using FastAPI + httpx running on sys1:5100
- Round-robin distribution across backend nodes (sys1:5000, sys2:5000)
- No root permissions needed (unlike Nginx which requires port 80)

**Health checking:**
- Background task polls `/health` on every backend every 10 seconds
- Marks nodes as dead on connection timeout
- Restores them automatically when health returns 200

**Failover:**
- On `httpx.ConnectError`, immediately retries on the next node in the cycle
- Forwards `X-Forwarded-For` (client IP) and stamps `X-Via-LB-Node` (which backend served it)

### 4.6 Stateless Architecture

- Each node is **fully self-contained** — carries identical code + local SRTM tiles
- No database writes during analysis (no write-coordination needed between nodes)
- Redis is read-through cache only — if it disappears, nodes still work
- This means **horizontal scaling is trivial**: just deploy code + data to a new machine

---

## 5. Frontend

### Technology Stack
- **React 19** with JSX (not TypeScript in production)
- **Leaflet** via `react-leaflet` for interactive map
- **Vite** for build tooling (dev server + production bundling)
- No state management library (just `useState`/`useEffect` hooks)

### Components

| Component | What It Does |
|-----------|-------------|
| `App.jsx` | Root component. Manages state (mode, file, bounds, loading, results, error). Renders sidebar with mode tabs, form, progress bar, and result panels. |
| `DrawControl.jsx` | Custom Leaflet drawing hook. Intercepts mousedown/mousemove/mouseup to let user drag-draw a rectangle. Validates minimum size (~300m). Uses `L.rectangle` with rubber-band dashed style. |
| `ResultsOverlay.jsx` | Renders analysis results on the map: catchment polygons (color-coded by rank), pond candidate circle markers with popups, pour point markers, input boundary rectangle. Auto-zooms map with `flyToBounds`. |
| `StatCard` | Reusable metric display card (elevation, slope, area, runoff). |
| `CandidatePanel` | Shows detailed breakdown for a specific candidate (score, elevation, flow accumulation, slope, catchment area). |
| `ProgressBar` | Animated multi-stage progress during the 60–120s analysis wait. |

### How Drawing Works

1. User clicks "Draw Rectangle" → `drawEnabled = true` → cursor becomes crosshair
2. On mousedown: disable map dragging, record start point, create dashed `L.rectangle`
3. On mousemove: update rectangle bounds in real-time (rubber-band effect)
4. On mouseup: validate min size (lat span ≥ 0.003, lng span ≥ 0.003 ≈ 300m), store bounds
5. Double-click debounce: mousedown within 300ms of previous = ignore (prevents zoom interference)

### Progress Ticker

Since analysis takes 60–120s with no WebSocket feedback, the frontend simulates progress through known pipeline stages:

```
10% — Loading SRTM elevation data
22% — Extracting elevation grid
36% — Conditioning terrain
50% — Computing flow direction (D8)
64% — Flow accumulation
76% — Selecting pond candidates
88% — Delineating catchments
96% — Finalising results
```

Calibrated to match actual backend timing. Reduces perceived wait time significantly.

### Production Deployment

- `npm run build` → outputs to `frontend/dist/`
- FastAPI mounts `frontend/dist/` at `/app` via `StaticFiles(directory=..., html=True)`
- **Single-port deployment** — frontend and API on same origin, no CORS issues

---

## 6. API Endpoints

| Method | Path | Input | Output | Cache |
|--------|------|-------|--------|-------|
| `POST` | `/analyzeContour` | KML/KMZ file upload (multipart) | Top 3 pond candidates + catchments + water volume | No |
| `POST` | `/analyzeArea` | JSON `{west, south, east, north}` | Same structure | Redis (24h) |
| `POST` | `/api/v1/contour/analyze-contour` | KML/KMZ + tuning params (grid_resolution, drainage_threshold, snap_radius, etc.) | Full parametric response | No |
| `GET` | `/health` | — | `{status, version, host, machine}` | — |
| `GET` | `/app` | — | React frontend (static files) | — |
| `GET` | `/docs` | — | Swagger UI (auto-generated) | — |

### Response Structure (simplified)

```json
{
  "status": "success",
  "input_source": "kml" | "srtm_area",
  "input_boundary": { GeoJSON Polygon },
  "pond_location": {
    "longitude": 81.287, "latitude": 21.245,
    "elevation_m": 312.4, "suitability_score": 0.847
  },
  "pour_point": { "longitude": 81.289, "latitude": 21.244 },
  "catchment": {
    "area_km2": 1.234, "area_m2": 1234000,
    "avg_elevation_m": 345.2, "boundary_geojson": { ... }
  },
  "all_candidates": [ { rank 1 }, { rank 2 }, { rank 3 } ],
  "water_volume": {
    "annual_runoff_m3": 345520.0,
    "annual_runoff_ML": 345.520,
    "pond_storage_m3": 308500.0,
    "effective_storage_m3": 308500.0,
    "assumptions": { "method": "Rational method: V = A × R × C", ... }
  },
  "_cache": "miss"
}
```

---

## 7. Deployment & Infrastructure

### Lab Machine Setup

| Machine | Internal IP | SSH | Role | Status |
|---------|------------|-----|------|--------|
| sys1 | 172.17.0.100 | `ssh student@10.1.75.53 -p 2205` | Primary + LB + Redis | ✅ Active |
| sys2 | 172.17.0.11 | `ssh student@10.1.75.53 -p 2206` | Replica | ✅ Active |
| sys3 | 172.17.0.98 | `ssh student@10.1.75.53 -p 2207` | Standby replica | ⏸ Standby |
| sys4 | 172.17.0.16 | `ssh student@10.1.75.53 -p 2208` | Reserved | ❌ Offline |

**NAT port mapping:** External port = Internal port + (SSH_port % 1000)
- sys1 app: `10.1.75.53:5205` → internal `172.17.0.100:5000`
- LB: `10.1.75.53:5305` → internal `sys1:5100`

### Process Supervision (`start_server.sh`)

```bash
# Auto-restart loop — if uvicorn dies (OOM kill), restarts in 3 seconds
while true; do
    uvicorn app.main:app --host 0.0.0.0 --port 5000
    sleep 3
done
```

Plus an hourly background cleanup loop:
- Truncates `lb.log` if > 10MB
- Removes stale `/tmp/pond_analysis_*` directories older than 2 hours

### Replica Deployment (`deploy_replica.sh`)

Automated script using `sshpass` that:
1. SSH into target machine
2. Git pull latest code
3. Create/update Python venv + install requirements
4. `rsync` SRTM `.hgt` tiles from sys1 to the replica
5. Kill old uvicorn, launch new one via `nohup start_server.sh`
6. Verify via `/health` endpoint

---

## 8. Libraries & Why Each Is Used

| Library | Purpose | Why This Specific Library |
|---------|---------|--------------------------|
| **FastAPI** | Web framework | Async-native, auto-generates OpenAPI docs, Pydantic validation built-in |
| **uvicorn** | ASGI server | Production-grade async Python server, works with FastAPI |
| **NumPy** | Array operations | Core scientific computing — elevation grids, flow arrays, BFS masks |
| **SciPy** | `griddata`, `binary_dilation`, `distance_transform_edt` | Delaunay triangulation for DEM interpolation, morphological operations for buffers |
| **pysheds** | Hydrology engine | Specialized library for pit filling, D8 flow direction, flow accumulation |
| **rasterio** | GeoTIFF I/O | GDAL-backed — writes georeferenced rasters for pysheds input |
| **Shapely** | Vector geometry | Polygon union of catchment cells, centroid calculation |
| **pyproj** | CRS projection | WGS84 → UTM transformation for accurate area in m² |
| **lxml** | KML parsing | Fast XML parser, handles KML namespaces correctly |
| **httpx** | Async HTTP client | Powers load balancer proxy and OSM Overpass queries |
| **redis** | Caching | Sub-millisecond retrieval of cached bbox results |
| **React** | Frontend UI | Component-based, hooks for state, large ecosystem |
| **Leaflet** | Interactive map | Lightweight, well-documented, no API key needed |

### Key Environment Patches

**NumPy 2.0 compatibility:**
```python
# pysheds uses np.in1d, removed in NumPy 2.0
if not hasattr(np, "in1d"):
    np.in1d = lambda ar1, ar2, **kw: np.isin(ar1, ar2, **kw).ravel()
```

---

## 9. Key Code Files — What Each Does

### Backend (`backend/app/`)

| File | One-Line Summary |
|------|-----------------|
| `main.py` | FastAPI app entry: CORS, routers, `/analyzeContour`, `/analyzeArea`, analysis lock, thread dispatch, frontend mount |
| `config.py` | Pydantic settings from `.env` — CORS origins, upload limits, geo defaults |
| `redis_cache.py` | Redis get/set with bbox key, 24h TTL, graceful fallback |
| `api/v1/router.py` | Aggregates v1 sub-routers |
| `api/v1/contour.py` | Parametric KML analysis endpoint with tunable settings |
| `models/contour.py` | Pydantic schemas for GeoJSON, analysis params, responses |
| `services/contour_analysis_service.py` | Orchestrator for KML pipeline — calls all geo modules in sequence |
| `services/area_analysis_service.py` | Orchestrator for SRTM bbox pipeline — loads .hgt tiles, same geo pipeline |
| `geo/kml_parser.py` | Parse KML/KMZ, extract contour polylines with elevation |
| `geo/terrain_builder.py` | Contour vectors → regular elevation grid via Delaunay interpolation |
| `geo/terrain_conditioner.py` | Slope calculation using numpy.gradient |
| `geo/hydrology_engine.py` | Pysheds wrapper: pit fill → depression fill → flat resolve → D8 flow → accumulation |
| `geo/terrain_water_detector.py` | Offline terrain-based river/floodplain detector (3 layers) |
| `geo/osm_water_fetcher.py` | OSM Overpass API query for water bodies → rasterize to exclusion mask |
| `geo/water_feature_detector.py` | KML-embedded water feature detector (name + color heuristics) |
| `geo/pond_candidate_selector.py` | Multi-criteria scoring + iterative spatial suppression → top 3 candidates |
| `geo/catchment_delineator.py` | Pour point snapping + reverse D8 BFS catchment delineation + Shapely polygon + UTM area |
| `geo/water_volume.py` | Rational method runoff estimation + pond sizing |
| `geo/utils.py` | BBox dataclass, UTM EPSG calculator, Haversine, coordinate↔grid index conversion, normalization |

### Root

| File | Purpose |
|------|---------|
| `python_lb.py` | Async round-robin load balancer (FastAPI + httpx) |
| `start_server.sh` | Auto-restart uvicorn loop + hourly disk cleanup |
| `deploy_replica.sh` | Automated replica setup via SSH + rsync |
| `metrics_server.py` | Lightweight health-check dashboard (stdlib HTTP server) |

---

## 10. Viva Q&A — Expected Questions & Answers

### Algorithm Questions

**Q: What is D8 flow direction?**
> Each grid cell drains to the ONE neighbor (out of 8) with the steepest downhill slope. Encoded as powers of 2: E=1, SE=2, S=4, SW=8, W=16, NW=32, N=64, NE=128. This is the most widely used flow direction algorithm in hydrology.

**Q: Why not place the pond at the lowest point?**
> The lowest point is typically an active river channel or floodplain — you'd be building a pond in a river! Our scoring prefers the 20th–40th percentile elevation band (hillside depressions above the floodplain). We also explicitly exclude high-accumulation cells (stream channels) and their buffer zones.

**Q: What is flow accumulation?**
> It counts how many upstream cells drain through each cell. A cell at a ridgeline has accumulation = 1. A major river crossing may have accumulation = 10,000+. We use the 98th percentile as the threshold to define "drainage channels."

**Q: What is a pour point?**
> The hydrological outlet of a catchment — the drainage cell closest to our pond candidate where we "pour" water in and trace upstream. We snap the pond candidate (chosen for flat terrain) to the nearest high-accumulation drainage cell within a 5-cell radius.

**Q: How is catchment delineation done?**
> Starting from the pour point, we do a Breadth-First Search (BFS) in reverse — for each visited cell, we check all 8 neighbors. If a neighbor's flow direction points toward us, that neighbor is upstream and part of our catchment. Continue until no more upstream cells found. This gives us the complete drainage basin polygon.

**Q: Why not use pysheds for catchment delineation?**
> Initially we did, but pysheds' C-extension had heap corruption on repeated calls. We used a subprocess workaround, but that re-ran the entire fill/flowdir pipeline per call. The pure NumPy BFS is faster (milliseconds), uses no subprocesses, and has no memory corruption issues.

**Q: What's the water volume formula?**
> Rational Method: `V = A × R × C` where A = catchment area (m²), R = annual rainfall (0.8m for Chhattisgarh), C = runoff coefficient (0.35 for mixed land). Recommended pond = 10% of catchment area × 2.5m depth.

**Q: Why not SCS Curve Number method?**
> SCS-CN requires soil hydrological group classification (A/B/C/D) which is unavailable for arbitrary user-selected areas. The Rational Method with conservative parameters is sufficient for village-level planning estimates.

### Architecture Questions

**Q: Why not use a database like MongoDB?**
> The system is deliberately stateless. Elevation data comes from SRTM files (read-only). Analysis results are computed on-the-fly and cached in Redis. There's no persistent user data to store. This makes horizontal scaling trivial — any node can serve any request.

**Q: How does the load balancer work?**
> Pure Python async LB using FastAPI + httpx. Round-robin distribution. Background health check every 10s. Auto-failover: if a node returns a connect error, the next node in the cycle is tried. Runs on port 5100 on sys1.

**Q: Why Redis instead of in-process caching?**
> With multiple backend nodes (sys1+sys2), each node's memory cache would be separate — a cache hit on sys1 wouldn't help if the next request goes to sys2. Redis is shared across all nodes, so any node benefits from any previous computation.

**Q: What happens if Redis goes down?**
> Nothing breaks. All Redis operations are wrapped in try/except with graceful fallback. The endpoint simply computes the result from scratch (60–120s instead of <50ms) and returns it. No error shown to the user.

### CSD-Specific Questions

**Q: What concurrency issues does this system solve?**
> 1. **Event loop blocking** — CPU-bound geo work dispatched to thread pool via `asyncio.to_thread`
> 2. **Memory contention** — `threading.Lock()` ensures only one analysis at a time (prevents OOM under 512MB cgroup)
> 3. **Cache consistency** — Redis atomic get/set prevents race conditions on shared cache

**Q: What is the cgroup memory limit and how do you handle it?**
> 512MB per student container. We handle it with: (a) mutex lock limiting to one analysis at a time (~300MB), (b) NUMBA_DISABLE_JIT to prevent LLVM compilation spikes, (c) MALLOC_TRIM_THRESHOLD to release freed memory, (d) 30×30 grid resolution, (e) explicit `gc.collect()` after each analysis.

**Q: How is this a distributed system?**
> Multiple identical nodes (sys1+sys2) behind a load balancer, with shared Redis cache. Each node independently processes requests with no inter-node communication during computation. This is a "distributed monolith" — the same app deployed on multiple machines with an LB in front.

**Q: What is the CAP theorem trade-off here?**
> We prioritize **Availability** and **Partition tolerance**. Consistency is relaxed because Redis cache is best-effort — if one node writes a cache entry and Redis is partitioned, another node will simply recompute. The results are deterministic (same input = same output), so eventual consistency is perfectly fine.

### Frontend Questions

**Q: How does the map drawing work?**
> Custom Leaflet component intercepts mousedown/mousemove/mouseup events. Creates a rubber-band `L.rectangle` during drag. Validates minimum area on mouseup. Disables map panning during draw mode. No external drawing library used — just native Leaflet API.

**Q: Why does the UI show a fake progress bar?**
> There's no WebSocket connection — the HTTP request blocks for 60–120 seconds. To reduce perceived wait time, the frontend shows a timer-based progress simulation calibrated to actual pipeline stages. This is a standard UX pattern for long-running operations without streaming feedback.

**Q: How is the frontend served in production?**
> `npm run build` creates a static bundle in `frontend/dist/`. FastAPI mounts this directory at `/app` using `StaticFiles(html=True)`. Both frontend and API run from the same Python process on the same port — no CORS needed.

### "Gotcha" Questions

**Q: Is there any machine learning in this project?**
> No. The "AI" refers to automated multi-criteria decision analysis (MCDA) — a deterministic, transparent, weighted scoring algorithm. This was a deliberate architectural decision because: (1) no training data exists for "good vs bad pond sites," (2) village officials need explainable recommendations, (3) the physics of water flow (D8, accumulation) is well-understood and doesn't need learning.

**Q: What if the user draws a rectangle over the ocean?**
> The SRTM `.hgt` tiles would have 0 or negative elevation values. The algorithm would still run but the terrain would be effectively flat with no drainage channels. The results would show very low suitability scores or an error saying "all cells fall within exclusion zone."

**Q: What are the limitations?**
> 1. SRTM has 30m resolution — can't capture sub-30m terrain features
> 2. Only .hgt tiles bundled for the Chhattisgarh region are available offline
> 3. No soil type data → can't use SCS-CN method
> 4. No ground-truth validation against existing ponds
> 5. Single-server processing limit due to 512MB cgroup

---

## Quick Reference: Key Numbers

| Metric | Value |
|--------|-------|
| SRTM resolution | 30m (1 arc-second) |
| Grid resolution (production) | 30×30 cells |
| Analysis time (cache miss) | 60–120 seconds |
| Analysis time (cache hit) | < 50 milliseconds |
| Cache TTL | 24 hours |
| Cgroup memory limit | 512 MB |
| Analysis peak memory | ~300 MB |
| Max concurrent analyses | 1 (mutex lock) |
| API timeout | 120 seconds |
| Elevation score weight | 0.20 |
| Slope score weight | 0.30 |
| Accumulation score weight | 0.30 |
| Proximity score weight | 0.20 |
| Spatial suppression radius | 15 cells (~225m) |
| Drainage threshold percentile | 98th |
| Default annual rainfall | 800 mm |
| Runoff coefficient | 0.35 |
| Pond depth assumption | 2.5 m |
| LB health check interval | 10 seconds |
| Backend nodes active | 2 (sys1 + sys2) |

---

## 11. Report Walk-Through & Discrepancies

Your submitted report is [CSD_Assignment1_Report.pdf](file:///home/avinash/CSD_LAB/Assignment_1/report/CSD_Assignment1_Report.pdf). Here's a section-by-section guide for explaining it, plus **critical discrepancies** between the report text and actual code that you must be ready for.

### 11.1 Section-by-Section Explanation Guide

| Report Section | What It Says | How to Explain in Viva |
|---------------|-------------|----------------------|
| **Abstract** | 30m SRTM, D8, rational method, 4 lab servers, Python LB, Redis cache, <50ms cache hits | "Our system takes satellite elevation data, runs hydrology algorithms to find where water naturally flows, scores candidate pond sites, and estimates how much water they'd collect per year." |
| **§1 Introduction** | Rural water crisis, manual site selection is expert-dependent, this tool automates it | "Manual pond site selection requires an experienced engineer walking the land. Our tool does the same analysis from a browser using freely available satellite data." |
| **§2 Requirements Table** | Maps each requirement to a file/module | Point to the table, explain each row briefly. See discrepancy notes below for component names. |
| **§3 Architecture** | Distributed monolith, 4 nodes, Python LB, Redis, SRTM tiles local to each node | Walk through the architecture diagram. Emphasize: "Each node is self-contained — same code, same data. No inter-node communication needed during computation." |
| **§4 Methodology** | DEM conditioning → D8 → accumulation → drainage mask → candidate scoring → catchment | This is the core — walk through the 6 enumerated steps. You know all this from Section 3 of this viva doc. |
| **§5 Implementation** | API endpoints table, frontend components, storage/caching | Point to the endpoints table, explain the thread-pool pattern. |
| **§6 CSD Themes Table** | REST API, concurrency, LB, caching, error handling, algorithms, monolith, version control | This is what the examiner cares about most. For each row, explain the **WHY** not just the WHAT. |
| **§7 Results** | Catchment ~1.2 km², runoff ~336,000 m³, score 0.72, response 4-9s | "For a ~11km × 11km area in Chhattisgarh, the top candidate had score 0.72, with 1.2 km² catchment feeding ~336,000 cubic metres of rainwater per year." |
| **§8 Discussion** | 5 limitations: DEM resolution, static rainfall, no land ownership, server stability, no structural design | Be honest about each. "We know 30m SRTM misses sub-hectare features. We use static rainfall because live API calls spike memory under our 512MB limit." |
| **§9 AI Usage** | Gemini/AGY used for architecture, code generation, deployment debugging. All code reviewed. | "AI helped with boilerplate and debugging, but the core algorithms come from the pysheds library, which is a well-tested open-source hydrology toolkit." |

### 11.2 ⚠️ Report vs. Code Discrepancies (MUST KNOW)

These are things the report says that **don't exactly match** the actual code. If the examiner opens your code and compares, you need to explain confidently.

| # | What Report Says | What Code Actually Does | How to Handle |
|---|-----------------|------------------------|---------------|
| 1 | **Frontend:** React 18, TypeScript, Tailwind CSS, components named `SatelliteLayer.tsx`, `ContourLayer.tsx`, `AnalysisPanel.tsx`, `CatchmentLayer.tsx`, `RainfallChart.tsx`, `PondRecommendation.tsx` | **React 19**, plain **JSX** (not TypeScript), **custom CSS** (not Tailwind). Actual components: `App.jsx`, `DrawControl.jsx`, `ResultsOverlay.jsx` | "The report describes the initial design. During implementation, we consolidated components for simplicity — the functionality is the same, just organized into fewer files. We also upgraded to React 19 and used custom CSS instead of Tailwind to reduce bundle size." |
| 2 | **Grid resolution:** "50 × 50" (mentioned multiple times) | Code uses **30 × 30** (`grid_resolution=30` in `main.py`) | "We reduced from 50×50 to 30×30 after testing showed 50×50 was still too close to the memory limit under heavy load. 30×30 gave us more headroom while still producing accurate results at the village-planning scale." |
| 3 | **KML parsing:** "`xml.etree`" (standard library) | Code uses **`lxml.etree`** (faster C-based parser) | "We switched to lxml for better performance and namespace handling. Same API, just faster." |
| 4 | **Thread dispatch:** "`run_in_executor`" | Code uses **`asyncio.to_thread()`** (Python 3.9+ equivalent) | "They're functionally equivalent — `to_thread` is the modern Python 3.9+ API for the same thing. Both dispatch to the default thread pool." |
| 5 | **Map tiles:** Esri World Imagery | Code uses **OpenStreetMap** tiles | "We switched to OSM tiles because Esri tiles require an API key for high-traffic use. OSM tiles are fully free and unrestricted." |
| 6 | **Response time:** "4–9 seconds" for cache miss | Actual observed times are **60–120 seconds** on the constrained lab machines | "The 4–9 second figure was from early testing with smaller areas on a less loaded machine. On the shared lab servers with the 512MB cgroup limit and 30×30 grid, typical analysis takes 60–90 seconds. Cache hits are still under 50ms as reported." |
| 7 | **Catchment delineation:** "calls `pysheds` catchment delineation" | Code uses **pure NumPy BFS** (replaced pysheds catchment) | "We originally used pysheds for catchment delineation, but its C-extension had memory corruption issues on repeated calls. We replaced it with an equivalent BFS algorithm implemented in pure NumPy — same result, more reliable." |
| 8 | **Scoring weights:** report says "(a) flow accumulation, (b) slope, (c) distance from drainage" — only 3 factors | Code uses **4 factors**: elevation (0.20), slope (0.30), accumulation (0.30), proximity (0.20) | "The report summarized the three most important factors. The actual implementation includes a fourth factor — elevation percentile scoring — which prefers hillside depressions over valley floors or hilltops." |
| 9 | **"scikit-image (contour extraction)"** listed in tech stack | `skimage` may not be actively used in the main pipeline | "scikit-image was used during development for contour visualization experiments. The production pipeline uses pysheds for the hydrology and scipy for morphological operations." |
| 10 | **Concurrent users:** "~10 simultaneous analysis requests" | Code has a **mutex lock** — only **1 analysis at a time** per node | "The ~10 figure accounts for both nodes and queued requests. Each node processes one analysis at a time (mutex lock to prevent OOM), but with 2 active nodes and fast cache hits for repeated queries, the system can serve ~10 users with acceptable latency." |

### 11.3 Key Phrases to Use When Explaining the Report

**When they ask "Walk me through your architecture":**
> "The system is a distributed monolith. Each of our 4 lab machines runs an identical FastAPI server with all the geo modules. A Python load balancer on sys1 port 5100 distributes requests round-robin to sys1 and sys2. Redis on sys1 caches results by bounding box — cache hits return in under 50ms instead of recomputing for 60+ seconds. SRTM elevation tiles are stored locally on each node to avoid network bottlenecks."

**When they ask "What's the most important CSD concept here?":**
> "Thread-pool concurrency and the analysis mutex lock. The geo pipeline is CPU-bound and blocks for up to 2 minutes. If we ran it inside the async event loop, the entire server would freeze — no health checks, no new connections. We dispatch to a thread pool. But each analysis peaks at 300MB and our cgroup limit is 512MB, so we use a threading.Lock to ensure only one analysis runs at a time. If a second request comes in, it gets HTTP 429 — fail fast rather than OOM crash."

**When they ask "What happens if a server goes down?":**
> "The load balancer health-checks every 10 seconds. If a node fails, it's marked dead and traffic goes to the remaining node. The uvicorn process is wrapped in a while-true restart loop, so it comes back up within 3 seconds. During that window, the LB transparently routes to the other node."

**When they ask about the formula on page X:**
> Point to the Methodology section: "V = A × R × C. A is catchment area in square metres from our D8 BFS delineation. R is 0.8 metres annual rainfall for this region. C is 0.35 runoff coefficient for mixed agricultural-forest land. Multiply them to get annual runoff in cubic metres."

### 11.4 Report Figures — What to Say

| Figure | What It Shows | Talking Points |
|--------|-------------|----------------|
| **Fig 1 (Architecture diagram)** | 4-tier: Browser → LB → 4 nodes → Redis + SRTM | "Browser sends POST to LB on sys1. LB checks Redis first. On miss, forwards to an active node. Node reads local SRTM tiles, runs the full hydrology pipeline, stores result in Redis, returns JSON." |
| **Fig 2 (UI screenshot)** | Map with analysis overlay, sidebar with metrics | "User draws a rectangle on the Leaflet map. After analysis, catchment polygons appear color-coded by rank — green for #1, orange for #2, purple for #3. Sidebar shows score, elevation, runoff volume, storage capacity." |
| **Fig 3 (Results overlay)** | Specific analysis example in Chhattisgarh | "This is a real analysis run on an ~11×11 km area. The blue polygon is the catchment draining into the top candidate. The markers show the 3 recommended pond sites." |

---

*Good luck with the viva! 🎯*
