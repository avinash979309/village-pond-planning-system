#!/bin/bash
# Analyze a contour map and save result.geojson (up to 3 pond candidates)
# Usage: ./generate_results.sh [path/to/contour.kml]

KML_FILE=${1:-"maps/sample_contour_map.kml"}

if [ ! -f "$KML_FILE" ]; then
    echo "Error: File '$KML_FILE' not found."
    echo "Usage: ./generate_results.sh [path/to/contour.kml]"
    exit 1
fi

echo "Analyzing: $KML_FILE"
echo "Please wait 60-90 seconds..."

curl -s -X POST http://localhost:8000/analyzeContour \
  -F "file=@$KML_FILE" \
  | python3 -c "
import sys, json

try:
    d = json.load(sys.stdin)
except Exception as e:
    print('Failed to parse response:', e)
    sys.exit(1)

if d.get('status') != 'success':
    print('API error:', d)
    sys.exit(1)

candidates = d.get('all_candidates', [])
best = candidates[0] if candidates else {}

# Build GeoJSON with pond points + catchment polygons for all candidates
# We need the full geometry — fetch from the full API response
all_features = []

# pond_location / pour_point / catchment from top-level (rank 1)
from_api = {
    'pond': d.get('pond_location', {}),
    'pour': d.get('pour_point', {}),
    'catchment': d.get('catchment', {}),
}

# Since /analyzeContour returns structured data (not raw GeoJSON per candidate),
# build GeoJSON features from what we have
for c in candidates:
    rank = c.get('rank', '?')
    colors = {1: '#2ecc71', 2: '#e67e22', 3: '#9b59b6'}
    color = colors.get(rank, '#cccccc')

    # Pond point
    all_features.append({
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [c['longitude'], c['latitude']]},
        'properties': {
            'rank': rank,
            'feature_type': 'pond_site',
            'suitability_score': c.get('suitability_score'),
            'catchment_area_km2': c.get('catchment_area_km2'),
            'marker-color': color,
            'marker-size': 'large',
            'marker-symbol': 'water',
            'title': f'Rank {rank} Pond Site',
        }
    })

# Add rank 1 catchment boundary if available
boundary = from_api['catchment'].get('boundary_geojson')
if boundary:
    all_features.append({
        'type': 'Feature',
        'geometry': boundary,
        'properties': {
            'rank': 1,
            'feature_type': 'catchment',
            'area_km2': from_api['catchment'].get('area_km2'),
            'area_m2': from_api['catchment'].get('area_m2'),
            'avg_elevation_m': from_api['catchment'].get('avg_elevation_m'),
            'stroke': '#2ecc71',
            'stroke-width': 2,
            'fill': '#2ecc71',
            'fill-opacity': 0.15,
            'title': 'Rank 1 Catchment Area',
        }
    })

# Add rank 1 pour point
pour = from_api['pour']
if pour.get('longitude'):
    all_features.append({
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [pour['longitude'], pour['latitude']]},
        'properties': {
            'rank': 1,
            'feature_type': 'pour_point',
            'marker-color': '#1a8a4e',
            'marker-size': 'medium',
            'marker-symbol': 'circle',
            'title': 'Pour Point (Catchment Outlet)',
        }
    })

geojson = {'type': 'FeatureCollection', 'features': all_features}
with open('result.geojson', 'w') as f:
    json.dump(geojson, f, indent=2)

print(f'')
print(f'Success! Saved result.geojson')
print(f'Candidates found: {len(candidates)}')
for c in candidates:
    print(f'  Rank {c[\"rank\"]}: [{c[\"longitude\"]:.4f}, {c[\"latitude\"]:.4f}]  score={c.get(\"suitability_score\")}  catchment={c.get(\"catchment_area_km2\")} km2')

osm = d.get('osm_water_exclusion', {})
if osm.get('water_bodies_found'):
    print(f'OSM: Excluded {osm[\"water_body_count\"]} water bodies ({', '.join(osm[\"water_body_names\"][:3])})')
else:
    print(f'OSM: Terrain-based exclusion used (OSM mirror unavailable)')

print(f'')
print(f'Visualize: drag result.geojson into https://geojson.io')
"
