#!/bin/bash
# deploy_replica.sh — Deploy app replica on sys2/3/4
# Run from LOCAL machine (this laptop).
# Usage: bash deploy_replica.sh <SSH_PORT> <MACHINE_ID>
# Example: bash deploy_replica.sh 2206 sys2
#          bash deploy_replica.sh 2207 sys3
#          bash deploy_replica.sh 2208 sys4
#
# What it does:
#   1. Git push latest code (sys1 must have remote access)
#   2. SSH into target machine, git pull, install deps, start server
#   3. Rsync SRTM tiles from sys1 to target
#   4. Verify /health responds

set -e

SSH_PORT="${1:-2206}"
MACHINE_ID="${2:-sys2}"
REMOTE_USER="student"
REMOTE_HOST="10.1.75.53"
PASS="abhi1patel"
REPO_DIR="/home/student/village-pond-planning-system"
SYS1_PORT="2205"

# Helper: run command on target machine (retry once on timeout)
ssh_cmd() {
    for i in 1 2 3; do
        SSHPASS="$PASS" sshpass -e ssh \
            -o StrictHostKeyChecking=no \
            -o ConnectTimeout=15 \
            -p "$SSH_PORT" \
            "$REMOTE_USER@$REMOTE_HOST" \
            "$@" && return 0
        echo "[deploy] attempt $i failed, retrying..."
        sleep 2
    done
    echo "[deploy] SSH failed after 3 attempts" && exit 1
}

echo "[deploy] === Deploying to $MACHINE_ID (port $SSH_PORT) ==="

echo "[deploy] Checking if repo exists..."
ssh_cmd "[ -d $REPO_DIR ] && echo exists || echo missing"

echo "[deploy] Pulling latest code..."
ssh_cmd "
    if [ ! -d $REPO_DIR ]; then
        git clone https://github.com/avinash979309/village-pond-planning-system.git $REPO_DIR 2>/dev/null || \
        git clone http://github.com/avinash979309/village-pond-planning-system.git $REPO_DIR
    fi
    cd $REPO_DIR
    git fetch origin
    git reset --hard origin/main
    echo '[deploy] Code updated'
"

echo "[deploy] Setting up Python venv + deps..."
ssh_cmd "
    cd $REPO_DIR/backend
    [ -d venv ] || python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt -q
    pip install redis -q
    echo '[deploy] Deps OK'
"

echo "[deploy] Rsyncing SRTM tiles from sys1..."
# Run rsync FROM sys1 to target machine via reverse: this script SSHes into sys1,
# which then rsyncs to target. Simpler: just rsync from local if SRTM tiles are local.
# Tiles are large — skip if already present on target.
ssh_cmd "
    mkdir -p $REPO_DIR/backend/app/data/srtm
    TILE_COUNT=\$(ls $REPO_DIR/backend/app/data/srtm/*.hgt 2>/dev/null | wc -l)
    echo \"[deploy] SRTM tiles on $MACHINE_ID: \$TILE_COUNT\"
    if [ \$TILE_COUNT -lt 5 ]; then
        echo '[deploy] Few tiles found — rsyncing from sys1...'
        SSHPASS='$PASS' sshpass -e rsync -az --progress \
            -e 'ssh -o StrictHostKeyChecking=no -p $SYS1_PORT' \
            $REMOTE_USER@$REMOTE_HOST:$REPO_DIR/backend/app/data/srtm/ \
            $REPO_DIR/backend/app/data/srtm/ 2>/dev/null || echo '[deploy] rsync failed, tiles will be absent'
    else
        echo '[deploy] SRTM tiles already present, skipping rsync'
    fi
"

echo "[deploy] Starting server (port 5000)..."
ssh_cmd "
    cd $REPO_DIR

    # Kill existing server if running
    pkill -f 'uvicorn app.main:app' 2>/dev/null || true
    sleep 1

    # Point all nodes at sys1 Redis
    export REDIS_HOST=127.0.0.1   # sys1 listens on 127.0.0.1 by default
    # Use sys1's Redis via the external port mapping: sys1:6379 is internal-only.
    # Set REDIS_HOST to sys1's LAN IP if accessible, else fallback gracefully.
    # For now let cache fallback silently on replicas (Redis not exposed externally).

    export NUMBA_DISABLE_JIT=1
    export NUMBA_CACHE_DIR=/tmp/numba_cache_pond
    export MALLOC_TRIM_THRESHOLD_=100000
    export MACHINE_ID=$MACHINE_ID

    source backend/venv/bin/activate
    nohup bash start_server.sh > ~/server_$MACHINE_ID.log 2>&1 &
    sleep 4
    curl -s http://localhost:5000/health | python3 -m json.tool 2>/dev/null || \
        curl -s http://localhost:5000/health
    echo ''
    echo '[deploy] Server started on $MACHINE_ID'
"

echo ""
echo "[deploy] === $MACHINE_ID deployed ==="
echo "  Direct:   http://$REMOTE_HOST:$((5000 + SSH_PORT - 2000))/app/"
echo "  Health:   http://$REMOTE_HOST:$((5000 + SSH_PORT - 2000))/health"
