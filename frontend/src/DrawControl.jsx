import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet-draw'

/**
 * DrawControl — adds leaflet-draw rectangle tool to the map.
 * Calls onBoundsSelected(bounds) when user finishes drawing.
 * Clears previous rectangle on new draw.
 */
export default function DrawControl({ onBoundsSelected, enabled }) {
  const map = useMap()
  const drawnItemsRef = useRef(null)
  const controlRef = useRef(null)

  useEffect(() => {
    const drawnItems = new L.FeatureGroup()
    map.addLayer(drawnItems)
    drawnItemsRef.current = drawnItems

    const drawControl = new L.Control.Draw({
      draw: {
        rectangle: { shapeOptions: { color: '#2b6cb0', weight: 2 } },
        polygon: false,
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false,
      },
      edit: { featureGroup: drawnItems, remove: false },
    })
    controlRef.current = drawControl

    if (enabled) map.addControl(drawControl)

    const onCreated = (e) => {
      drawnItems.clearLayers()
      drawnItems.addLayer(e.layer)
      onBoundsSelected(e.layer.getBounds())
    }
    map.on(L.Draw.Event.CREATED, onCreated)

    return () => {
      map.off(L.Draw.Event.CREATED, onCreated)
      map.removeLayer(drawnItems)
      if (map.hasLayer && controlRef.current) {
        try { map.removeControl(controlRef.current) } catch (_) {}
      }
    }
  }, [map]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!controlRef.current) return
    if (enabled) { try { map.addControl(controlRef.current) } catch (_) {} }
    else         { try { map.removeControl(controlRef.current) } catch (_) {} }
  }, [enabled, map])

  return null
}
