# System Design Integration — Village Pond Planning System

> **Rule**: Core app on main machine stays untouched.  
> All additions here are read-only observers or separate services.

---

## Architecture Overview

```
[Users / Browser]
       |
  WiFi Network (port routing: machine 22XX port P → external port 5XXX)
       |
    ┌──┴──────────────────────────────────────────────────────┐
    │  Machine 2208 (this laptop, 10.50.24.226)              │
    │  Port 5000  → existing FastAPI app (CORE — DO NOT TOUCH)│
    └──┬──────────────────────────────────────────────────────┘
       |
    ┌──┴──────────┐   ┌──────────────┐   ┌──────────────────┐
    │ Machine 2205│   │ Machine 2206 │   │ Machine 2207      │
    │ Port 5000   │   │ Port 5000    │   │ Port 5000         │
    │ Replica app │   │ Load monitor │   │ Stress test node  │
    │ (read-only) │   │ + metrics    │   │ (locust runner)   │
    └─────────────┘   └──────────────┘   └──────────────────┘
```

**Port external access**: machine 22XX running port P → accessible at P+XX  
(e.g., 2207 port 5000 → external 5207, 2207 port 4000 → external 4207)

---

## What Each Machine Does

### Machine 2208 (this laptop) — Primary App
- Existing FastAPI + uvicorn on port 5000 **unchanged**
- SRTM tiles for Chhattisgarh coverage
- Auto-restart loop via `start_server.sh`

### Machine 2205 — Replica (Read-Only)
- **Purpose**: show horizontal scaling is possible
- Clone repo, run same app on port 5000
- Uses rsync'd SRTM tiles from 2208
- Demonstrates: if 2208 OOMs, 2205 still serves

### Machine 2206 — Metrics / Monitoring
- **Purpose**: show system limitations awareness
- Run lightweight metrics collector (Python script, no extra deps)
- Polls 2208 and 2205 `/health` every 5s
- Serves simple JSON dashboard on port 5000
- Tracks: response time, memory (via `/proc`), uptime

### Machine 2207 — Stress Test Node
- **Purpose**: demonstrate stress/load testing
- Run `locust` against 2208 app
- 10–50 simulated users, ramp 10/s
- Results viewable at port 4000 (locust UI) → external 4207

---

## Implementation Steps (Minimal)

### Step 1 — Verify SSH access (you confirm IPs)
```bash
ssh avinash@<IP_2205>  # password: 2205
ssh avinash@<IP_2206>  # password: 2206
ssh avinash@<IP_2207>  # password: 2207
```

### Step 2 — Health endpoint on main app (1 line addition)
Add to `backend/app/main.py` — already exists or trivial to add:
```python
@app.get("/health")
def health(): return {"status": "ok", "machine": "2208"}
```

### Step 3 — Deploy replica on 2205
```bash
# On 2205:
git clone <repo_url> ~/Assignment_1
rsync -az avinash@10.x.x.x:/home/avinash/CSD_LAB/Assignment_1/backend/app/data/srtm/ ~/Assignment_1/backend/app/data/srtm/
cd ~/Assignment_1/backend && pip install -r requirements.txt
NUMBA_DISABLE_JIT=1 uvicorn app.main:app --host 0.0.0.0 --port 5000 &
```

### Step 4 — Metrics collector on 2206
Single Python script `metrics_server.py` — polls health endpoints, serves JSON:
```
GET http://10.x.x.x:5000/metrics  → {"machines": [...], "timestamp": "..."}
```
No extra pip install — uses stdlib `http.server` + `urllib`.

### Step 5 — Stress test on 2207
```bash
pip install locust
locust -f locustfile.py --host http://10.x.x.x:5000 --headless -u 20 -r 5 --run-time 2m
# Or with UI:
locust -f locustfile.py --host http://10.x.x.x:5000 --web-port 4000
```

---

## System Limitations Addressed

| Concern | Evidence shown |
|---------|---------------|
| Memory OOM | NUMBA_DISABLE_JIT, auto-restart loop, lazy pysheds import |
| Concurrent users | Replica on 2205; locust shows degradation at ~20 users |
| SRTM tile missing | Clear error message returned, not silent crash |
| Single point of failure | 2205 replica stays up if 2208 crashes |
| Response time | Metrics dashboard shows latency per endpoint |

---

## Files to Create

- `backend/app/main.py` — add `/health` endpoint (2 lines)
- `metrics_server.py` — monitoring service for 2206 (stdlib only)
- `locustfile.py` — stress test scenarios for 2207
- `setup_replica.sh` — one-shot setup script for 2205

---

## What Will NOT Change

- `area_analysis_service.py` — no touch
- `hydrology_engine.py` — no touch  
- `App.jsx` / frontend — no touch
- `start_server.sh` — no touch
- All existing routes and logic

---

## Timeline

1. Confirm SSH IPs for 2205/2206/2207 → **5 min**
2. Add `/health` endpoint → **2 min**
3. `metrics_server.py` + `locustfile.py` → **10 min**
4. Deploy on 2205 and 2207 → **10 min**
5. Verify all 4 systems running → **5 min**

**Total: ~30 min**
