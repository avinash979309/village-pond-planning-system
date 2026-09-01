"""
FastAPI application entry point.

Mounts all API routers, configures CORS, and exposes the health endpoint.
"""

# ── Compatibility shim ────────────────────────────────────────────────────────
# pysheds (<=0.5) uses np.in1d, removed in NumPy 2.0.
# np.isin is the modern equivalent for 1-D membership testing.
import numpy as _numpy_compat
if not hasattr(_numpy_compat, "in1d"):
    def _in1d_compat(ar1, ar2, **kw):
        """np.in1d removed in NumPy 2.0 — redirect to np.isin (equivalent for 1-D)."""
        import numpy as _n
        return _n.isin(ar1, ar2, **kw).ravel()
    _numpy_compat.in1d = _in1d_compat
    del _in1d_compat
del _numpy_compat
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1.router import api_router
from app.services.contour_analysis_service import analyze_contour as _analyze_contour

app = FastAPI(
    title="Village Pond Planning System API",
    description=(
        "Backend API for the AI-based Village Pond Planning System. "
        "Provides terrain analysis, catchment delineation, and pond "
        "site recommendation from contour maps and DEM data."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["Health"])
async def health():
    """Basic liveness check."""
    return {"status": "ok", "version": "0.1.0"}


# ── Root route ────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    """API information and available endpoints."""
    return {
        "name": "Village Pond Planning System API",
        "version": "0.1.0",
        "status": "running",
        "usage": {
            "analyze": "POST /analyzeContour  — upload a KML/KMZ contour map",
            "docs": "GET /docs  — interactive API documentation",
            "health": "GET /api/v1/health  — liveness check",
        },
        "description": (
            "Upload a contour map to identify optimal pond locations. "
            "Returns up to 3 ranked candidates with catchment area, coordinates, "
            "and suitability scores."
        ),
    }


# ── Simple top-level route ────────────────────────────────────────────────────
from fastapi import UploadFile

@app.post(
    "/analyzeContour",
    tags=["Pond Analysis"],
    summary="Analyze a contour map and identify optimal pond locations",
    description=(
        "Upload a KML or KMZ contour map. "
        "The API analyzes terrain, identifies optimal pond sites away from rivers, "
        "and returns up to 3 ranked candidates with catchment area and coordinates. "
        "**No extra parameters needed** — just upload the file."
    ),
)
async def analyze_contour_simple(file: UploadFile):
    """
    POST /analyzeContour

    Upload a KML or KMZ contour map. Returns pond location,
    pour point, and catchment area as structured JSON.

    Simple single-file endpoint — no extra parameters needed.
    """
    file_bytes = await file.read()
    result = await _analyze_contour(
        file_bytes=file_bytes,
        filename=file.filename or "upload.kml",
        grid_resolution=200,
        drainage_threshold_pct=2.0,
        drainage_buffer_cells=2,
        snap_radius_cells=5,
        skip_osm=False,
    )

    # Best candidate
    candidates = result.get("top_candidates", [])
    best = candidates[0] if candidates else {}
    pond_props = best.get("pond_candidate", {}).get("properties", {})
    pond_coords = best.get("pond_candidate", {}).get("geometry", {}).get("coordinates", [])
    catchment_props = best.get("catchment", {}).get("properties", {})
    pour_coords = best.get("pour_point", {}).get("geometry", {}).get("coordinates", [])

    return {
        "status": "success",
        "pond_location": {
            "longitude": pond_coords[0] if pond_coords else None,
            "latitude": pond_coords[1] if pond_coords else None,
            "elevation_m": pond_props.get("elevation_m"),
            "suitability_score": pond_props.get("suitability_score"),
        },
        "pour_point": {
            "longitude": pour_coords[0] if pour_coords else None,
            "latitude": pour_coords[1] if pour_coords else None,
        },
        "catchment": {
            "area_km2": catchment_props.get("area_km2") or catchment_props.get("area_sq_km"),
            "area_m2": catchment_props.get("area_sq_m"),
            "avg_elevation_m": catchment_props.get("avg_elevation_m"),
            "boundary_geojson": best.get("catchment", {}).get("geometry"),
        },
        "all_candidates": [
            {
                "rank": c["rank"],
                "longitude": c["pond_candidate"]["geometry"]["coordinates"][0],
                "latitude": c["pond_candidate"]["geometry"]["coordinates"][1],
                "suitability_score": c["pond_candidate"]["properties"].get("suitability_score"),
                "catchment_area_km2": (
                    c["catchment"]["properties"].get("area_km2")
                    or c["catchment"]["properties"].get("area_sq_km")
                ),
            }
            for c in candidates
        ],
        "osm_water_exclusion": result.get("osm_water_exclusion", {}),
    }

