#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   AI Embedded DevOps Platform                    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Prerequisites — run these in PowerShell first:"
echo "   \$env:OLLAMA_HOST = '0.0.0.0'; ollama serve"
echo ""

cd ~/ai-embedded-devops
source venv/bin/activate

# ── auto-detect WSL2 host IP ──────────────────────────────────────────
WSL_HOST_IP=$(ip route | grep default | awk '{print $3}')
echo "WSL2 host IP: $WSL_HOST_IP"
sed -i "s|OLLAMA_URL=.*|OLLAMA_URL=http://${WSL_HOST_IP}:11434|" .env
sed -i "s|OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=http://${WSL_HOST_IP}:11434|" .env

# ── start infrastructure containers ──────────────────────────────────
echo ""
echo "Starting infrastructure..."
docker-compose up -d postgres redis prometheus grafana
sleep 5

# ── start RPi4 simulator ──────────────────────────────────────────────
echo "Starting RPi4 simulator..."
docker rm -f rpi4-sim 2>/dev/null || true
docker run -d \
  -p 8080:8080 \
  --name rpi4-sim \
  --network ai-embedded-devops_default \
  rpi4-sim

sleep 3

# ── update Trivy DB once at startup ───────────────────────────────────
echo "Updating Trivy vulnerability database..."
trivy image --download-db-only --quiet 2>/dev/null \
  && echo "  Trivy DB updated" \
  || echo "  Trivy DB update failed (using cached)"

# ── update Prometheus config with simulator IP ────────────────────────
SIM_IP=$(docker inspect rpi4-sim \
  --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' \
  | tr ' ' '\n' | grep "172.18" | head -1)

if [ -n "$SIM_IP" ]; then
  cat > ~/ai-embedded-devops/infra/prometheus.yml << PROM
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: rpi4_simulator
    static_configs:
      - targets: ['${SIM_IP}:8080']
    metrics_path: /metrics
PROM
  docker-compose restart prometheus > /dev/null 2>&1
  echo "Prometheus -> simulator at $SIM_IP"
fi

# ── health checks ─────────────────────────────────────────────────────
echo ""
echo "Health checks:"

docker exec devops_postgres pg_isready -U devops > /dev/null 2>&1 \
  && echo "  PostgreSQL   -> localhost:5432" \
  || echo "  PostgreSQL   -> not ready"

docker exec devops_redis redis-cli ping > /dev/null 2>&1 \
  && echo "  Redis        -> localhost:6379" \
  || echo "  Redis        -> not ready"

curl -s http://localhost:8080/health > /dev/null 2>&1 \
  && echo "  Simulator    -> http://localhost:8080" \
  || echo "  Simulator    -> not ready"

curl -s http://localhost:9090/-/ready > /dev/null 2>&1 \
  && echo "  Prometheus   -> http://localhost:9090" \
  || echo "  Prometheus   -> not ready"

curl -s http://localhost:3000/api/health > /dev/null 2>&1 \
  && echo "  Grafana      -> http://localhost:3000 (admin/admin)" \
  || echo "  Grafana      -> not ready"

curl -s http://${WSL_HOST_IP}:11434/api/tags > /dev/null 2>&1 \
  && echo "  Ollama       -> models ready" \
  || echo "  Ollama       -> start in PowerShell: \$env:OLLAMA_HOST='0.0.0.0'; ollama serve"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Service URLs (accessible from Windows):"
echo "     Control Plane -> http://localhost:3001"
echo "     API Docs      -> http://localhost:8000/docs"
echo "     Grafana       -> http://localhost:3000"
echo ""
echo "  Quick Start Demo (Copy-Paste to PowerShell):"
echo "     Invoke-RestMethod -Method Post -Uri \"http://${WSL_HOST_IP}:8000/pipeline/trigger\" -ContentType \"application/json\" -Body '{\"firmware_path\": \"v1.0.0\", \"firmware_image\": \"ubuntu:22.04\"}'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo " Open a second terminal for the dashboard:"
echo "   cd ~/ai-embedded-devops && source venv/bin/activate"
echo "   streamlit run dashboard/app.py --server.port 8501"
echo ""
echo " Starting API..."
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 --no-access-log
