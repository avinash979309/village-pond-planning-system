"""
Contour analysis API routes.

POST /api/v1/contour/analyze-contour
    Full analysis — returns JSON with pond candidate, pour point, catchment,
    colored GeoJSON, and a one-click geojson.io visualization URL.

POST /api/v1/contour/analyze-contour/download-geojson
    Same analysis — returns a downloadable .geojson file with colour styling
    (pond=green, pour point=blue, catchment=red) so the user can drag-drop it
    into geojson.io or any GIS tool without any extra commands.

GET  /api/v1/contour/visualize/{result_id}
    Redirect to geojson.io using a stored result. Requires a prior call to
    analyze-contour which stores the result under a UUID.

Route responsibilities (ONLY):
- Validate uploaded file (type and size).
- Parse optional parameters.
- Delegate to contour_analysis_service.analyze_contour().
- Format and return the API response envelope.

This route contains NO geospatial logic.
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.config import settings
from app.services.contour_analysis_service import analyze_contour

router = APIRouter()

# Allowed file extensions (lowercase)
_ALLOWED_EXTENSIONS = {"kml", "kmz"}
# Allowed MIME types (not authoritative — extension check is primary)
_ALLOWED_MIME_TYPES = {
    "application/vnd.google-earth.kml+xml",
    "application/vnd.google-earth.kmz",
    "application/xml",
    "text/xml",
    "application/zip",
    "application/octet-stream",  # many clients send this for binary uploads
}

# Simple in-memory store for recent results (keyed by result_id UUID).
# Holds at most _RESULT_CACHE_LIMIT entries; oldest evicted when full.
_result_cache: dict[str, dict] = {}
_RESULT_CACHE_LIMIT = 20


# ── Main analysis endpoint ────────────────────────────────────────────────────

@router.post(
    "/analyze-contour",
    summary="Analyze a contour map and return catchment information",
    description=(
        "Upload a KML or KMZ contour map. "
        "The API parses contour lines, reconstructs an elevation surface, "
        "performs D8 hydrological analysis, fetches real water bodies from OSM "
        "(so results are never placed inside rivers/lakes), selects a pond candidate, "
        "and delineates the contributing catchment area. "
        "Response includes a `visualization_urls.geojson_io` link — click it to see "
        "pond (green), pour point (blue), and catchment (red) on a live map instantly. "
        "All results are derived algorithmically from the input — no hardcoded values."
    ),
    response_description="Structured catchment analysis result with GeoJSON geometries and visualization URLs",
    status_code=status.HTTP_200_OK,
)
async def analyze_contour_endpoint(
    file: UploadFile,
    grid_resolution: int = Form(default=200, ge=50, le=1000),
    drainage_threshold_pct: float = Form(default=2.0, ge=0.1, le=20.0),
    drainage_buffer_cells: int = Form(default=2, ge=0, le=20),
    snap_radius_cells: int = Form(default=5, ge=1, le=30),
    skip_osm: bool = Form(
        default=False,
        description=(
            "Set true to skip the OpenStreetMap water body query (faster, offline). "
            "When false (default), real rivers and lakes are excluded from candidate selection."
        ),
    ),
):
    """
    POST /api/v1/contour/analyze-contour

    **multipart/form-data fields:**
    - `file` (required): .kml or .kmz contour map
    - `grid_resolution` (optional, default 200): interpolation grid cells per axis
    - `drainage_threshold_pct` (optional, default 2.0): top N% of flow accumulation = drainage
    - `drainage_buffer_cells` (optional, default 2): exclusion buffer around drainage (cells)
    - `snap_radius_cells` (optional, default 5): pour-point snap search radius (cells)
    - `skip_osm` (optional, default false): skip OSM water body exclusion query

    **Response includes:**
    - `data.visualization_urls.geojson_io` — click to open geojson.io instantly
    - `data.colored_geojson` — download this as result.geojson for drag-drop visualization
    - `data.osm_water_exclusion` — OSM query status and water bodies found
    """
    result = await _run_analysis(
        file=file,
        grid_resolution=grid_resolution,
        drainage_threshold_pct=drainage_threshold_pct,
        drainage_buffer_cells=drainage_buffer_cells,
        snap_radius_cells=snap_radius_cells,
        skip_osm=skip_osm,
    )

    # Store result for /visualize/{result_id} redirect
    result_id = str(uuid.uuid4())
    _cache_result(result_id, result)

    return {
        "status": "success",
        "data": result,
        "result_id": result_id,
        "message": "Contour analysis complete.",
        "errors": [],
    }


# ── Download GeoJSON endpoint ─────────────────────────────────────────────────

@router.post(
    "/analyze-contour/download-geojson",
    summary="Analyze contour map and download a styled GeoJSON file",
    description=(
        "Same analysis as /analyze-contour but returns a downloadable .geojson file "
        "instead of JSON. The file is pre-styled with Mapbox SimpleStyle colours: "
        "pond candidate = green, pour point = blue, catchment = red. "
        "Drag-drop the downloaded file into https://geojson.io to visualise instantly."
    ),
    response_description="Downloadable styled GeoJSON FeatureCollection",
    status_code=status.HTTP_200_OK,
)
async def download_geojson_endpoint(
    file: UploadFile,
    grid_resolution: int = Form(default=200, ge=50, le=1000),
    drainage_threshold_pct: float = Form(default=2.0, ge=0.1, le=20.0),
    drainage_buffer_cells: int = Form(default=2, ge=0, le=20),
    snap_radius_cells: int = Form(default=5, ge=1, le=30),
    skip_osm: bool = Form(default=False),
):
    """
    POST /api/v1/contour/analyze-contour/download-geojson

    Returns a `result.geojson` file download — pre-coloured, ready for
    drag-drop into geojson.io or QGIS.

    **Colour legend:**
    - 🟢 Green = Pond Candidate
    - 🔵 Blue  = Pour Point (catchment outlet)
    - 🔴 Red   = Catchment Boundary
    """
    result = await _run_analysis(
        file=file,
        grid_resolution=grid_resolution,
        drainage_threshold_pct=drainage_threshold_pct,
        drainage_buffer_cells=drainage_buffer_cells,
        snap_radius_cells=snap_radius_cells,
        skip_osm=skip_osm,
    )

    geojson_bytes = json.dumps(result["colored_geojson"], indent=2).encode("utf-8")

    return Response(
        content=geojson_bytes,
        media_type="application/geo+json",
        headers={
            "Content-Disposition": "attachment; filename=\"result.geojson\"",
            "Content-Length": str(len(geojson_bytes)),
        },
    )


# ── Visualize redirect endpoint ───────────────────────────────────────────────

@router.get(
    "/visualize/{result_id}",
    summary="Redirect to geojson.io visualization for a stored result",
    description=(
        "Redirects the browser to geojson.io with the colored GeoJSON pre-loaded. "
        "The result_id is returned by POST /analyze-contour in the `result_id` field. "
        "Results are cached in memory for up to 20 requests."
    ),
    status_code=status.HTTP_302_FOUND,
)
async def visualize_result_endpoint(result_id: str):
    """
    GET /api/v1/contour/visualize/{result_id}

    Opens geojson.io with the pond candidate (green), pour point (blue),
    and catchment boundary (red) pre-loaded on a satellite map.

    Use the result_id from a previous POST /analyze-contour response.
    """
    result = _result_cache.get(result_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_envelope(
                f"Result '{result_id}' not found. "
                "Re-run the analysis to get a fresh result_id."
            ),
        )

    visualize_url = result.get("visualization_urls", {}).get("geojson_io")
    if not visualize_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_envelope("Visualization URL not available for this result."),
        )

    return RedirectResponse(url=visualize_url, status_code=status.HTTP_302_FOUND)


# ── Shared analysis helper ────────────────────────────────────────────────────

async def _run_analysis(
    file: UploadFile,
    grid_resolution: int,
    drainage_threshold_pct: float,
    drainage_buffer_cells: int,
    snap_radius_cells: int,
    skip_osm: bool,
) -> dict:
    """Validate file and run analysis. Shared by both POST endpoints."""
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_envelope(
                f"Unsupported file type '.{ext}'. Upload a .kml or .kmz file.",
                field="file",
            ),
        )

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_envelope("Uploaded file is empty.", field="file"),
        )

    if len(file_bytes) > settings.max_upload_size_bytes:
        max_mb = settings.max_upload_size_mb
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_envelope(
                f"File exceeds maximum allowed size of {max_mb} MB.", field="file"
            ),
        )

    try:
        result = await analyze_contour(
            file_bytes=file_bytes,
            filename=filename,
            grid_resolution=grid_resolution,
            drainage_threshold_pct=drainage_threshold_pct,
            drainage_buffer_cells=drainage_buffer_cells,
            snap_radius_cells=snap_radius_cells,
            skip_osm=skip_osm,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_envelope(str(exc)),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_envelope("Internal processing error. Please try again."),
        )

    return result


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_result(result_id: str, result: dict) -> None:
    """Store result in memory cache, evicting oldest if over limit."""
    if len(_result_cache) >= _RESULT_CACHE_LIMIT:
        oldest_key = next(iter(_result_cache))
        del _result_cache[oldest_key]
    _result_cache[result_id] = result


# ── Error envelope ────────────────────────────────────────────────────────────

def _error_envelope(message: str, field: Optional[str] = None) -> dict:
    """
    Build the standard error response body used across all endpoints.
    Does not expose stack traces or internal implementation details.
    """
    errors = [{"field": field or "general", "message": message}]
    return {
        "status": "error",
        "data": None,
        "message": message,
        "errors": errors,
    }
