#!/bin/bash
# setup_lb.sh — Install Nginx + Redis on sys1, configure load balancer
# Run ON sys1 (student@10.1.75.53 -p 2205)
# Usage: bash setup_lb.sh
#
# After this: LB accessible at 10.1.75.53:5305 (sys1 port 5100)
# sys1:5000 still works unchanged.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[lb] Installing Nginx and Redis..."
sudo apt-get update -q
sudo apt-get install -y nginx redis-server

echo "[lb] Starting Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping && echo "[lb] Redis OK"

echo "[lb] Installing redis-py in backend venv..."
source "$SCRIPT_DIR/backend/venv/bin/activate"
pip install redis -q
deactivate

echo "[lb] Configuring Nginx..."
sudo cp "$SCRIPT_DIR/nginx_lb.conf" /etc/nginx/sites-available/pond_lb
sudo ln -sf /etc/nginx/sites-available/pond_lb /etc/nginx/sites-enabled/pond_lb
# Disable default site if present
[ -f /etc/nginx/sites-enabled/default ] && sudo rm -f /etc/nginx/sites-enabled/default || true

sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo ""
echo "[lb] ✓ Done. Test:"
echo "  curl http://localhost:5100/health"
echo "  curl http://localhost:5100/app/"
echo ""
echo "[lb] External URL: http://10.1.75.53:5305/app/"
echo "[lb] sys1 direct (unchanged): http://10.1.75.53:5205/app/"
