"""
python_lb.py — Pure Python round-robin load balancer for lab machines.
Uses FastAPI + httpx to proxy to all 4 backend nodes.
No nginx, no root, no systemd needed.

Usage:
    source backend/venv/bin/activate
    python python_lb.py

Listens on port 5100 (external: 10.1.75.53:5305 for sys1).
Backends: sys1:5000, sys2:5000, sys3:5000, sys4:5000
"""

import asyncio
import itertools
import os
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
import uvicorn

# ── Backend pool ──────────────────────────────────────────────────────────────
# Each backend is (label, base_url). sys1 is localhost; others via LAN port.
BACKENDS = [
    ("sys1", "http://127.0.0.1:5000"),
    ("sys2", "http://10.1.75.53:5206"),
    ("sys3", "http://10.1.75.53:5207"),
    ("sys4", "http://10.1.75.53:5208"),
]

_cycle = itertools.cycle(BACKENDS)
_lock  = asyncio.Lock()

app = FastAPI(title="Pond LB", docs_url=None, redoc_url=None)

# Shared httpx client — connection pool, keep-alive
_client: httpx.AsyncClient | None = None

@app.on_event("startup")
async def _startup():
    global _client
    _client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=180.0, write=30.0, pool=5.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        follow_redirects=True,
    )

@app.on_event("shutdown")
async def _shutdown():
    if _client:
        await _client.aclose()


async def _next_backend():
    async with _lock:
        return next(_cycle)


@app.api_route("/{path:path}", methods=["GET","POST","PUT","DELETE","PATCH","HEAD","OPTIONS"])
async def proxy(request: Request, path: str):
    label, base = await _next_backend()

    url = f"{base}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    body = await request.body()

    # Forward all original headers except Host
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
    headers["X-Via-LB-Node"]   = label

    try:
        resp = await _client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
    except httpx.ConnectError:
        # Backend down — try next node (simple fallback)
        label2, base2 = await _next_backend()
        url2 = f"{base2}/{path}"
        if request.url.query:
            url2 += f"?{request.url.query}"
        try:
            resp2 = await _client.request(request.method, url2, headers=headers, content=body)
            return Response(content=resp2.content, status_code=resp2.status_code, headers=dict(resp2.headers))
        except Exception as e:
            return JSONResponse({"error": f"all backends unreachable: {e}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": str(e), "backend": label}, status_code=502)


if __name__ == "__main__":
    port = int(os.environ.get("LB_PORT", "5100"))
    print(f"[lb] Starting round-robin proxy on port {port}")
    print(f"[lb] Backends: {[b for _, b in BACKENDS]}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
