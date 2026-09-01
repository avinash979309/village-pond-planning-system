#!/bin/bash
# Helper script to run the analysis and save results to result.geojson

KML_FILE=${1:-"maps/sample_contour_map.kml"}
CANDIDATES=${2:-3}

echo "Running analysis on $KML_FILE for top $CANDIDATES candidates..."
echo "This takes 60-90 seconds..."

curl -s -X POST http://localhost:8000/api/v1/contour/analyze-contour \
  -F "file=@$KML_FILE" \
  -F "top_candidates=$CANDIDATES" \
  | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    if 'data' not in d:
        print('Error from API:', d)
        sys.exit(1)
        
    data = d['data']
    all_features = []
    
    for c in data.get('top_candidates',[]):
        rank = c['rank']
        # pond
        pond = c['pond_candidate']
        pond['properties']['feature_type'] = 'pond_site'
        all_features.append(pond)
        # pour point
        pour = c['pour_point']
        pour['properties']['feature_type'] = 'pour_point'
        pour['properties']['rank'] = rank
        all_features.append(pour)
        # catchment
        catch = c['catchment']
        catch['properties']['feature_type'] = 'catchment'
        catch['properties']['rank'] = rank
        all_features.append(catch)

    geojson = {'type':'FeatureCollection','features':all_features}
    with open('result.geojson','w') as f:
        json.dump(geojson, f, indent=2)
        
    print(f'\nSuccess! Saved result.geojson with {len(data.get(\"top_candidates\",[]))} candidates.')
    
    osm = data.get('osm_water_exclusion',{})
    if osm.get('water_bodies_found'):
        print(f'OSM Exclusion Active: {osm.get(\"water_body_count\")} bodies avoided ({\", \".join(osm.get(\"water_body_names\",[]))})')
        
except Exception as e:
    print('Failed to parse response:', e)
"
