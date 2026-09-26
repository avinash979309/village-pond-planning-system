import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet-draw'

/**
 * DrawControl — adds leaflet-draw rectangle + polygon tools to the map.
 * Calls onBoundsSelected(bounds) when user finishes drawing.
 * Clears previous shape on new draw.
 * Only shows the toolbar when enabled=true.
 */
export default function DrawControl({ onBoundsSelected, enabled }) {
  const map = useMap()
  const drawnItemsRef = useRef(null)
  const controlRef    = useRef(null)

  useEffect(() => {
    const drawnItems = new L.FeatureGroup()
    map.addLayer(drawnItems)
    drawnItemsRef.current = drawnItems

    const drawControl = new L.Control.Draw({
      position: 'topleft',
      draw: {
        rectangle: {
          shapeOptions: { color: '#1565C0', weight: 2, fillOpacity: 0.08 },
          showArea: true,
        },
        polygon: {
          shapeOptions: { color: '#1565C0', weight: 2, fillOpacity: 0.08 },
          showArea: true,
          allowIntersection: false,
        },
        polyline:     false,
        circle:       false,
        circlemarker: false,
        marker:       false,
      },
      edit: { featureGroup: drawnItems, remove: true },
    })
    controlRef.current = drawControl

    if (enabled) {
      try { map.addControl(drawControl) } catch (_) {}
    }

    const onCreated = (e) => {
      drawnItems.clearLayers()
      drawnItems.addLayer(e.layer)
      onBoundsSelected(e.layer.getBounds())
    }

    const onDeleted = () => {
      onBoundsSelected(null)
    }

    map.on(L.Draw.Event.CREATED, onCreated)
    map.on(L.Draw.Event.DELETED, onDeleted)

    return () => {
      map.off(L.Draw.Event.CREATED, onCreated)
      map.off(L.Draw.Event.DELETED, onDeleted)
      try { map.removeLayer(drawnItems) }  catch (_) {}
      try { map.removeControl(drawControl) } catch (_) {}
    }
  }, [map]) // eslint-disable-line react-hooks/exhaustive-deps

  // Add/remove control when enabled changes
  useEffect(() => {
    if (!controlRef.current) return
    if (enabled) {
      try { map.addControl(controlRef.current) }    catch (_) {}
    } else {
      try { map.removeControl(controlRef.current) } catch (_) {}
      // Clear any drawn shapes when disabled
      if (drawnItemsRef.current) drawnItemsRef.current.clearLayers()
    }
  }, [enabled, map])

  return null
}
