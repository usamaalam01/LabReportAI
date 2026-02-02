#!/bin/bash
# ===========================================
# LabReportAI - Production Deployment Script
# ===========================================
# Run this on a fresh Ubuntu 22.04+ server (AMD64 or ARM64)
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Prerequisites:
#   - Ubuntu 22.04+ (AMD64 or ARM64)
#   - Root or sudo access
#   - Internet connection

set -e

echo "============================================="
echo "  LabReportAI - Production Deployment"
echo "============================================="

# --- Step 1: Install Docker ---
if ! command -v docker &> /dev/null; then
    echo "[1/6] Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to log out and back in for group changes."
else
    echo "[1/6] Docker already installed."
fi

# --- Step 2: Install Docker Compose plugin ---
if ! docker compose version &> /dev/null; then
    echo "[2/6] Installing Docker Compose plugin..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
else
    echo "[2/6] Docker Compose already installed."
fi

# --- Step 3: Clone repository (if not already cloned) ---
APP_DIR="$HOME/labreportai"
if [ ! -d "$APP_DIR" ]; then
    echo "[3/6] Cloning repository..."
    git clone https://github.com/usamaalam01/LabReportAI.git "$APP_DIR"
else
    echo "[3/6] Repository already exists. Pulling latest changes..."
    cd "$APP_DIR"
    git pull origin main
fi
cd "$APP_DIR"

# --- Step 4: Configure environment ---
if [ ! -f "$APP_DIR/.env" ]; then
    echo "[4/6] Setting up environment..."
    cp .env.production.example .env
    echo ""
    echo "================================================================"
    echo "  IMPORTANT: Edit .env file with your production values!"
    echo "  At minimum, set:"
    echo "    - DOMAIN (your DuckDNS subdomain)"
    echo "    - MYSQL_ROOT_PASSWORD (strong password)"
    echo "    - MYSQL_PASSWORD (strong password)"
    echo "    - LLM_API_KEY (your Groq API key)"
    echo "    - NEXT_PUBLIC_API_URL (https://your-domain)"
    echo "    - CORS_ORIGINS (https://your-domain)"
    echo ""
    echo "  Run: nano .env"
    echo "================================================================"
    echo ""
    read -p "Press Enter after editing .env to continue..."
else
    echo "[4/6] .env file already exists."
fi

# --- Step 5: Open firewall ports ---
echo "[5/6] Configuring firewall..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow 22/tcp
    sudo ufw --force enable
    echo "UFW firewall configured (ports 22, 80, 443 open)."
else
    echo "UFW not found. Make sure ports 80 and 443 are open in your cloud provider's security group/firewall."
fi

# Also open iptables (Oracle Cloud uses iptables by default)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT 2>/dev/null || true

# --- Step 6: Build and start services ---
echo "[6/6] Building and starting services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

echo ""
echo "============================================="
echo "  Deployment complete!"
echo "============================================="
echo ""
echo "Services starting up (may take 1-2 minutes)..."
echo ""
echo "Check status:  docker compose ps"
echo "View logs:     docker compose logs -f"
echo "Health check:  curl http://localhost:8000/v1/health"
echo ""
echo "Once DNS is configured, visit: https://$(grep DOMAIN .env | head -1 | cut -d= -f2)"
echo ""
