#!/bin/bash
# setup_replica.sh — Deploy app replica on another machine (2205/2206/2207)
# Run THIS script ON the other machine.
# Usage: bash setup_replica.sh <PRIMARY_IP> <THIS_MACHINE_ID>
# Example: bash setup_replica.sh 10.50.24.226 2205

set -e
PRIMARY_IP="${1:-10.50.24.226}"
MACHINE_ID="${2:-2205}"
REPO_URL="https://github.com/YOUR_REPO_URL/Assignment_1.git"  # replace if needed

echo "[setup] Machine $MACHINE_ID — cloning repo..."
[ -d ~/Assignment_1 ] && echo "Already cloned, pulling..." && git -C ~/Assignment_1 pull && cd ~/Assignment_1 || \
  git clone "$REPO_URL" ~/Assignment_1

cd ~/Assignment_1

echo "[setup] Syncing SRTM tiles from primary ($PRIMARY_IP)..."
mkdir -p backend/app/data/srtm
rsync -az --progress "avinash@${PRIMARY_IP}:/home/avinash/CSD_LAB/Assignment_1/backend/app/data/srtm/" \
  backend/app/data/srtm/

echo "[setup] Installing Python deps..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -q

echo "[setup] Starting replica server on port 5000..."
NUMBA_DISABLE_JIT=1 MALLOC_TRIM_THRESHOLD_=100000 \
  nohup uvicorn app.main:app --host 0.0.0.0 --port 5000 \
  > ~/replica_server.log 2>&1 &

sleep 3
curl -s "http://localhost:5000/health" && echo "" && echo "[setup] Replica up on machine $MACHINE_ID ✓"
