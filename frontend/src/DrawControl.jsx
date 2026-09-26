import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'

/**
 * RectangleDraw — click-drag rectangle on the map.
 *
 * When `enabled` is true, left-click+drag draws a rectangle.
 * Map shows a crosshair cursor. Double-click / pan / zoom work normally
 * when enabled=false (user can navigate freely).
 *
 * Drawing starts ONLY on mousedown, NOT on double-click, because we check
 * that the previous mousedown happened >200ms ago (double-click fires two
 * mousedowns within ~300ms — we ignore the second one).
 */
export default function RectangleDraw({ onBoundsSelected, enabled }) {
  const map         = useMap()
  const rectRef     = useRef(null)
  const startLL     = useRef(null)
  const drawing     = useRef(false)
  const lastDown    = useRef(0)   // timestamp of last mousedown

  useEffect(() => {
    const onMouseDown = (e) => {
      if (!enabled) return
      if (e.originalEvent.button !== 0) return

      const now = Date.now()
      // Ignore second click of a double-click (< 300 ms after last mousedown)
      if (now - lastDown.current < 300) {
        lastDown.current = now
        return
      }
      lastDown.current = now

      drawing.current = true
      startLL.current = e.latlng
      map.dragging.disable()

      if (rectRef.current) { try { map.removeLayer(rectRef.current) } catch (_) {} }
      rectRef.current = L.rectangle([e.latlng, e.latlng], {
        color: '#1565C0',
        weight: 2,
        dashArray: '6 3',
        fillOpacity: 0.08,
        interactive: false,
      }).addTo(map)
    }

    const onMouseMove = (e) => {
      if (!drawing.current || !startLL.current || !rectRef.current) return
      rectRef.current.setBounds(L.latLngBounds(startLL.current, e.latlng))
    }

    const onMouseUp = (e) => {
      if (!drawing.current) return
      drawing.current = false
      map.dragging.enable()

      if (!startLL.current || !rectRef.current) return
      const bounds = L.latLngBounds(startLL.current, e.latlng)

      const latSpan = Math.abs(bounds.getNorth() - bounds.getSouth())
      const lngSpan = Math.abs(bounds.getEast()  - bounds.getWest())
      if (latSpan < 0.003 || lngSpan < 0.003) {
        try { map.removeLayer(rectRef.current) } catch (_) {}
        rectRef.current = null
        startLL.current = null
        return
      }

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

  // Cursor + cleanup when disabled
  useEffect(() => {
    map.getContainer().style.cursor = enabled ? 'crosshair' : ''
    if (!enabled) {
      map.dragging.enable()
      drawing.current = false
      startLL.current = null
      if (rectRef.current) {
        try { map.removeLayer(rectRef.current) } catch (_) {}
        rectRef.current = null
      }
    }
  }, [enabled, map])

  return null
}
