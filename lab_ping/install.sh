#!/usr/bin/env bash
#
# lab_ping installer
# Installs lab_ping as systemd services on Linux hosts.
# Installs both the JSON HTTP endpoint and the MCP HTTP server.
#
# Usage:
#   curl -sL <your-host>/install.sh | sudo bash
#   # or
#   sudo ./install.sh
#
# Environment variables:
#   LAB_PING_PORT      - HTTP JSON port (default: 7442)
#   LAB_PING_MCP_PORT  - MCP HTTP/SSE port (default: 7443)
#   LAB_PING_NO_MCP    - set to 1 to skip MCP service install
#
set -euo pipefail

INSTALL_DIR="/opt/lab_ping"
SERVICES_DIR="/etc/lab_ping/services.d"
PORT="${LAB_PING_PORT:-7442}"
MCP_PORT="${LAB_PING_MCP_PORT:-7443}"
NO_MCP="${LAB_PING_NO_MCP:-0}"

echo "=== lab_ping installer ==="

# Must be root
if [[ $EUID -ne 0 ]]; then
    echo "Error: run as root (sudo ./install.sh)"
    exit 1
fi

# Check python3
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required"
    exit 1
fi

echo "[1/5] Installing to ${INSTALL_DIR}..."
mkdir -p "$INSTALL_DIR"
cp "$(dirname "$0")/lab_ping.py" "$INSTALL_DIR/lab_ping.py"
chmod +x "$INSTALL_DIR/lab_ping.py"

echo "[2/5] Creating services directory ${SERVICES_DIR}..."
mkdir -p "$SERVICES_DIR"
# Drop an example file if the dir is empty
if [ -z "$(ls -A "$SERVICES_DIR" 2>/dev/null)" ]; then
    cat > "$SERVICES_DIR/example.json.disabled" <<'EXAMPLE'
{
    "name": "my-service",
    "port": 8080,
    "description": "Example service descriptor - rename to .json to activate",
    "repo": "https://github.com/user/my-service",
    "health_endpoint": "/health"
}
EXAMPLE
fi

echo "[3/5] Installing lab_ping HTTP service (port ${PORT})..."
cat > /etc/systemd/system/lab_ping.service <<EOF
[Unit]
Description=lab_ping - Home lab system info service (HTTP)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/lab_ping.py serve --port ${PORT}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Minimal sandboxing
NoNewPrivileges=true
ProtectSystem=strict
ReadOnlyPaths=/
ReadWritePaths=/tmp

[Install]
WantedBy=multi-user.target
EOF

if [[ "$NO_MCP" != "1" ]]; then
    echo "[4/5] Installing lab_ping MCP service (port ${MCP_PORT})..."
    cat > /etc/systemd/system/lab_ping_mcp.service <<EOF
[Unit]
Description=lab_ping - Home lab MCP server (HTTP/SSE)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/lab_ping.py mcp-sse --port ${MCP_PORT}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Minimal sandboxing
NoNewPrivileges=true
ProtectSystem=strict
ReadOnlyPaths=/
ReadWritePaths=/tmp

[Install]
WantedBy=multi-user.target
EOF
else
    echo "[4/5] Skipping MCP service (LAB_PING_NO_MCP=1)..."
fi

echo "[5/5] Enabling and starting services..."
systemctl daemon-reload

systemctl enable lab_ping.service
systemctl restart lab_ping.service

if [[ "$NO_MCP" != "1" ]]; then
    systemctl enable lab_ping_mcp.service
    systemctl restart lab_ping_mcp.service
fi

systemctl --no-pager status lab_ping.service || true
if [[ "$NO_MCP" != "1" ]]; then
    systemctl --no-pager status lab_ping_mcp.service || true
fi

echo ""
echo "Done! lab_ping is running:"
echo "  HTTP JSON:  http://localhost:${PORT}/ping"
if [[ "$NO_MCP" != "1" ]]; then
    echo "  MCP (SSE):  http://localhost:${MCP_PORT}/mcp"
fi
echo ""
echo "  Logs:  journalctl -u lab_ping -f"
if [[ "$NO_MCP" != "1" ]]; then
    echo "         journalctl -u lab_ping_mcp -f"
fi
echo ""
echo "To register custom services, drop JSON files in:"
echo "  ${SERVICES_DIR}/"
echo ""
echo "MCP stdio mode (e.g. over SSH):"
echo "  ssh user@host python3 ${INSTALL_DIR}/lab_ping.py mcp"
