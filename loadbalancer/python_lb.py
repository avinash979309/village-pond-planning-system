"""
python_lb.py — Round-robin load balancer for Village Pond Planning System.

Backends: sys1, sys2, sys3, sys4 (all port 5000 on their internal IPs).
Health check: GET /health on each backend every 10s.
Dead backends are skipped; revived automatically on next health pass.

Run on sys1:  uvicorn lb_app:app --host 0.0.0.0 --port 6000 --workers 1
"""

import asyncio
import logging
import time
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("lb")

# ── Backend pool ──────────────────────────────────────────────────────────────
BACKENDS = [
    "http://172.17.0.100:5000",   # sys1
    "http://172.17.0.11:5000",    # sys2
    "http://172.17.0.98:5000",    # sys3
    "http://172.17.0.16:5000",    # sys4
]

# Track liveness: True = alive, False = dead
_alive = {b: True for b in BACKENDS}
_rr_index = 0          # round-robin cursor
_HEALTH_INTERVAL = 10  # seconds between health checks


def _next_backend() -> Optional[str]:
    """Return next alive backend (round-robin), or None if all dead."""
    global _rr_index
    for _ in range(len(BACKENDS)):
        b = BACKENDS[_rr_index % len(BACKENDS)]
        _rr_index += 1
        if _alive.get(b, False):
            return b
    return None


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Pond LB", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def start_health_loop():
    asyncio.create_task(_health_loop())


async def _health_loop():
    """Background task: ping every backend every HEALTH_INTERVAL seconds."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            for b in BACKENDS:
                try:
                    r = await client.get(f"{b}/health")
                    was_alive = _alive[b]
                    _alive[b] = r.status_code == 200
                    if not was_alive and _alive[b]:
                        log.info(f"Backend RECOVERED: {b}")
                    elif was_alive and not _alive[b]:
                        log.warning(f"Backend DOWN: {b}")
                except Exception:
                    if _alive.get(b):
                        log.warning(f"Backend DOWN: {b}")
                    _alive[b] = False
            await asyncio.sleep(_HEALTH_INTERVAL)


@app.get("/lb/health")
async def lb_health():
    return {"lb": "ok", "backends": _alive}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
)
async def proxy(request: Request, path: str):
    backend = _next_backend()
    if backend is None:
        return JSONResponse({"error": "All backends unavailable"}, status_code=503)

    url = f"{backend}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    headers = dict(request.headers)
    headers.pop("host", None)
    body = await request.body()

    timeout = httpx.Timeout(150.0, connect=10.0)  # 150s for long analyses
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
            )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
            media_type=resp.headers.get("content-type"),
        )
    except httpx.TimeoutException:
        _alive[backend] = False
        log.warning(f"Timeout on {backend} — marked dead")
        return JSONResponse({"error": "Backend timeout"}, status_code=504)
    except Exception as e:
        _alive[backend] = False
        log.warning(f"Error on {backend}: {e} — marked dead")
        return JSONResponse({"error": "Backend error"}, status_code=502)
