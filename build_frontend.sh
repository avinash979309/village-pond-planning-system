#!/bin/bash
# build_frontend.sh — build React frontend and copy dist/ into place
set -e
cd "$(dirname "$0")/frontend"
echo "Installing deps..."
npm ci
echo "Building..."
npm run build
echo "Done. dist/ at frontend/dist/"
echo "Restart the backend to serve updated frontend at http://localhost:5000/app"
