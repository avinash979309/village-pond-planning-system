"""
redis_cache.py — Thin Redis wrapper for analyzeArea result caching.

Graceful fallback: if Redis is unavailable, returns None (caller computes normally).
Key format: analyzeArea:{west:.4f}:{south:.4f}:{east:.4f}:{north:.4f}
TTL: 86400s (24h) — SRTM-derived terrain doesn't change.
"""

import json
import logging
import os

log = logging.getLogger(__name__)

_REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
_CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "86400"))

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import redis  # lazy import — not installed on replicas without Redis
        _client = redis.Redis(
            host=_REDIS_HOST,
            port=_REDIS_PORT,
            db=0,
            socket_connect_timeout=1,
            socket_timeout=2,
            decode_responses=True,
        )
        _client.ping()
        log.info("Redis connected at %s:%s", _REDIS_HOST, _REDIS_PORT)
    except Exception as exc:
        log.warning("Redis unavailable (%s) — cache disabled, computing normally", exc)
        _client = None
    return _client


def _bbox_key(west: float, south: float, east: float, north: float) -> str:
    return f"analyzeArea:{west:.4f}:{south:.4f}:{east:.4f}:{north:.4f}"


def get(west: float, south: float, east: float, north: float):
    """Return cached result dict or None."""
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(_bbox_key(west, south, east, north))
        if raw:
            log.info("Cache HIT for bbox %.4f,%.4f,%.4f,%.4f", west, south, east, north)
            return json.loads(raw)
    except Exception as exc:
        log.warning("Redis get error: %s — proceeding without cache", exc)
    return None


def set(west: float, south: float, east: float, north: float, result: dict) -> None:
    """Store result in cache. Silently ignores errors."""
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(
            _bbox_key(west, south, east, north),
            _CACHE_TTL,
            json.dumps(result),
        )
        log.info("Cache SET for bbox %.4f,%.4f,%.4f,%.4f (TTL %ds)", west, south, east, north, _CACHE_TTL)
    except Exception as exc:
        log.warning("Redis set error: %s — result not cached", exc)
