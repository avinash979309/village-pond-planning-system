import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'

/**
 * RectangleDraw — when enabled, user can click-drag anywhere on the map
 * to draw a rectangle. No toolbar, no extra clicks.
 *
 * UX:
 *   mousedown → start corner
 *   mousemove → live rectangle preview
 *   mouseup   → finalise → calls onBoundsSelected(bounds)
 *
 * Map panning is disabled while drawing so drag creates rectangle not pan.
 */
export default function RectangleDraw({ onBoundsSelected, enabled }) {
  const map = useMap()
  const rectRef     = useRef(null)   // live preview rectangle
  const startLatLng = useRef(null)   // where mousedown happened
  const drawing     = useRef(false)

  useEffect(() => {
    const container = map.getContainer()

    const onMouseDown = (e) => {
      if (!enabled) return
      // Only respond to left-button clicks not on a control/marker
      if (e.originalEvent.button !== 0) return
      // Stop propagation so map click handler doesn't interfere
      L.DomEvent.stop(e)

      drawing.current = true
      startLatLng.current = e.latlng

      // Disable map drag while drawing
      map.dragging.disable()

      // Create initial zero-size rectangle
      if (rectRef.current) { map.removeLayer(rectRef.current) }
      rectRef.current = L.rectangle([e.latlng, e.latlng], {
        color: '#1565C0',
        weight: 2,
        dashArray: '6 3',
        fillOpacity: 0.08,
        interactive: false,
      }).addTo(map)
    }

    const onMouseMove = (e) => {
      if (!drawing.current || !startLatLng.current || !rectRef.current) return
      rectRef.current.setBounds(L.latLngBounds(startLatLng.current, e.latlng))
    }

    const onMouseUp = (e) => {
      if (!drawing.current) return
      drawing.current = false
      map.dragging.enable()

      if (!startLatLng.current || !rectRef.current) return

      const bounds = L.latLngBounds(startLatLng.current, e.latlng)

      // Ignore tiny accidental clicks (< 0.003° ≈ 300m)
      const latSpan = Math.abs(bounds.getNorth() - bounds.getSouth())
      const lngSpan = Math.abs(bounds.getEast() - bounds.getWest())
      if (latSpan < 0.003 || lngSpan < 0.003) {
        // Too small — remove preview
        map.removeLayer(rectRef.current)
        rectRef.current = null
        startLatLng.current = null
        return
      }

      // Keep the final rectangle (solid)
      rectRef.current.setStyle({ dashArray: null, fillOpacity: 0.1, weight: 2.5 })
      onBoundsSelected(bounds)
    }

    map.on('mousedown', onMouseDown)
    map.on('mousemove', onMouseMove)
    map.on('mouseup',   onMouseUp)

    return () => {
      map.off('mousedown', onMouseDown)
      map.off('mousemove', onMouseMove)
      map.off('mouseup',   onMouseUp)
      map.dragging.enable()
    }
  }, [map, enabled, onBoundsSelected])

  // When disabled: remove the drawn rectangle, re-enable dragging
  useEffect(() => {
    if (!enabled) {
      map.dragging.enable()
      drawing.current = false
      startLatLng.current = null
      if (rectRef.current) {
        try { map.removeLayer(rectRef.current) } catch (_) {}
        rectRef.current = null
      }
      onBoundsSelected(null)
    }
    // Change cursor
    map.getContainer().style.cursor = enabled ? 'crosshair' : ''
  }, [enabled, map, onBoundsSelected])

  return null
}
