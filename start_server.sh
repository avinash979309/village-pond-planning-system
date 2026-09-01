#!/bin/bash
# start_server.sh — run this instead of uvicorn directly
#
# NUMBA_DISABLE_JIT=1 prevents numba/llvmlite from doing JIT compilation
# when pysheds is first imported. Without this, the JIT spike can use
# 500MB-1GB of RAM and trigger the OOM killer on shared lab machines.
#
# MALLOC_TRIM_THRESHOLD_=100000 tells glibc to release memory back to the
# OS more aggressively after large allocations (pysheds, scipy) are freed.

cd "$(dirname "$0")/backend"

export NUMBA_DISABLE_JIT=1
export NUMBA_CACHE_DIR=/tmp/numba_cache_pond
export MALLOC_TRIM_THRESHOLD_=100000

source venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port 5000
