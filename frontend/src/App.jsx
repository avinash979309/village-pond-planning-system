import { useState, useRef, useCallback, useEffect } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'
import DrawControl from './DrawControl'
import ResultsOverlay from './ResultsOverlay'

import L from 'leaflet'
import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png'
import shadowUrl from 'leaflet/dist/images/marker-shadow.png'
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl })

const API_BASE = import.meta.env.VITE_API_BASE || ''
const MODE_KML  = 'kml'
const MODE_DRAW = 'draw'

// ── Analysis pipeline stages ────────────────────────────────────────────────
const KML_STAGES = [
  { label: 'Parsing contour map',       pct: 8,  dur: 4000  },
  { label: 'Building elevation grid',   pct: 20, dur: 8000  },
  { label: 'Conditioning terrain',      pct: 32, dur: 8000  },
  { label: 'Computing flow direction',  pct: 48, dur: 20000 },
  { label: 'Flow accumulation',         pct: 62, dur: 20000 },
  { label: 'Selecting pond candidates', pct: 74, dur: 10000 },
  { label: 'Delineating catchments',    pct: 88, dur: 30000 },
  { label: 'Finalising results',        pct: 96, dur: 5000  },
]
const AREA_STAGES = [
  { label: 'Loading SRTM elevation data', pct: 10, dur: 3000  },
  { label: 'Extracting elevation grid',   pct: 22, dur: 5000  },
  { label: 'Conditioning terrain',        pct: 36, dur: 8000  },
  { label: 'Computing flow direction',    pct: 50, dur: 20000 },
  { label: 'Flow accumulation',           pct: 64, dur: 20000 },
  { label: 'Selecting pond candidates',   pct: 76, dur: 10000 },
  { label: 'Delineating catchments',      pct: 88, dur: 30000 },
  { label: 'Finalising results',          pct: 96, dur: 5000  },
]

function useProgressTicker(loading, mode) {
  const [stageIdx, setStageIdx] = useState(0)
  const [pct, setPct]           = useState(0)
  const timerRef = useRef(null)

  useEffect(() => {
    if (!loading) {
      clearTimeout(timerRef.current)
      setStageIdx(0)
      setPct(0)
      return
    }
    const stages = mode === MODE_DRAW ? AREA_STAGES : KML_STAGES
    let idx = 0

    const advance = () => {
      if (idx >= stages.length) return
      setPct(stages[idx].pct)
      setStageIdx(idx)
      timerRef.current = setTimeout(() => { idx++; advance() }, stages[idx]?.dur ?? 5000)
    }
    advance()
    return () => clearTimeout(timerRef.current)
  }, [loading, mode])

  const stages = mode === MODE_DRAW ? AREA_STAGES : KML_STAGES
  return { stage: stages[stageIdx]?.label ?? 'Processing…', pct }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
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

const RANK_COLORS = ['#1565C0','#2e7d32','#6a1b9a']
const RANK_LABELS = ['🥇 Best Site','🥈 2nd Site','🥉 3rd Site']

function CandidatePanel({ c, rank }) {
  if (!c) return null
  const color = RANK_COLORS[Math.min(rank, 2)]
  const label = RANK_LABELS[Math.min(rank, 2)]
  return (
    <div className="candidate-panel" style={{ borderTopColor: color }}>
      <div className="rank-badge" style={{ background: color }}>{label}</div>
      <div className="stat-grid">
        <StatCard label="Score"           value={fmt(c.score, 3)}             cls="blue" />
        <StatCard label="Elevation"       value={`${fmt(c.elevation_m, 1)} m`} />
        <StatCard label="Flow accum."     value={fmt(c.flow_accumulation, 0)} cls="teal" />
        <StatCard label="Slope"           value={`${fmt(c.slope_deg, 2)}°`} />
        <StatCard label="Catchment area"  value={`${fmt(c.catchment?.area_sq_km, 2)} km²`} cls="blue" />
        <StatCard label="Avg elevation"   value={`${fmt(c.catchment?.avg_elevation_m, 1)} m`} />
        <StatCard label="Area (m²)"       value={`${fmt(c.catchment?.area_m2, 0)} m²`} />
      </div>
    </div>
  )
}

function ProgressBar({ pct, stage }) {
  return (
    <div className="progress-wrap">
      <div className="progress-header">
        <span className="progress-stage">{stage}</span>
        <span className="progress-pct">{pct}%</span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-steps">
        {KML_STAGES.map((s, i) => (
          <div key={i} className={`progress-dot ${pct >= s.pct ? 'done' : ''}`} title={s.label} />
        ))}
      </div>
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [mode, setMode]               = useState(MODE_KML)
  const [file, setFile]               = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)
  const [result, setResult]           = useState(null)
  const [activeTab, setActiveTab]     = useState(0)
  const [selectedBounds, setSelectedBounds] = useState(null)
  const [drawEnabled, setDrawEnabled] = useState(false)
  const [startTime, setStartTime]     = useState(null)
  const [elapsed, setElapsed]         = useState(null)
  const fileInputRef = useRef()
  const { stage, pct } = useProgressTicker(loading, mode)

  // Elapsed timer
  useEffect(() => {
    if (!loading) return
    setStartTime(Date.now())
    const iv = setInterval(() => setElapsed(((Date.now() - startTime) / 1000).toFixed(0)), 1000)
    return () => clearInterval(iv)
  }, [loading])

  // ── shared analysis runner ──────────────────────────────────────────────
  const runAnalysis = useCallback(async (url, body, isJson = false) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setElapsed(null)
    const t0 = Date.now()
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
      data._elapsed_s = ((Date.now() - t0) / 1000).toFixed(1)
      setResult(data)
      setElapsed(data._elapsed_s)
      setActiveTab(0)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleFileSubmit = () => {
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    runAnalysis('/analyzeContour', fd)
  }

  const handleAreaSubmit = () => {
    if (!selectedBounds) { setError('Draw a rectangle on the map first.'); return }
    const sw = selectedBounds.getSouthWest()
    const ne = selectedBounds.getNorthEast()
    runAnalysis('/analyzeArea', { west: sw.lng, south: sw.lat, east: ne.lng, north: ne.lat }, true)
  }

  const switchMode = (m) => {
    setMode(m); setError(null); setResult(null)
    setFile(null); setSelectedBounds(null); setDrawEnabled(false)
  }

  // Download JSON
  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `pond_analysis_${new Date().toISOString().slice(0,10)}.json`
    a.click()
  }

  const vol = result?.water_volume
  const inputBoundary = result?.input_boundary

  return (
    <div id="root">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <div className="header-logo">
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
              <circle cx="18" cy="18" r="18" fill="rgba(255,255,255,0.15)"/>
              <ellipse cx="18" cy="22" rx="10" ry="5" fill="rgba(255,255,255,0.3)"/>
              <path d="M10 22 Q14 14 18 18 Q22 22 26 14" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round"/>
              <circle cx="18" cy="13" r="3" fill="rgba(255,255,255,0.9)"/>
              <path d="M15 11 L18 7 L21 11" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
            </svg>
          </div>
          <div className="header-title">
            <h1>Village Pond Planning System</h1>
            <p>AI-powered optimal pond site identification for rural water harvesting</p>
          </div>
        </div>
        <div className="header-badges">
          <span className="badge">🛰️ SRTM DEM</span>
          <span className="badge">🌊 Hydrology</span>
          <span className="badge">📍 GIS</span>
        </div>
      </header>

      <div className="layout">
        {/* ── Sidebar ── */}
        <aside className="sidebar">

          {/* Mode tabs */}
          <div className="mode-tabs">
            <button className={`mode-tab ${mode === MODE_KML  ? 'active' : ''}`} onClick={() => switchMode(MODE_KML)}>
              📄 Upload KML
            </button>
            <button className={`mode-tab ${mode === MODE_DRAW ? 'active' : ''}`} onClick={() => switchMode(MODE_DRAW)}>
              🗺️ Draw Area
            </button>
          </div>

          {/* ── KML mode ── */}
          {mode === MODE_KML && (
            <div className="sidebar-section">
              <div className="section-header">
                <span className="section-icon">📄</span>
                <h2>Upload Contour Map</h2>
              </div>
              <div className="how-to-card">
                <div className="how-to-title">How to use</div>
                <ol>
                  <li>Upload a KML/KMZ contour map file</li>
                  <li>Click <b>Analyze</b> — takes ~60–90 s</li>
                  <li>View ranked pond sites on the map</li>
                  <li>Click map markers for detailed info</li>
                </ol>
              </div>
              <label className={`upload-label ${file ? 'has-file' : ''}`}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                {file ? file.name : 'Choose KML / KMZ file'}
                <input
                  ref={fileInputRef} type="file" accept=".kml,.kmz"
                  onChange={e => { setFile(e.target.files[0]); setResult(null); setError(null) }}
                />
              </label>
              <button className="btn btn-primary" disabled={!file || loading} onClick={handleFileSubmit}>
                {loading ? 'Analyzing…' : '▶ Analyze Contour Map'}
              </button>
              {file && (
                <button className="btn btn-clear" onClick={() => { setFile(null); setResult(null); setError(null) }}>
                  Clear
                </button>
              )}
            </div>
          )}

          {/* ── Draw mode ── */}
          {mode === MODE_DRAW && (
            <div className="sidebar-section">
              <div className="section-header">
                <span className="section-icon">🗺️</span>
                <h2>Select Area on Map</h2>
              </div>
              <div className="how-to-card">
                <div className="how-to-title">How to use</div>
                <ol>
                  <li>Click <b>Draw Rectangle</b> below</li>
                  <li>Click-drag on the map to select area</li>
                  <li>Click <b>Analyze Area</b> — uses SRTM elevation</li>
                  <li>View pond candidates on the map</li>
                </ol>
                <div className="coverage-note">
                  📍 Coverage: 21–22°N, 81–82°E (IIT Bhilai / Chhattisgarh)
                </div>
              </div>

              <button
                className={`btn ${drawEnabled ? 'btn-drawing-active' : 'btn-primary'}`}
                style={{ width: '100%' }}
                onClick={() => {
                  if (drawEnabled) { setDrawEnabled(false) }
                  else { setSelectedBounds(null); setResult(null); setError(null); setDrawEnabled(true) }
                }}
                disabled={loading}
              >
                {drawEnabled ? '✅ Drawing Active — click to stop' : '✏️ Draw Rectangle on Map'}
              </button>

              {drawEnabled && (
                <div className="draw-hint">🖱️ <b>Click and drag</b> on the map to draw rectangle</div>
              )}
              {!drawEnabled && !selectedBounds && (
                <div className="draw-hint">Click <b>Draw Rectangle</b> above, then drag on map</div>
              )}
              {selectedBounds && (
                <div className="draw-bounds-info">
                  ✅ Area selected
                  <div className="coords">
                    SW {selectedBounds.getSouthWest().lat.toFixed(4)}°N {selectedBounds.getSouthWest().lng.toFixed(4)}°E<br/>
                    NE {selectedBounds.getNorthEast().lat.toFixed(4)}°N {selectedBounds.getNorthEast().lng.toFixed(4)}°E
                  </div>
                </div>
              )}

              <button className="btn btn-primary" style={{ marginTop: 8 }}
                disabled={!selectedBounds || loading} onClick={handleAreaSubmit}>
                {loading ? 'Analyzing…' : '▶ Analyze Area'}
              </button>
              {selectedBounds && (
                <button className="btn btn-clear" onClick={() => {
                  setSelectedBounds(null); setResult(null); setError(null); setDrawEnabled(false)
                }}>Clear Selection</button>
              )}
            </div>
          )}

          {/* ── Progress ── */}
          {loading && (
            <div className="sidebar-section">
              <ProgressBar pct={pct} stage={stage} />
              <div className="progress-note">
                ⏱️ Analysis typically takes 60–120 seconds
              </div>
            </div>
          )}

          {/* ── Error ── */}
          {error && <div className="sidebar-section"><div className="error-box">⚠️ {error}</div></div>}

          {/* ── Results ── */}
          {result && (
            <div className="sidebar-section result-section">
              <div className="result-header">
                <h2>Results</h2>
                <div className="result-meta">
                  {result._elapsed_s && <span className="elapsed-badge">⏱ {result._elapsed_s}s</span>}
                  <button className="btn-icon" title="Download JSON" onClick={downloadJSON}>
                    ⬇ JSON
                  </button>
                </div>
              </div>

              {result.input_source && (
                <div className="input-source-badge">
                  {result.input_source === 'kml' ? '📄 KML contour map' : '🛰️ SRTM elevation data'}
                </div>
              )}

              {vol && (
                <div className="result-block">
                  <h3>💧 Water Harvest Estimate</h3>
                  <div className="stat-grid">
                    <StatCard label="Annual runoff"  value={`${fmt(vol.annual_runoff_m3,0)} m³`}    cls="blue" />
                    <StatCard label="Runoff (ML)"    value={`${fmt(vol.annual_runoff_ML,2)} ML`}    cls="blue" />
                    <StatCard label="Pond capacity"  value={`${fmt(vol.pond_storage_m3,0)} m³`}     cls="teal" />
                    <StatCard label="Eff. storage"   value={`${fmt(vol.effective_storage_m3,0)} m³`} cls="teal" />
                    <StatCard label="Assumptions"    cls="full"
                      value={`${vol.assumptions?.annual_rainfall_mm}mm/yr · C=${vol.assumptions?.runoff_coefficient} · ${vol.assumptions?.pond_depth_m}m depth`}
                    />
                  </div>
                </div>
              )}

              {result.all_candidates?.length > 0 && (
                <div className="result-block">
                  <h3>📍 Pond Candidates <span className="count-badge">{result.all_candidates.length}</span></h3>
                  <div className="tabs">
                    {result.all_candidates.map((_, i) => (
                      <button key={i} className={`tab ${activeTab === i ? 'active' : ''}`}
                        onClick={() => setActiveTab(i)}>#{i + 1}</button>
                    ))}
                  </div>
                  <CandidatePanel c={result.all_candidates[activeTab]} rank={activeTab} />
                </div>
              )}

              {result.osm_water_exclusion?.water_bodies_found && (
                <div className="result-block">
                  <h3>🌊 Water Body Exclusion</h3>
                  <p className="small-note">
                    {result.osm_water_exclusion.water_body_count} OSM water bodies excluded:{' '}
                    {result.osm_water_exclusion.water_body_names?.slice(0, 5).join(', ')}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* ── Info panel when idle ── */}
          {!loading && !result && !error && (
            <div className="info-panels">
              <div className="info-card">
                <div className="info-card-title">🔬 Analysis Pipeline</div>
                <div className="pipeline-steps">
                  {['SRTM Elevation', 'Terrain Conditioning', 'Flow Direction (D8)', 'Flow Accumulation', 'Candidate Selection', 'Catchment Delineation'].map((s, i) => (
                    <div key={i} className="pipeline-step">
                      <span className="step-num">{i + 1}</span>
                      <span>{s}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="info-card">
                <div className="info-card-title">📊 Selection Strategy</div>
                <ul className="strategy-list">
                  <li>High flow accumulation = natural water convergence</li>
                  <li>Low slope = minimal excavation cost</li>
                  <li>Upstream catchment = large harvest area</li>
                  <li>Water bodies excluded via OSM data</li>
                  <li>Top 5 candidates ranked by composite score</li>
                </ul>
              </div>

              <div className="info-card">
                <div className="info-card-title">⏱ Typical Timing</div>
                <div className="timing-list">
                  <div><span>KML upload analysis</span><span>60–90 s</span></div>
                  <div><span>Draw area analysis</span><span>60–120 s</span></div>
                  <div><span>SRTM resolution</span><span>30 m (1 arcsec)</span></div>
                  <div><span>Grid resolution</span><span>50 × 50</span></div>
                </div>
              </div>
            </div>
          )}

        </aside>

        {/* ── Map ── */}
        <div className="map-wrap">
          {loading && (
            <div className="map-overlay-loading">
              <div className="map-loading-inner">
                <div className="spinner" />
                <div>{stage}</div>
                <div className="map-pct">{pct}%</div>
              </div>
            </div>
          )}
          {!loading && !result && (
            <div className="map-hint">
              {mode === MODE_KML ? '📄 Upload a KML file and click Analyze' : '🗺️ Draw a rectangle on the map, then click Analyze Area'}
            </div>
          )}

          <MapContainer center={[21.25, 81.3]} zoom={10} style={{ width: '100%', height: '100%' }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <DrawControl onBoundsSelected={setSelectedBounds} enabled={drawEnabled} />
            {result && <ResultsOverlay data={result} inputBoundary={inputBoundary} />}
          </MapContainer>
        </div>
      </div>
    </div>
  )
}
