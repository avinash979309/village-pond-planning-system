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
echo "Please wait 3-5 minutes on first run..."

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

# The API returns a pre-built colored FeatureCollection that already contains:
#   - Catchment polygon  for every ranked candidate (green / orange / purple)
#   - Pond site point    for every ranked candidate
#   - Pour point         for every ranked candidate
# Just save it directly.
geojson = d.get('geojson')
if not geojson:
    # Fallback: build minimal GeoJSON from flat fields if geojson key missing
    features = []
    for c in d.get('all_candidates', []):
        colors = {1: '#27AE60', 2: '#E67E22', 3: '#8E44AD'}
        clr = colors.get(c['rank'], '#999999')
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [c['longitude'], c['latitude']]},
            'properties': {
                'title': f'Pond Candidate #{c[\"rank\"]}',
                'rank': c['rank'],
                'suitability_score': c.get('suitability_score'),
                'marker-color': clr, 'marker-size': 'large',
            }
        })
        # pour point
        pp = c.get('pour_point', {})
        if pp.get('longitude'):
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [pp['longitude'], pp['latitude']]},
                'properties': {'title': f'Pour Point #{c[\"rank\"]}', 'rank': c['rank'],
                               'marker-color': clr, 'marker-size': 'small'}
            })
        # catchment polygon
        bdry = c.get('catchment', {}).get('boundary_geojson')
        if bdry:
            features.append({
                'type': 'Feature', 'geometry': bdry,
                'properties': {
                    'title': f'Catchment #{c[\"rank\"]}',
                    'area_km2': c['catchment'].get('area_km2'),
                    'stroke': clr, 'stroke-width': 2,
                    'fill': clr, 'fill-opacity': 0.15,
                }
            })
    geojson = {'type': 'FeatureCollection', 'features': features}

with open('result.geojson', 'w') as f:
    json.dump(geojson, f, indent=2)

candidates = d.get('all_candidates', [])
print()
print(f'Success! result.geojson saved ({len(candidates)} candidates)')
for c in candidates:
    cat = c.get('catchment', {})
    print(f'  Rank {c[\"rank\"]}: [{c[\"longitude\"]:.4f}, {c[\"latitude\"]:.4f}]'
          f'  score={c.get(\"suitability_score\")}  catchment={cat.get(\"area_km2\")} km2')

osm = d.get('osm_water_exclusion', {})
if osm.get('water_bodies_found'):
    names = ', '.join(osm['water_body_names'][:3])
    print(f'OSM: Excluded {osm[\"water_body_count\"]} water bodies ({names})')
else:
    print('OSM: Terrain-based exclusion used (OSM mirror unavailable)')

print()
print('Visualize: drag result.geojson into https://geojson.io')
print('  Green  = Rank 1 (best)  |  Orange = Rank 2  |  Purple = Rank 3')
"
