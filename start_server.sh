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

# ── Background hourly disk cleanup ───────────────────────────────────────────
# crontab unavailable on this machine, so we run a cleanup loop in background.
_disk_cleanup() {
  while true; do
    sleep 3600  # every hour
    # Truncate lb.log if > 10 MB (keep file handle open for lb process)
    LB_LOG="$HOME/loadbalancer/lb.log"
    if [ -f "$LB_LOG" ] && [ "$(stat -c%s "$LB_LOG" 2>/dev/null || echo 0)" -gt 10485760 ]; then
      truncate -s 0 "$LB_LOG"
      echo "[cleanup] $(date '+%H:%M:%S') — lb.log truncated"
    fi
    # Remove temp pond analysis dirs older than 2 hours
    find /tmp -maxdepth 1 -name 'pond_analysis_*' -type d -mmin +120 -exec rm -rf {} + 2>/dev/null
    echo "[cleanup] $(date '+%H:%M:%S') — disk: $(df -h / | awk 'NR==2{print $3" used / "$2" total ("$5")"}')"
  done
}
_disk_cleanup &
CLEANUP_PID=$!
echo "[server] Disk cleanup loop started (PID $CLEANUP_PID, runs every hour)"
# ─────────────────────────────────────────────────────────────────────────────

echo "[server] Starting with auto-restart loop. Ctrl-C twice to stop."

while true; do
  echo "[server] $(date '+%H:%M:%S') — uvicorn starting..."
  uvicorn app.main:app --host 0.0.0.0 --port 5000
  EXIT=$?
  echo "[server] $(date '+%H:%M:%S') — uvicorn exited (code $EXIT). Restarting in 3s..."
  sleep 3
done
