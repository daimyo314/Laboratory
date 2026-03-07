#!/usr/bin/env bash
#
# lab_ping installer
# Installs lab_ping as a systemd service on Linux hosts.
#
# Usage:
#   curl -sL <your-host>/install.sh | sudo bash
#   # or
#   sudo ./install.sh
#
set -euo pipefail

INSTALL_DIR="/opt/lab_ping"
SERVICES_DIR="/etc/lab_ping/services.d"
UNIT_FILE="/etc/systemd/system/lab_ping.service"
PORT="${LAB_PING_PORT:-7442}"

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

echo "[1/4] Installing to ${INSTALL_DIR}..."
mkdir -p "$INSTALL_DIR"
cp "$(dirname "$0")/lab_ping.py" "$INSTALL_DIR/lab_ping.py"
chmod +x "$INSTALL_DIR/lab_ping.py"

echo "[2/4] Creating services directory ${SERVICES_DIR}..."
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

echo "[3/4] Installing systemd service (port ${PORT})..."
cat > "$UNIT_FILE" <<EOF
[Unit]
Description=lab_ping - Home lab system info service
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

echo "[4/4] Enabling and starting service..."
systemctl daemon-reload
systemctl enable lab_ping.service
systemctl restart lab_ping.service
systemctl --no-pager status lab_ping.service

echo ""
echo "Done! lab_ping is running on port ${PORT}"
echo "  Test:  curl http://localhost:${PORT}/ping"
echo "  Logs:  journalctl -u lab_ping -f"
echo ""
echo "To register custom services, drop JSON files in:"
echo "  ${SERVICES_DIR}/"
