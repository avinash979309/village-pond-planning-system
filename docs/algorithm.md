# Algorithm: Pond Site Selection & Catchment Delineation

## Overview

This system identifies optimal **rainwater harvesting pond locations** from contour map data (KML/KMZ), computes their **catchment areas**, and returns up to three ranked candidate sites. The algorithm is fully **data-driven** — no hardcoded coordinates, elevation values, river names, or region-specific constants. Every threshold is derived from percentiles of the input data, so the method works on any contour map regardless of geography.

---

## Pipeline Stages

```
KML/KMZ Upload
      |
      v
Stage 1:  Parse Contour Lines         [kml_parser.py]
      |
      v
Stage 2:  Detect Explicit Water       [water_feature_detector.py]
      |
      v
Stage 3:  Build Elevation Grid (DEM)  [terrain_builder.py]
      |
      v
Stage 4:  Compute Slope               [terrain_conditioner.py]
      |
      v
Stage 5:  Hydrological Analysis       [hydrology_engine.py]
      |     D8 Flow Direction
      |     Flow Accumulation
      |     Drainage Network + Exclusion Mask
      |
      v
Stage 6a: Terrain Water Detection     [terrain_water_detector.py]
Stage 6b: OSM Water Body Exclusion    [osm_water_fetcher.py]
      |
      v
Stage 7:  Pond Candidate Selection    [pond_candidate_selector.py]
      |     Weighted Suitability Scoring
      |     Iterative Spatial Suppression -> Top-N Candidates
      |
      v
Stage 8:  Pour Point Snapping         [catchment_delineator.py]
      |
      v
Stage 9:  Catchment Delineation       [catchment_delineator.py]
      |
      v
Stage 10: Result Assembly             [contour_analysis_service.py]
```

---

## Stage 1 — Parse Contour Lines

**Module**: `kml_parser.py`

The KML/KMZ file is parsed to extract:
- **Contour polylines**: sequences of (longitude, latitude, elevation) points.
- **Other features**: polygons/linestrings that may represent explicit water bodies.
- **Bounding box**: spatial extent covering all contour data.

Each contour line is stored as `ContourLine(elevation_m, coordinates)`. Elevation is read from the KML `<altitudeMode>` or placemark name.

---

## Stage 2 — Detect Explicit Water Features

**Module**: `water_feature_detector.py`

If the KML encodes river or lake polygons as named placemarks, their geometry is extracted for exclusion. Supplemented by terrain-based and OSM detection in Stages 6a/6b.

---

## Stage 3 — Build Elevation Grid (DEM)

**Module**: `terrain_builder.py`

### 3.1 Point Sampling

Each contour polyline is sampled uniformly by arc length (up to 50 points per contour), converting vector contour lines into an **irregular point cloud** of (lon, lat, elevation) triples.

### 3.2 Grid Construction

A regular **N x N grid** (default N=200 cells per axis) is defined over the bounding box. Each grid cell is approximately 15–50 m on the ground depending on map extent.

### 3.3 Interpolation

| Pass | Method | Purpose |
|------|--------|---------|
| Primary | `scipy.griddata` linear (Delaunay triangulation) | Smooth surface inside convex hull of sample points |
| Gap fill | `scipy.griddata` nearest neighbour | Fills boundary cells outside convex hull |

**Why linear, not cubic?** At 1 m contour intervals, adjacent contours are close. Cubic splines can produce oscillations between nearly-parallel contours. Linear avoids this.

Result: 2D array `elev_grid[row, col]`, row 0 = northernmost row.

---

## Stage 4 — Slope Computation

**Module**: `terrain_conditioner.py`

Central difference of elevation grid:

```
dz/dx = (elev[r, c+1] - elev[r, c-1]) / (2 * cell_width_m)
dz/dy = (elev[r+1, c] - elev[r-1, c]) / (2 * cell_height_m)
slope_degrees = arctan(sqrt((dz/dx)^2 + (dz/dy)^2)) * (180/pi)
```

Cell dimensions in metres computed via Haversine formula from bounding box and grid resolution.

---

## Stage 5 — Hydrological Analysis

**Module**: `hydrology_engine.py`  
**Library**: [pysheds](https://mattbartos.com/pysheds/) — standard GIS hydrology toolkit

### 5.1 DEM Conditioning

Three preprocessing steps to ensure every cell has a defined downhill neighbour:

1. **Pit filling** — removes single-cell sinks by raising them to their lowest neighbour.
2. **Depression filling** — fills enclosed multi-cell basins (raises basin floor to lowest outlet elevation).
3. **Flat resolution** — adds tiny artificial gradient across flat areas so D8 can assign flow directions.

### 5.2 D8 Flow Direction

Each cell is assigned one of 8 encoded directions indicating which neighbour is lowest:

```
  NW(32) N(64) NE(128)
  W(16)   .    E(1)
  SW(8)  S(4)  SE(2)
```

The neighbour with the steepest downhill gradient receives all flow. Ties broken deterministically.

### 5.3 Flow Accumulation

```
flow_accumulation[r,c] = count of all cells that route to [r,c]
                         (directly or transitively through D8 chains)
```

High accumulation = stream channel (many upstream slopes converge here).

### 5.4 Drainage Network

```
threshold = percentile(flow_accumulation, 100 - drainage_threshold_pct)
          = percentile(flow_accumulation, 98)    [default 2%]

drainage_mask[r,c] = True  if  flow_accumulation[r,c] >= threshold
```

Threshold derived from the data — no fixed accumulation value hardcoded.

### 5.5 Exclusion Mask

```
exclusion_mask = binary_dilation(drainage_mask, radius=drainage_buffer_cells)
```

Default buffer = 2 cells. Pond candidates excluded from drainage channels and their immediate surroundings.

---

## Stage 6a — Terrain-Based Water Exclusion

**Module**: `terrain_water_detector.py`

Identifies river corridors and floodplains from terrain alone (no network needed). All thresholds are percentile-based, making this fully general.

Three layers OR-combined:

### Layer 1 — Absolute Low-Elevation Zone
```
low_thresh = min_elev + (max_elev - min_elev) * 15%
low_elev_mask = (elev_grid <= low_thresh)
```
Bottom 15% of elevation range = valley floor / river bed.

### Layer 2 — High-Flow-Accumulation River Channel
```
acc_threshold = percentile(flow_accumulation, 98)
river_raw     = (flow_accumulation >= acc_threshold)
high_acc_mask = binary_dilation(river_raw, radius=8 cells)
```
Top 2% accumulation = major channels. Dilated 8 cells (~120 m at 15 m/cell) to cover full river width.

### Layer 3 — Flat Low Zone (Floodplain)
```
p20_elev      = percentile(elev_grid, 20)
flat_low_mask = (elev_grid <= p20_elev) AND (slope <= 1 degree)
```
Bottom 20% elevation AND nearly flat = floodplain / valley terrace.

### Safety Cap
If combined mask covers >65% of the grid (very flat terrain), falls back to high-accumulation-only mask to avoid excluding all valid candidates.

**Generalisation**: every threshold is a percentile of the current grid. On any different map, the same algorithm detects the dominant low-flat corridor automatically.

---

## Stage 6b — OSM Water Body Exclusion

**Module**: `osm_water_fetcher.py`

When network is available, queries **OpenStreetMap Overpass API** with the bounding box:

```
Overpass QL:
  way/relation [natural=water]
  way/relation [waterway~river|stream|canal|drain]
  way          [landuse=reservoir]
  -- within (south, west, north, east)
```

Each polygon rasterised onto the grid:
- Closed rings: filled scanline via Shapely
- Open ways (river centerlines): Bresenham line drawing

Mask dilated by `buffer_cells` (default 3). Graceful degradation: if network fails, returns empty mask; Stage 6a terrain detection already handles exclusion.

---

## Stage 7 — Pond Candidate Selection

**Module**: `pond_candidate_selector.py`

### 7.1 Weighted Suitability Scoring

Each non-excluded grid cell receives a composite score in [0, 1]:

```
score(r,c) = 0.20 * elevation_score(r,c)
           + 0.30 * slope_score(r,c)
           + 0.30 * accumulation_score(r,c)
           + 0.20 * proximity_score(r,c)
```

#### Elevation Score (weight 0.20)

Prefers moderate elevation — not the river bed (absolute low) and not hilltops (no catchment):

```
p20 = 20th percentile of elev_grid
p40 = 40th percentile of elev_grid

elev <= p20:         score = (elev - min_elev) / (p20 - min_elev)    [rises 0->1]
p20 < elev <= p40:   score = 1.0                                      [optimal band]
elev > p40:          score = 1 - (elev - p40) / (max_elev - p40)     [decays 1->0]
```

Cells in the 20th–40th percentile band score 1.0. Ideal zone: hillside depressions above the floodplain, below the watershed divide.

#### Slope Score (weight 0.30)

Lower slope = easier excavation, better water retention, cheaper to dam:

```
slope_score = 1 - normalise_01(slope_degrees)
```

#### Flow Accumulation Score (weight 0.30)

Higher accumulation = larger upstream contributing area = more water supply. Capped at 80th percentile to prevent river-channel cells (extremely high values) from pulling candidates back into the river bed:

```
acc_capped = clip(flow_accumulation, 0, percentile(flow_accumulation, 80))
acc_score  = normalise_01(acc_capped)
```

#### Proximity-to-Drainage Score (weight 0.20)

A pond near (but NOT on) a drainage channel captures runoff efficiently via natural topographic funnelling:

```
dist_to_drainage = Euclidean distance transform from drainage_mask
max_dist         = percentile(dist_to_drainage, 80)
proximity_score  = 1 - clip(dist_to_drainage / max_dist, 0, 1)
```

Cells adjacent to drainage score ~1; distant cells score ~0.

### 7.2 Exclusion Enforcement

Before finding the maximum:
```
composite[exclusion_mask] = 0.0
```

No candidate can be placed inside a river, lake, floodplain, or active drainage channel.

### 7.3 Multi-Candidate Selection — Iterative Spatial Suppression

Algorithm to return N spatially separated candidates:

```
1. remaining = composite.copy()
2. For rank = 1 to N:
     a. Candidate #rank = cell with max(remaining)
     b. Zero out circular region of radius min_separation_cells
        around Candidate #rank in 'remaining'
3. Return all candidates ordered best -> worst
```

Default: N=3 candidates, min_separation=15 cells (~225 m).  
Each candidate is a genuinely different geographical location.

**Visual colour coding** (Mapbox SimpleStyle):

| Rank | Pond + Catchment | Pour Point | Marker Size |
|------|-----------------|------------|-------------|
| #1 Best | Green `#27AE60` | Dark green `#1A7A43` | Large |
| #2 | Orange `#E67E22` | Dark orange `#B35A10` | Medium |
| #3 | Purple `#8E44AD` | Dark purple `#5E2C7B` | Medium |

The user inspects all three in geojson.io and picks the most practically suitable one.

---

## Stage 8 — Pour Point Snapping

**Module**: `catchment_delineator.py`

The pond candidate (selected by suitability scoring) may not lie on a well-defined flow path. pysheds catchment delineation needs a pour point on a high-accumulation drainage cell.

```
Search window: +/- snap_radius_cells (default 5) around candidate grid cell
Preference:    drainage channel cells first; all cells if none found in window
Snap target:   cell with highest flow_accumulation in search window
Snap distance: Haversine(candidate_coords, snap_coords) in metres
```

Pond candidate and pour point are kept as **distinct concepts**:
- **Pond candidate** — the recommended construction site (optimised for suitability score)
- **Pour point** — nearby drainage cell used as hydrological outlet for catchment delineation

---

## Stage 9 — Catchment Delineation

**Module**: `catchment_delineator.py`  
**Library**: pysheds `grid.catchment()`

All upstream cells draining to the pour point identified by tracing D8 flow graph in reverse:

```
catchment_mask[r,c] = True   if D8 path exists from [r,c] to pour_point
```

Binary raster vectorised to GeoJSON Polygon via `rasterio.features.shapes` and merged with `shapely.ops.unary_union`.

### Area Calculation

Area computed in projected (metric) coordinates — never in degree-squared units:

```
UTM EPSG zone = auto-selected from bounding box centroid (pyproj)
area_sq_m     = shapely projected polygon area
area_sq_km    = area_sq_m / 1,000,000
```

---

## Stage 10 — Result Assembly

**Module**: `contour_analysis_service.py`

All candidates assembled into a single `FeatureCollection` GeoJSON with colour properties applied. A `geojson.io` visualisation URL is generated. The user can open it, compare all three catchment areas and pond locations, and select whichever is most practically feasible — considering area, land availability, accessibility, cost, or any factor not captured by the terrain model.

---

## Why the Algorithm Works on Any Map (Not Hardcoded)

All thresholds are **percentile-based** — computed fresh from each input grid:

| Threshold | How computed |
|-----------|-------------|
| Drainage network boundary | Top 2% of flow accumulation in THIS grid |
| Low-elevation zone | Bottom 15% of elevation range in THIS grid |
| River channel (terrain) | Top 2% accumulation, dilated to cover detected channel width |
| Floodplain zone | Bottom 20% elevation AND slope <= 1 degree |
| Optimal elevation band | 20th–40th percentile of elevation |
| Flow accumulation cap | 80th percentile of flow accumulation |
| Candidate separation | 15 grid cells (scales with resolution) |

No constant encodes any specific river name, coordinate, or elevation value. Upload a different contour map; every percentile recalculates, exclusion zones adapt, scoring adapts, candidates found in the new terrain.

---

## Algorithm Limitations

| Limitation | Impact |
|-----------|--------|
| DEM accuracy bounded by contour interval | Slope and flow direction error up to +/-(interval/2) m |
| Linear interpolation between contours | Assumes uniform slope; real terrain may be convex/concave |
| D8 single-flow-direction | All flow to one neighbour; no dispersion on very flat terrain |
| Catchment at grid resolution | Polygon edges step-shaped at ~15–50 m scale |
| OSM water bodies require network | Falls back to terrain-based detection when offline |
| No soil, land-use, or ownership data | Suitability score purely terrain-derived |

---

## Key Libraries

| Library | Purpose |
|---------|---------|
| `scipy.interpolate.griddata` | Contour-to-DEM interpolation |
| `scipy.ndimage` | Slope gradient, binary dilation for buffers |
| `pysheds` | Pit fill, D8 flow direction, flow accumulation, catchment tracing |
| `rasterio` | GeoTIFF I/O, catchment raster vectorisation |
| `shapely` | Polygon union, area, OSM geometry rasterisation |
| `pyproj` | UTM projection for accurate area calculation |
| `httpx` | OSM Overpass API queries |

---

*Last updated: 2026-08-29*
