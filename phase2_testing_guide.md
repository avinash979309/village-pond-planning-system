# Phase 2 — Local Testing & Result Analysis Guide

## 1. Start the Server

```bash
cd /home/avinash/CSD_LAB/Assignment_1/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server ready when you see:
```
INFO:     Application startup complete.
```

---

## 2. Interactive API Docs (easiest way to test)

Open browser → **http://localhost:8000/docs**

This is Swagger UI. Click `POST /api/v1/contour/analyze-contour` → **Try it out** → upload your KML → **Execute**.

Also available: **http://localhost:8000/redoc** (read-only docs, nicer format).

---

## 3. Test with the Sample KML (curl)

```bash
curl -X POST http://localhost:8000/api/v1/contour/analyze-contour \
  -F "file=@/home/avinash/CSD_LAB/Assignment_1/maps/sample_contour_map.kml" \
  -F "grid_resolution=200" \
  -F "drainage_threshold_pct=2.0" \
  | python3 -m json.tool
```

`python3 -m json.tool` pretty-prints the JSON response.

---

## 4. Health Check

```bash
curl http://localhost:8000/health
# → {"status":"healthy","version":"0.1.0"}
```

---

## 5. Parameters You Can Tune

| Parameter | Default | Effect |
|-----------|---------|--------|
| `grid_resolution` | 200 | Cells per axis (200×200 grid). Higher = finer but slower. Try 100, 300, 500. |
| `drainage_threshold_pct` | 2.0 | Top N% flow accumulation = drainage channel. Lower = more channels detected. |
| `drainage_buffer_cells` | 2 | Exclusion buffer around drainage. Bigger = pond farther from stream. |
| `snap_radius_cells` | 5 | Search radius to snap pour point to nearest drainage cell. |

---

## 6. What the Response Contains

```
response.data
├── input_summary       ← what was parsed from your KML
├── terrain             ← grid built from contours
├── drainage            ← derived drainage network stats
├── pond_candidate      ← GeoJSON Point (best location for pond)
├── pour_point          ← GeoJSON Point (snapped to drainage)
├── catchment           ← GeoJSON Polygon (area draining into pour point)
└── methodology         ← algorithm details
```

---

## 7. Key Fields to Read

### `pond_candidate.geometry.coordinates`
`[longitude, latitude]` — put this in Google Maps to see where the algorithm recommends building the pond.

### `pond_candidate.properties.suitability_score`
0–1. Higher = better. Score breakdown:
- `elevation_score` — lower elevation preferred
-## 3. Visualising the Results (Phase 2 Update)

The Phase 2 API analyzes the map, applies exact OSM water boundaries (so ponds are never in rivers), and returns multiple candidates. 

We added a helper script to make testing easy. To generate the `result.geojson` file with multiple candidates:

```bash
# Run this from the Assignment_1 root folder
./generate_results.sh maps/sample_contour_map.kml 3
```

*(First argument is the KML file, second argument is the number of candidates you want).*

Wait 60-90 seconds. It will save `result.geojson` in your root folder.

### Visualisation in geojson.io
1. Open [geojson.io](https://geojson.io) in your browser.
2. Drag and drop the generated `result.geojson` file onto the map.to visualize the catchment boundary on a map.

### `terrain.elevation_stats`
Min/max/mean elevation of the mapped area.

### `drainage.drainage_cells_count`
How many grid cells were classified as drainage channels.

---

## 8. Visualize Results

### Option A — geojson.io (easiest)
1. Save pond + catchment as GeoJSON:

```bash
curl -s -X POST http://localhost:8000/api/v1/contour/analyze-contour \
  -F "file=@/home/avinash/CSD_LAB/Assignment_1/maps/sample_contour_map.kml" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
fc = {
    'type': 'FeatureCollection',
    'features': [
        d['catchment'],
        d['pond_candidate'],
        d['pour_point']
    ]
}
print(json.dumps(fc, indent=2))
" > /tmp/result.geojson
```

2. Go to **https://geojson.io** → drag and drop `/tmp/result.geojson`
3. See catchment polygon + pond point + pour point on satellite map.

### Option B — QGIS
Open QGIS → Layer → Add Layer → Add Vector Layer → load `/tmp/result.geojson`

### Option C — Python + matplotlib (quick plot)
```python
import json, matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import shape

with open('/tmp/result.geojson') as f:
    fc = json.load(f)

fig, ax = plt.subplots(figsize=(8,8))
for feature in fc['features']:
    geom = shape(feature['geometry'])
    if geom.geom_type == 'Polygon':
        x, y = geom.exterior.xy
        ax.fill(x, y, alpha=0.3, color='blue', label='Catchment')
        ax.plot(x, y, color='blue')
    elif geom.geom_type == 'Point':
        ax.plot(geom.x, geom.y, 'ro', markersize=10)

ax.set_title('Catchment + Pond Candidate')
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
plt.tight_layout()
plt.savefig('/tmp/catchment_map.png', dpi=150)
plt.show()
```

---

## 9. Test Error Handling

Upload wrong file type:
```bash
curl -X POST http://localhost:8000/api/v1/contour/analyze-contour \
  -F "file=@/etc/hostname" \
  | python3 -m json.tool
# → 400 error with meaningful message
```

---

## 10. Run All Tests

```bash
cd /home/avinash/CSD_LAB/Assignment_1/backend
source venv/bin/activate
pytest tests/ -v
```

Run one file:
```bash
pytest tests/test_contour_api.py -v   # integration tests (API end-to-end)
pytest tests/test_hydrology.py -v     # hydrology engine
pytest tests/test_kml_parser.py -v    # KML parsing
pytest tests/test_terrain_builder.py -v  # terrain grid building
```

---

## 11. What "Good" Results Look Like

| Field | Good sign |
|-------|-----------|
| `suitability_score` | > 0.6 |
| `catchment.area_sq_km` | 0.5–5 km² (typical small village pond catchment) |
| `pond_candidate` `on_drainage_channel` | `false` (pond not on active stream) |
| `pond_candidate` `exclusion_zone_respected` | `true` |
| `slope_degrees` | < 5° (flat enough to build embankment) |
| `flow_accumulation` | high relative to surrounding cells |
