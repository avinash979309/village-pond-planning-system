"""
Pydantic request/response schemas for the contour analysis endpoint.

All geographic outputs use GeoJSON Feature format for compatibility with
Leaflet, QGIS, and any standard GIS consumer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── GeoJSON primitives ────────────────────────────────────────────────────────

class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float] = Field(..., min_length=2, max_length=3)


class GeoJSONPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any] = Field(default_factory=dict)


# ── Analysis parameters (from multipart form) ─────────────────────────────────

class ContourAnalysisParams(BaseModel):
    """
    Optional tuning parameters for the contour analysis pipeline.
    All have sensible defaults. No sample-specific values.
    """
    grid_resolution: int = Field(
        default=200,
        ge=50,
        le=1000,
        description="Number of grid cells per axis for elevation interpolation.",
    )
    drainage_threshold_pct: float = Field(
        default=2.0,
        ge=0.1,
        le=20.0,
        description=(
            "Top N% of flow-accumulation values treated as drainage channels. "
            "Lower values = fewer, more prominent channels."
        ),
    )
    drainage_buffer_cells: int = Field(
        default=2,
        ge=0,
        le=20,
        description="Grid cells of exclusion buffer around drainage channels.",
    )
    snap_radius_cells: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Search radius (grid cells) for snapping pond candidate to pour point.",
    )


# ── Sub-schemas for the response ──────────────────────────────────────────────

class SpatialExtent(BaseModel):
    west: float
    east: float
    south: float
    north: float


class ElevationRange(BaseModel):
    min_m: float
    max_m: float


class InputSummary(BaseModel):
    filename: str
    file_format: str  # "kml" or "kmz"
    contour_line_count: int
    elevation_range_m: ElevationRange
    spatial_extent: SpatialExtent
    contour_interval_m: Optional[float]
    explicit_water_features_found: bool
    explicit_water_feature_count: int


class TerrainInfo(BaseModel):
    grid_resolution: int
    grid_shape: List[int]  # [rows, cols]
    interpolation_method: str
    cell_size_approx_m: List[float]  # [lon_cell_m, lat_cell_m]
    elevation_stats: Dict[str, float]  # min, max, mean, std


class DrainageInfo(BaseModel):
    method: str  # "terrain_derived" | "explicit_feature"
    drainage_threshold_pct: float
    drainage_cells_count: int
    exclusion_buffer_cells: int
    note: str


class ScoreBreakdown(BaseModel):
    elevation_score: float
    slope_score: float
    accumulation_score: float
    proximity_score: float


class PondCandidateProperties(BaseModel):
    elevation_m: float
    slope_degrees: float
    flow_accumulation: float
    suitability_score: float
    score_breakdown: ScoreBreakdown
    on_drainage_channel: bool
    exclusion_zone_respected: bool


class PourPointProperties(BaseModel):
    snap_distance_m: float
    flow_accumulation: float
    note: str


class CatchmentProperties(BaseModel):
    area_sq_km: float
    area_sq_m: float
    avg_elevation_m: float
    cell_count: int
    projection_used: str


class MethodologyInfo(BaseModel):
    contour_interpolation: str
    flow_direction_algorithm: str
    catchment_delineation: str
    area_calculation_projection: str
    drainage_derivation: str
    candidate_scoring: str
    weights: Dict[str, float]


# ── Top-level response ────────────────────────────────────────────────────────

class ContourAnalysisData(BaseModel):
    input_summary: InputSummary
    terrain: TerrainInfo
    drainage: DrainageInfo
    pond_candidate: GeoJSONFeature
    pour_point: GeoJSONFeature
    catchment: GeoJSONFeature
    methodology: MethodologyInfo


class ContourAnalysisResponse(BaseModel):
    """Standard API envelope used by all endpoints in this system."""
    status: str  # "success" | "error"
    data: Optional[ContourAnalysisData] = None
    message: str
    errors: List[Dict[str, str]] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    status: str = "error"
    data: None = None
    message: str
    errors: List[Dict[str, str]] = Field(default_factory=list)
