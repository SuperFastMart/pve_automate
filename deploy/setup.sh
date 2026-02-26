#!/usr/bin/env bash
set -euo pipefail

# Peevinator Server Setup Script
# Run on a fresh Ubuntu 24.04 LXC container as root
# Usage: chmod +x deploy/setup.sh && ./deploy/setup.sh

REPO_URL="https://github.com/SuperFastMart/pve_automate.git"
INSTALL_DIR="/opt/peevinator"

echo "=== Peevinator Server Setup ==="

# ── 1. System packages ──────────────────────────────────────────────
echo "[1/8] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx git curl > /dev/null

# Node.js 20 LTS via NodeSource
if ! command -v node &> /dev/null; then
    echo "[1/8] Installing Node.js 20 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
    apt-get install -y -qq nodejs > /dev/null
fi
echo "       Python: $(python3 --version)"
echo "       Node:   $(node --version)"
echo "       npm:    $(npm --version)"

# ── 2. Clone or pull repo ───────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[2/8] Updating existing repo..."
    cd "$INSTALL_DIR"
    git pull --ff-only
else
    echo "[2/8] Cloning repo..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ── 3. Backend: Python venv + dependencies ──────────────────────────
echo "[3/8] Setting up Python backend..."
cd "$INSTALL_DIR/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# ── 4. Backend: .env file ───────────────────────────────────────────
echo "[4/8] Checking .env file..."
if [ ! -f ".env" ]; then
    cp "$INSTALL_DIR/.env.example" .env
    echo "       Created .env from .env.example — edit it with your credentials!"
    echo "       nano $INSTALL_DIR/backend/.env"
else
    echo "       .env already exists, skipping"
fi

# ── 5. Frontend: build ──────────────────────────────────────────────
echo "[5/8] Building frontend..."
cd "$INSTALL_DIR/frontend"
npm ci --silent
npm run build

# ── 6. Nginx config ─────────────────────────────────────────────────
echo "[6/8] Configuring nginx..."
rm -f /etc/nginx/sites-enabled/default
cp "$INSTALL_DIR/deploy/nginx.conf" /etc/nginx/sites-available/peevinator
ln -sf /etc/nginx/sites-available/peevinator /etc/nginx/sites-enabled/peevinator
nginx -t

# ── 7. systemd service ──────────────────────────────────────────────
echo "[7/8] Installing systemd service..."
cp "$INSTALL_DIR/deploy/peevinator.service" /etc/systemd/system/peevinator.service
systemctl daemon-reload

# ── 8. Ownership + start services ───────────────────────────────────
echo "[8/8] Setting permissions and starting services..."
chown -R www-data:www-data "$INSTALL_DIR/backend"
chown -R www-data:www-data "$INSTALL_DIR/frontend/dist"

systemctl enable --now peevinator
systemctl enable --now nginx
systemctl restart nginx

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit credentials:  nano $INSTALL_DIR/backend/.env"
echo "  2. Restart backend:   systemctl restart peevinator"
echo "  3. Check status:      systemctl status peevinator"
echo "  4. View logs:         journalctl -u peevinator -f"
echo "  5. Browse to:         http://$(hostname -I | awk '{print $1}')"
echo ""
