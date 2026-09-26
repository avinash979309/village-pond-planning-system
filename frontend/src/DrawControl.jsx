import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet-draw'

/**
 * DrawControl — rectangle-only draw tool for selecting analysis area.
 * No polygon (auto-close bug). Rectangle = clean 2-click draw.
 * Calls onBoundsSelected(bounds) on finish, onBoundsSelected(null) on delete.
 */
export default function DrawControl({ onBoundsSelected, enabled }) {
  const map = useMap()
  const drawnItemsRef = useRef(null)
  const controlRef    = useRef(null)
  const handlerRef    = useRef(null)

  useEffect(() => {
    const drawnItems = new L.FeatureGroup()
    map.addLayer(drawnItems)
    drawnItemsRef.current = drawnItems

    const drawControl = new L.Control.Draw({
      position: 'topleft',
      draw: {
        rectangle: {
          shapeOptions: {
            color: '#1565C0',
            weight: 2.5,
            fillOpacity: 0.08,
            dashArray: null,
          },
          showArea: true,
          metric: true,
        },
        polygon:      false,
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
    const onDeleted = () => onBoundsSelected(null)
    const onEdited  = (e) => {
      e.layers.eachLayer(layer => onBoundsSelected(layer.getBounds()))
    }

    map.on(L.Draw.Event.CREATED, onCreated)
    map.on(L.Draw.Event.DELETED, onDeleted)
    map.on(L.Draw.Event.EDITED,  onEdited)

    return () => {
      map.off(L.Draw.Event.CREATED, onCreated)
      map.off(L.Draw.Event.DELETED, onDeleted)
      map.off(L.Draw.Event.EDITED,  onEdited)
      try { map.removeLayer(drawnItems)    } catch (_) {}
      try { map.removeControl(drawControl) } catch (_) {}
    }
  }, [map]) // eslint-disable-line react-hooks/exhaustive-deps

  // Show/hide toolbar when enabled changes
  useEffect(() => {
    if (!controlRef.current) return
    if (enabled) {
      try { map.addControl(controlRef.current) } catch (_) {}
    } else {
      try { map.removeControl(controlRef.current) } catch (_) {}
      if (drawnItemsRef.current) drawnItemsRef.current.clearLayers()
    }
  }, [enabled, map])

  return null
}
