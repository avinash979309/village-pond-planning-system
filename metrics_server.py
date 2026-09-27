#!/usr/bin/env python3
"""
metrics_server.py — Lightweight monitoring for Village Pond Planning System.
Polls health endpoints on all 4 machines, serves JSON + simple HTML dashboard.
No extra pip install — stdlib only (http.server, urllib, threading).

Usage (on machine 2206):
  python3 metrics_server.py --port 5000
"""

import json
import threading
import time
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import urlopen
from urllib.error import URLError

# ── Config ────────────────────────────────────────────────────────────────────
# Fill actual IPs after SSH confirmed
MACHINES = [
    {"id": "2205", "url": "http://MACHINE_2205_IP:5000/health"},
    {"id": "2206", "url": "http://MACHINE_2206_IP:5000/health"},  # self
    {"id": "2207", "url": "http://MACHINE_2207_IP:5000/health"},
    {"id": "2208", "url": "http://MACHINE_2208_IP:5000/health"},  # primary
]
POLL_INTERVAL = 5  # seconds

# ── State ─────────────────────────────────────────────────────────────────────
_state = {"machines": [], "last_updated": ""}
_lock = threading.Lock()


def poll_once():
    results = []
    for m in MACHINES:
        entry = {"id": m["id"], "url": m["url"]}
        t0 = time.time()
        try:
            with urlopen(m["url"], timeout=4) as resp:
                data = json.loads(resp.read())
                entry["status"] = "up"
                entry["latency_ms"] = round((time.time() - t0) * 1000, 1)
                entry["response"] = data
        except URLError as e:
            entry["status"] = "down"
            entry["error"] = str(e)
            entry["latency_ms"] = None
        results.append(entry)
    return results


def poller():
    while True:
        results = poll_once()
        with _lock:
            _state["machines"] = results
            _state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        time.sleep(POLL_INTERVAL)


_HTML = """<!doctype html>
<html><head><meta charset=utf-8><title>Pond System Monitor</title>
<meta http-equiv="refresh" content="5">
<style>
body{font-family:monospace;background:#111;color:#eee;padding:20px}
h1{color:#4af}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #333;padding:8px 12px;text-align:left}
th{background:#222}.up{color:#4f4}.down{color:#f44}
</style></head><body>
<h1>🌿 Village Pond System Monitor</h1>
<p>Updated: {updated} | Refresh: 5s</p>
<table><tr><th>Machine</th><th>Status</th><th>Latency</th><th>Details</th></tr>
{rows}
</table>
<pre style="color:#888;font-size:11px">JSON: /metrics</pre>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # suppress access logs

    def do_GET(self):
        with _lock:
            state = dict(_state)

        if self.path == "/metrics":
            body = json.dumps(state, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/", "/monitor"):
            rows = ""
            for m in state.get("machines", []):
                cls = "up" if m["status"] == "up" else "down"
                lat = f"{m.get('latency_ms', '?')} ms" if m.get("latency_ms") else "—"
                detail = str(m.get("response", m.get("error", "")))
                rows += f'<tr><td>{m["id"]}</td><td class="{cls}">{m["status"].upper()}</td><td>{lat}</td><td>{detail}</td></tr>'
            body = _HTML.format(updated=state.get("last_updated", "—"), rows=rows).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    t = threading.Thread(target=poller, daemon=True)
    t.start()

    print(f"[monitor] Polling {len(MACHINES)} machines every {POLL_INTERVAL}s")
    print(f"[monitor] Dashboard at http://0.0.0.0:{args.port}/monitor")
    print(f"[monitor] JSON at http://0.0.0.0:{args.port}/metrics")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
