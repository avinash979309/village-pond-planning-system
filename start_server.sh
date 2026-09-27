#!/bin/bash
# start_server.sh — auto-restarts uvicorn if it crashes (OOM kill etc.)
#
# NUMBA_DISABLE_JIT=1 prevents numba/llvmlite JIT spike (500MB-1GB RAM)
# MALLOC_TRIM_THRESHOLD_=100000 releases memory back to OS aggressively

cd "$(dirname "$0")/backend"

export NUMBA_DISABLE_JIT=1
export NUMBA_CACHE_DIR=/tmp/numba_cache_pond
export MALLOC_TRIM_THRESHOLD_=100000

source venv/bin/activate

echo "[server] Starting with auto-restart loop. Ctrl-C twice to stop."

while true; do
  echo "[server] $(date '+%H:%M:%S') — uvicorn starting..."
  uvicorn app.main:app --host 0.0.0.0 --port 5000
  EXIT=$?
  echo "[server] $(date '+%H:%M:%S') — uvicorn exited (code $EXIT). Restarting in 3s..."
  sleep 3
done
