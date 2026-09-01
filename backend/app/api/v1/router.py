"""Aggregated API v1 router."""

from fastapi import APIRouter

from app.api.v1.contour import router as contour_router

api_router = APIRouter()

api_router.include_router(contour_router, prefix="/contour", tags=["Contour Analysis"])
