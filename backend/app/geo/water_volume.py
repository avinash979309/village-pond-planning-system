"""
water_volume.py — simple runoff volume estimator.

Formula: V = A × R × C
  A = catchment area (m²)
  R = annual rainfall depth (m)  — default 800 mm for Central India
  C = runoff coefficient         — 0.35 for mixed agricultural/forest

ponytail: SCS-CN not needed for assignment; simple rational formula sufficient.
Add SCS-CN if instructor asks for curve-number-based estimate.
"""

# Default values for Chhattisgarh / Central India region
DEFAULT_ANNUAL_RAINFALL_MM = 800.0   # mm/year — conservative for region
DEFAULT_RUNOFF_COEFFICIENT = 0.35    # fraction of rainfall that becomes runoff
POND_DEPTH_M = 2.5                   # assumed usable pond depth (m)


def estimate_water_volume(
    catchment_area_m2: float,
    annual_rainfall_mm: float = DEFAULT_ANNUAL_RAINFALL_MM,
    runoff_coefficient: float = DEFAULT_RUNOFF_COEFFICIENT,
    pond_depth_m: float = POND_DEPTH_M,
) -> dict:
    """
    Estimate annual runoff volume and pond storage for a catchment.

    Returns dict with:
      annual_runoff_m3    — total runoff volume per year (m³)
      annual_runoff_ML    — same in megalitres
      pond_storage_m3     — recommended pond capacity (based on pond_area × depth)
      pond_area_m2        — pond surface area estimate (10% of catchment)
      assumptions         — parameter dict for report transparency
    """
    rainfall_m = annual_rainfall_mm / 1000.0
    annual_runoff_m3 = catchment_area_m2 * rainfall_m * runoff_coefficient

    # Pond surface = 10% of catchment is a common rural guideline
    pond_area_m2 = catchment_area_m2 * 0.10
    pond_storage_m3 = pond_area_m2 * pond_depth_m

    # Effective storage = min(runoff, pond capacity)
    effective_storage_m3 = min(annual_runoff_m3, pond_storage_m3)

    return {
        "annual_runoff_m3": round(annual_runoff_m3, 1),
        "annual_runoff_ML": round(annual_runoff_m3 / 1000, 3),
        "pond_storage_m3": round(pond_storage_m3, 1),
        "pond_area_m2": round(pond_area_m2, 1),
        "effective_storage_m3": round(effective_storage_m3, 1),
        "assumptions": {
            "annual_rainfall_mm": annual_rainfall_mm,
            "runoff_coefficient": runoff_coefficient,
            "pond_depth_m": pond_depth_m,
            "pond_area_fraction": 0.10,
            "method": "Rational method: V = A × R × C",
        },
    }
