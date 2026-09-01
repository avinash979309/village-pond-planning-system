"""
Application configuration.

All values are read from environment variables (via .env file in development).
Never hardcode secrets or environment-specific values in source code.
"""

from __future__ import annotations

import json
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_env: str = "development"
    debug: bool = False

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Stored as a JSON array string in .env: ["http://localhost:5173"]
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── MongoDB ──────────────────────────────────────────────────────────────
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "pond_planner"

    # ── External APIs ────────────────────────────────────────────────────────
    opentopography_api_key: str = ""

    # ── Upload limits ────────────────────────────────────────────────────────
    max_upload_size_mb: int = 50

    # ── Geospatial processing defaults ───────────────────────────────────────
    default_grid_resolution: int = 200
    default_drainage_threshold_pct: float = 2.0
    default_drainage_buffer_cells: int = 2
    default_snap_radius_cells: int = 5

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
