import { useState, useRef, useCallback } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'
import DrawControl from './DrawControl'
import ResultsOverlay from './ResultsOverlay'

// Fix leaflet default icon paths broken by Vite
import L from 'leaflet'
import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png'
import shadowUrl from 'leaflet/dist/images/marker-shadow.png'
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl })

const API_BASE = import.meta.env.VITE_API_BASE || ''

// ── Input modes ────────────────────────────────────────────────────────────────
const MODE_KML  = 'kml'
const MODE_DRAW = 'draw'

function fmt(v, decimals = 2) {
  if (v == null || v === '') return '—'
  return typeof v === 'number' ? v.toFixed(decimals) : v
}

function StatCard({ label, value, cls = '' }) {
  return (
    <div className={`stat-card ${cls}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  )
}

function CandidatePanel({ c, rank }) {
  const colors = ['green', 'orange', 'teal']
  const labels = ['#1 Best Site', '#2 Alternate', '#3 Alternate']
  const pillCls = ['pill-1', 'pill-2', 'pill-3']
  return (
    <div style={{ marginBottom: 12 }}>
      <span className={`candidate-pill ${pillCls[rank]}`}>● {labels[rank]}</span>
      <div className="stat-grid">
        <StatCard label="Longitude" value={fmt(c.longitude, 5)} cls={colors[rank]} />
        <StatCard label="Latitude"  value={fmt(c.latitude, 5)}  cls={colors[rank]} />
        <StatCard label="Elevation" value={`${fmt(c.elevation_m, 1)} m`} />
        <StatCard label="Score"     value={fmt(c.suitability_score, 4)} />
        <StatCard label="Catchment area" value={`${fmt(c.catchment?.area_km2, 4)} km²`} cls="full" />
        <StatCard label="Avg elevation"  value={`${fmt(c.catchment?.avg_elevation_m, 1)} m`} />
        <StatCard label="Area (m²)"      value={`${fmt(c.catchment?.area_m2, 0)} m²`} />
      </div>
    </div>
  )
}

export default function App() {
  const [mode, setMode]               = useState(MODE_KML)
  const [file, setFile]               = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)
  const [result, setResult]           = useState(null)
  const [activeTab, setActiveTab]     = useState(0)
  const [selectedBounds, setSelectedBounds] = useState(null)
  const [drawEnabled, setDrawEnabled] = useState(false)
  const fileInputRef = useRef()

  // ── shared analysis runner ──────────────────────────────────────────────────
  const runAnalysis = useCallback(async (url, body, isJson = false) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const opts = isJson
        ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
        : { method: 'POST', body }
      const res = await fetch(`${API_BASE}${url}`, opts)
      if (!res.ok) {
        const txt = await res.text()
        throw new Error(`Server ${res.status}: ${txt.slice(0, 300)}`)
      }
      const data = await res.json()
      setResult(data)
      setActiveTab(0)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // ── KML file submit ─────────────────────────────────────────────────────────
  const handleFileSubmit = () => {
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    runAnalysis('/analyzeContour', fd)
  }

  // ── Drawn area submit ───────────────────────────────────────────────────────
  const handleAreaSubmit = () => {
    if (!selectedBounds) {
      setError('Draw a rectangle on the map first, then click Analyze Area.')
      return
    }
    const sw = selectedBounds.getSouthWest()
    const ne = selectedBounds.getNorthEast()
    runAnalysis('/analyzeArea', {
      west:  sw.lng,
      south: sw.lat,
      east:  ne.lng,
      north: ne.lat,
    }, true)
  }

  // ── Mode switch ─────────────────────────────────────────────────────────────
  const switchMode = (m) => {
    setMode(m)
    setError(null)
    setResult(null)
    setFile(null)
    setSelectedBounds(null)
    setDrawEnabled(false)   // always off — user clicks toggle button to start
  }

  const vol  = result?.water_volume
  const inputBoundary = result?.input_boundary  // bbox polygon GeoJSON

  return (
    <div id="root">
      {/* ── Top bar ── */}
      <div className="topbar">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
          <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10A15.3 15.3 0 0 1 8 12 15.3 15.3 0 0 1 12 2z"/>
        </svg>
        <div>
          <h1>AI-based Village Pond Planning System</h1>
          <p>Identify optimal pond locations — upload a contour map or select an area on the map</p>
        </div>
      </div>

      <div className="layout">
        {/* ── Sidebar ── */}
        <aside className="sidebar">

          {/* ── Mode switcher tabs ── */}
          <div className="sidebar-section" style={{ paddingBottom: 0 }}>
            <div className="mode-tabs">
              <button
                className={`mode-tab ${mode === MODE_KML ? 'active' : ''}`}
                onClick={() => switchMode(MODE_KML)}
              >
                📄 Upload KML
              </button>
              <button
                className={`mode-tab ${mode === MODE_DRAW ? 'active' : ''}`}
                onClick={() => switchMode(MODE_DRAW)}
              >
                🗺️ Draw Area
              </button>
            </div>
          </div>

          {/* ── KML Upload mode ── */}
          {mode === MODE_KML && (
            <div className="sidebar-section">
              <h2>Upload Contour Map</h2>
              <div className="instructions" style={{ marginBottom: 10 }}>
                <ol>
                  <li>Upload a KML/KMZ contour map file</li>
                  <li>Click <b>Analyze</b> — takes ~60–90 s</li>
                  <li>View results on the map and panel</li>
                  <li>Click map markers for details</li>
                </ol>
              </div>

              <label className={`upload-label ${file ? 'has-file' : ''}`}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                {file ? `✓ ${file.name}` : 'Click to select .kml or .kmz'}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".kml,.kmz"
                  onChange={e => { setFile(e.target.files[0] || null); setError(null) }}
                />
              </label>

              <button
                className="btn btn-primary"
                style={{ marginTop: 10 }}
                disabled={!file || loading}
                onClick={handleFileSubmit}
              >
                {loading ? 'Analyzing…' : 'Analyze'}
              </button>

              {file && (
                <button className="btn btn-clear" onClick={() => { setFile(null); setResult(null); setError(null) }}>
                  Clear
                </button>
              )}
            </div>
          )}

          {/* ── Draw Area mode ── */}
          {mode === MODE_DRAW && (
            <div className="sidebar-section">
              <h2>Select Area on Map</h2>

              {/* Draw toggle button */}
              <button
                className={`btn ${drawEnabled ? 'btn-drawing-active' : 'btn-primary'}`}
                style={{ marginBottom: 10, width: '100%' }}
                onClick={() => {
                  if (drawEnabled) {
                    setDrawEnabled(false)
                  } else {
                    setSelectedBounds(null)
                    setResult(null)
                    setError(null)
                    setDrawEnabled(true)
                  }
                }}
                disabled={loading}
              >
                {drawEnabled ? '✅ Drawing Active — click to stop' : '✏️ Draw Rectangle on Map'}
              </button>

              {drawEnabled && (
                <div className="draw-hint" style={{ marginBottom: 8 }}>
                  🖱️ <b>Click and drag</b> on the map to draw. Double-click still zooms normally.
                </div>
              )}

              {!drawEnabled && !selectedBounds && (
                <div className="draw-hint" style={{ marginBottom: 8 }}>
                  Click <b>Draw Rectangle</b> above, then drag on the map to select your area.
                </div>
              )}

              {selectedBounds && (
                <div className="draw-bounds-info">
                  ✅ Area selected<br/>
                  <small>
                    SW: {selectedBounds.getSouthWest().lat.toFixed(4)}°N, {selectedBounds.getSouthWest().lng.toFixed(4)}°E<br/>
                    NE: {selectedBounds.getNorthEast().lat.toFixed(4)}°N, {selectedBounds.getNorthEast().lng.toFixed(4)}°E
                  </small>
                </div>
              )}

              <button
                className="btn btn-primary"
                style={{ marginTop: 8 }}
                disabled={!selectedBounds || loading}
                onClick={handleAreaSubmit}
              >
                {loading ? 'Analyzing…' : 'Analyze Area'}
              </button>

              {selectedBounds && (
                <button
                  className="btn btn-clear"
                  onClick={() => {
                    setSelectedBounds(null)
                    setResult(null)
                    setError(null)
                    setDrawEnabled(false)
                  }}
                >
                  Clear Selection
                </button>
              )}
            </div>
          )}

          {/* ── Loading spinner ── */}
          {loading && (
            <div className="sidebar-section">
              <div className="spinner-wrap">
                <div className="spinner" />
                <span>
                  {mode === MODE_DRAW
                    ? 'Fetching elevation data + running terrain analysis…'
                    : 'Running terrain + hydrology analysis…'}
                </span>
              </div>
            </div>
          )}

          {/* ── Error ── */}
          {error && <div className="sidebar-section"><div className="error-box">{error}</div></div>}

          {/* ── Results ── */}
          {result && (
            <div className="sidebar-section" style={{ flex: 1 }}>
              <h2>Results</h2>

              {/* Input area info badge */}
              {result.input_source && (
                <div className="input-source-badge">
                  {result.input_source === 'kml'
                    ? '📄 Source: KML contour map'
                    : '🗺️ Source: Selected map area (SRTM DEM)'}
                </div>
              )}

              {/* Water volume summary */}
              {vol && (
                <div className="result-block">
                  <h3>Water Harvest Estimate</h3>
                  <div className="stat-grid">
                    <StatCard label="Annual runoff" value={`${fmt(vol.annual_runoff_m3, 0)} m³`} cls="blue" />
                    <StatCard label="Runoff (ML)"   value={`${fmt(vol.annual_runoff_ML, 2)} ML`} cls="blue" />
                    <StatCard label="Pond capacity" value={`${fmt(vol.pond_storage_m3, 0)} m³`} cls="teal" />
                    <StatCard label="Effective storage" value={`${fmt(vol.effective_storage_m3, 0)} m³`} cls="teal" />
                    <StatCard
                      label="Assumptions"
                      value={`${vol.assumptions?.annual_rainfall_mm} mm/yr · C=${vol.assumptions?.runoff_coefficient} · depth=${vol.assumptions?.pond_depth_m} m`}
                      cls="full"
                    />
                  </div>
                </div>
              )}

              {/* Candidate tabs */}
              {result.all_candidates?.length > 0 && (
                <div className="result-block" style={{ marginTop: 14 }}>
                  <h3>Pond Candidates</h3>
                  <div className="tabs">
                    {result.all_candidates.map((_, i) => (
                      <button key={i} className={`tab ${activeTab === i ? 'active' : ''}`} onClick={() => setActiveTab(i)}>
                        #{i + 1}
                      </button>
                    ))}
                  </div>
                  <CandidatePanel c={result.all_candidates[activeTab]} rank={activeTab} />
                </div>
              )}

              {/* OSM exclusion note */}
              {result.osm_water_exclusion?.water_bodies_found && (
                <div className="result-block">
                  <h3>Water Body Exclusion</h3>
                  <div className="instructions">
                    {result.osm_water_exclusion.water_body_count} OSM water bodies excluded:{' '}
                    {result.osm_water_exclusion.water_body_names?.slice(0, 5).join(', ')}
                  </div>
                </div>
              )}
            </div>
          )}
        </aside>

        {/* ── Map ── */}
        <div className="map-wrap">
          {loading && <div className="map-hint">⏳ Analyzing terrain — please wait…</div>}
          {!loading && !result && mode === MODE_KML && (
            <div className="map-hint">Upload a KML file and click Analyze</div>
          )}
          {!loading && !result && mode === MODE_DRAW && (
            <div className="map-hint">Draw a rectangle on the map, then click Analyze Area</div>
          )}

          <MapContainer
            center={[21.25, 81.3]}
            zoom={10}
            style={{ width: '100%', height: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <DrawControl
              onBoundsSelected={setSelectedBounds}
              enabled={drawEnabled}
            />
            {result && (
              <ResultsOverlay
                data={result}
                inputBoundary={inputBoundary}
              />
            )}
          </MapContainer>
        </div>
      </div>
    </div>
  )
}
