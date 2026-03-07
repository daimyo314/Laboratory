#!/usr/bin/env python3
"""
lab_ping - Lightweight system info gatherer for home lab inventory.

Runs on each server/Raspberry Pi and exposes system information via a simple
HTTP endpoint or CLI output. Designed to be queried by a central lab AI or
any automation tool to maintain a smart inventory.

No external dependencies - stdlib only.
"""

import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

VERSION = "0.1.0"
DEFAULT_PORT = 7442
SERVICES_DIR = "/etc/lab_ping/services.d"


# ---------------------------------------------------------------------------
# System info collectors
# ---------------------------------------------------------------------------

def _read_file(path, default=""):
    try:
        return Path(path).read_text().strip()
    except (OSError, PermissionError):
        return default


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip()
    except Exception:
        return ""


def get_hostname():
    return socket.gethostname()


def get_os_info():
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "arch": platform.machine(),
    }
    # Distro info from os-release
    os_release = _read_file("/etc/os-release")
    if os_release:
        for line in os_release.splitlines():
            if line.startswith("PRETTY_NAME="):
                info["distro"] = line.split("=", 1)[1].strip('"')
            elif line.startswith("ID="):
                info["distro_id"] = line.split("=", 1)[1].strip('"')
            elif line.startswith("VERSION_ID="):
                info["distro_version"] = line.split("=", 1)[1].strip('"')
    return info


def get_cpu_info():
    info = {"cores_logical": os.cpu_count()}

    cpuinfo = _read_file("/proc/cpuinfo")
    if cpuinfo:
        models = re.findall(r"model name\s*:\s*(.+)", cpuinfo)
        if models:
            info["model"] = models[0].strip()
        # Physical cores (count unique core ids per physical id)
        physical_ids = set(re.findall(r"physical id\s*:\s*(\d+)", cpuinfo))
        core_ids = re.findall(r"core id\s*:\s*(\d+)", cpuinfo)
        if physical_ids:
            info["sockets"] = len(physical_ids)
        if core_ids:
            info["cores_physical"] = len(set(core_ids))

    # For Raspberry Pi / ARM - check device-tree model
    dt_model = _read_file("/proc/device-tree/model")
    if dt_model:
        info["board_model"] = dt_model.rstrip("\x00")

    # CPU temperature
    temp = _read_file("/sys/class/thermal/thermal_zone0/temp")
    if temp:
        try:
            info["temp_celsius"] = round(int(temp) / 1000, 1)
        except ValueError:
            pass

    return info


def get_memory_info():
    meminfo = _read_file("/proc/meminfo")
    info = {}
    if meminfo:
        for key, label in [
            ("MemTotal", "total_kb"),
            ("MemAvailable", "available_kb"),
            ("SwapTotal", "swap_total_kb"),
            ("SwapFree", "swap_free_kb"),
        ]:
            m = re.search(rf"^{key}:\s+(\d+)", meminfo, re.MULTILINE)
            if m:
                info[label] = int(m.group(1))
    return info


def get_disk_info():
    disks = []
    try:
        output = _run("df -BK --output=source,fstype,size,used,avail,pcent,target -x tmpfs -x devtmpfs -x squashfs 2>/dev/null")
        if output:
            lines = output.strip().splitlines()[1:]  # skip header
            for line in lines:
                parts = line.split()
                if len(parts) >= 7:
                    disks.append({
                        "device": parts[0],
                        "fstype": parts[1],
                        "size_kb": int(parts[2].rstrip("K")),
                        "used_kb": int(parts[3].rstrip("K")),
                        "avail_kb": int(parts[4].rstrip("K")),
                        "use_pct": parts[5],
                        "mount": parts[6],
                    })
    except Exception:
        pass
    return disks


def get_network_info():
    interfaces = []
    try:
        output = _run("ip -j addr show 2>/dev/null")
        if output:
            for iface in json.loads(output):
                if iface.get("ifname") == "lo":
                    continue
                entry = {
                    "name": iface.get("ifname"),
                    "state": iface.get("operstate", "").lower(),
                    "mac": iface.get("address"),
                    "addresses": [],
                }
                for addr in iface.get("addr_info", []):
                    entry["addresses"].append({
                        "family": addr.get("family"),
                        "addr": addr.get("local"),
                        "prefix": addr.get("prefixlen"),
                    })
                interfaces.append(entry)
    except Exception:
        pass
    return interfaces


def get_uptime():
    raw = _read_file("/proc/uptime")
    if raw:
        try:
            secs = float(raw.split()[0])
            return {
                "seconds": int(secs),
                "days": int(secs // 86400),
                "human": _format_duration(secs),
            }
        except ValueError:
            pass
    return {}


def _format_duration(secs):
    d = int(secs // 86400)
    h = int((secs % 86400) // 3600)
    m = int((secs % 3600) // 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


def get_load():
    raw = _read_file("/proc/loadavg")
    if raw:
        parts = raw.split()
        return {
            "1min": float(parts[0]),
            "5min": float(parts[1]),
            "15min": float(parts[2]),
        }
    return {}


def get_services():
    """
    Reads custom service descriptors from /etc/lab_ping/services.d/*.json

    Each JSON file describes a service running on this host, e.g.:
    {
        "name": "my-api",
        "port": 8080,
        "description": "REST API for sensor data",
        "repo": "https://github.com/user/my-api",
        "health_endpoint": "/health"
    }
    """
    services = []
    services_path = Path(SERVICES_DIR)
    if services_path.is_dir():
        for f in sorted(services_path.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                if isinstance(data, dict):
                    services.append(data)
                elif isinstance(data, list):
                    services.extend(data)
            except (json.JSONDecodeError, OSError):
                services.append({"file": f.name, "error": "invalid json"})

    # Also detect docker containers if docker is available
    docker_ps = _run("docker ps --format '{{json .}}' 2>/dev/null")
    if docker_ps:
        containers = []
        for line in docker_ps.splitlines():
            try:
                c = json.loads(line)
                containers.append({
                    "name": c.get("Names", ""),
                    "image": c.get("Image", ""),
                    "status": c.get("Status", ""),
                    "ports": c.get("Ports", ""),
                })
            except json.JSONDecodeError:
                pass
        if containers:
            services.append({
                "name": "docker",
                "type": "container_runtime",
                "containers": containers,
            })

    # Detect systemd custom services (user-defined, not system)
    systemd_units = _run(
        "systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null"
    )
    if systemd_units:
        running_services = []
        for line in systemd_units.splitlines():
            parts = line.split()
            if parts:
                unit = parts[0]
                # Filter to likely user/lab services, skip system noise
                if not any(unit.startswith(p) for p in (
                    "systemd-", "dbus", "ssh", "cron", "getty", "user@",
                    "polkit", "rsyslog", "networking", "ModemManager",
                    "NetworkManager", "accounts-daemon", "udisks",
                    "upower", "wpa_supplicant", "avahi",
                )):
                    running_services.append(unit.removesuffix(".service"))
        if running_services:
            services.append({
                "name": "systemd",
                "type": "service_manager",
                "lab_services": running_services,
            })

    return services


# ---------------------------------------------------------------------------
# Assemble full report
# ---------------------------------------------------------------------------

def gather_info():
    return {
        "lab_ping_version": VERSION,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "hostname": get_hostname(),
        "os": get_os_info(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disks": get_disk_info(),
        "network": get_network_info(),
        "uptime": get_uptime(),
        "load": get_load(),
        "services": get_services(),
    }


# ---------------------------------------------------------------------------
# HTTP server mode
# ---------------------------------------------------------------------------

class LabPingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/ping":
            data = gather_info()
            payload = json.dumps(data, indent=2)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload.encode())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        # Quiet logging - only errors
        pass


def serve(port=DEFAULT_PORT, bind="0.0.0.0"):
    server = HTTPServer((bind, port), LabPingHandler)
    print(f"lab_ping v{VERSION} serving on {bind}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="lab_ping - Home lab system info gatherer"
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="dump",
        choices=["dump", "serve"],
        help="'dump' prints info to stdout (default), 'serve' starts HTTP server",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"HTTP port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "-b", "--bind",
        default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON output (no indentation)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"lab_ping {VERSION}",
    )
    args = parser.parse_args()

    if args.mode == "serve":
        serve(port=args.port, bind=args.bind)
    else:
        data = gather_info()
        indent = None if args.compact else 2
        print(json.dumps(data, indent=indent))


if __name__ == "__main__":
    main()
