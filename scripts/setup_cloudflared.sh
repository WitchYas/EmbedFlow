#!/usr/bin/env bash
set -euo pipefail

TUNNEL_NAME="${1:-ai-embedded-devops}"
HOSTNAME="${2:-}" # e.g. api.example.com

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Installing cloudflared..."
  tmp_pkg="/tmp/cloudflared.deb"
  curl -L -o "$tmp_pkg" \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
  sudo dpkg -i "$tmp_pkg"
fi

if [ ! -f "$HOME/.cloudflared/cert.pem" ]; then
  echo "Logging in to Cloudflare (browser auth)..."
  cloudflared tunnel login
fi

echo "Creating tunnel: $TUNNEL_NAME"
cloudflared tunnel create "$TUNNEL_NAME" || true

TUNNEL_ID=$(cloudflared tunnel list | awk -v name="$TUNNEL_NAME" '$2==name {print $1; exit}')
if [ -z "$TUNNEL_ID" ]; then
  echo "Could not find tunnel ID for $TUNNEL_NAME"
  exit 1
fi

CONFIG_DIR="$HOME/.cloudflared"
CONFIG_FILE="$CONFIG_DIR/config.yml"
CRED_FILE="$CONFIG_DIR/$TUNNEL_ID.json"

cat > "$CONFIG_FILE" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $CRED_FILE

ingress:
  - hostname: ${HOSTNAME:-"<your-subdomain.example.com>"}
    service: http://localhost:8000
  - service: http_status:404
EOF

echo "Config written to $CONFIG_FILE"

if [ -n "$HOSTNAME" ]; then
  echo "Creating DNS route for $HOSTNAME"
  cloudflared tunnel route dns "$TUNNEL_NAME" "$HOSTNAME"
  echo "Run: cloudflared tunnel --config $CONFIG_FILE run $TUNNEL_NAME"
else
  echo "Set a hostname in config.yml, then run:"
  echo "  cloudflared tunnel --config $CONFIG_FILE run $TUNNEL_NAME"
fi
