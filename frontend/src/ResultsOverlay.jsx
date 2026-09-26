import { useEffect } from 'react'
import { useMap, GeoJSON } from 'react-leaflet'
import L from 'leaflet'

const RANK_COLORS = ['#27AE60', '#E67E22', '#8E44AD']
const RANK_LABELS = ['Rank #1 (Best)', 'Rank #2', 'Rank #3']

/**
 * ResultsOverlay — renders pond candidates + catchment polygons on the map.
 * Flies the map to fit all results when data changes.
 */
export default function ResultsOverlay({ data }) {
  const map = useMap()

  useEffect(() => {
    if (!data) return
    const bounds = []
    data.all_candidates?.forEach(c => {
      bounds.push([c.latitude, c.longitude])
      const poly = c.catchment?.boundary_geojson
      if (poly?.type === 'Polygon') {
        poly.coordinates[0].forEach(([lng, lat]) => bounds.push([lat, lng]))
      }
    })
    if (bounds.length) {
      try { map.flyToBounds(L.latLngBounds(bounds), { padding: [40, 40], maxZoom: 14, duration: 1 }) }
      catch (_) {}
    }
  }, [data, map])

  if (!data) return null

  return data.all_candidates?.map((c, i) => {
    const color = RANK_COLORS[Math.min(i, 2)]
    const label = RANK_LABELS[Math.min(i, 2)]
    const catchGeom = c.catchment?.boundary_geojson

    return (
      <div key={i}>
        {/* Catchment polygon */}
        {catchGeom && (
          <GeoJSON
            key={`catch-${i}-${JSON.stringify(c.longitude)}`}
            data={{ type: 'Feature', geometry: catchGeom }}
            style={{ color, weight: 2, fillColor: color, fillOpacity: 0.15, opacity: 0.9 }}
            onEachFeature={(_, layer) => {
              layer.bindPopup(
                `<b>${label} — Catchment</b><br/>` +
                `Area: ${c.catchment.area_km2?.toFixed(4)} km²<br/>` +
                `Avg elevation: ${c.catchment.avg_elevation_m?.toFixed(1)} m`
              )
            }}
          />
        )}

        {/* Pond candidate marker */}
        <GeoJSON
          key={`pond-${i}`}
          data={{ type: 'Feature', geometry: { type: 'Point', coordinates: [c.longitude, c.latitude] } }}
          pointToLayer={(_, latlng) =>
            L.circleMarker(latlng, { radius: i === 0 ? 10 : 7, color: '#fff', weight: 2, fillColor: color, fillOpacity: 1 })
          }
          onEachFeature={(_, layer) => {
            layer.bindPopup(
              `<b>${label} — Pond Site</b><br/>` +
              `Lon: ${c.longitude?.toFixed(5)}, Lat: ${c.latitude?.toFixed(5)}<br/>` +
              `Elevation: ${c.elevation_m?.toFixed(1)} m<br/>` +
              `Score: ${c.suitability_score?.toFixed(4)}`
            )
            if (i === 0) layer.openPopup()
          }}
        />

        {/* Pour point */}
        {c.pour_point && (
          <GeoJSON
            key={`pp-${i}`}
            data={{ type: 'Feature', geometry: { type: 'Point', coordinates: [c.pour_point.longitude, c.pour_point.latitude] } }}
            pointToLayer={(_, latlng) =>
              L.circleMarker(latlng, { radius: 5, color: '#fff', weight: 1.5, fillColor: '#2980B9', fillOpacity: 0.9 })
            }
            onEachFeature={(_, layer) => {
              layer.bindPopup(`<b>Pour Point (${label})</b><br/>Catchment outlet / hydrological input`)
            }}
          />
        )}
      </div>
    )
  })
}
