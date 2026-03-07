# lab_ping

Lightweight system info gatherer for home lab inventory. Runs on each server or Raspberry Pi and exposes hardware/software information via a simple HTTP endpoint or CLI.

**Zero dependencies** - Python 3 stdlib only.

## Quick Start

```bash
# One-shot dump to stdout
python3 lab_ping.py

# Run as HTTP server (default port 7442)
python3 lab_ping.py serve

# Custom port
python3 lab_ping.py serve -p 9000
```

## Install as Service

```bash
sudo ./install.sh
# or set a custom port:
LAB_PING_PORT=9000 sudo ./install.sh
```

This installs a systemd service that starts on boot and serves on port 7442 (default).

## Endpoints

| Path | Description |
|------|-------------|
| `GET /` or `GET /ping` | Full system info JSON |
| `GET /health` | Simple health check |

## What It Reports

- **hostname** - machine name
- **os** - distro, kernel, architecture
- **cpu** - model, cores, temperature, board model (Raspberry Pi)
- **memory** - total, available, swap
- **disks** - filesystems, usage
- **network** - interfaces, IPs, MACs, link state
- **uptime** - seconds, human-readable
- **load** - 1/5/15 min averages
- **services** - custom service descriptors, Docker containers, systemd units

## Registering Custom Services

Drop JSON files in `/etc/lab_ping/services.d/` to describe services running on the host:

```json
{
    "name": "sensor-api",
    "port": 8080,
    "description": "REST API for sensor data",
    "repo": "https://github.com/user/sensor-api",
    "health_endpoint": "/health"
}
```

These appear in the `services` array of the ping response, making it easy for a central inventory system to know what each machine runs.

## Example Response

```json
{
  "lab_ping_version": "0.1.0",
  "timestamp": "2026-03-07T14:30:00-0500",
  "hostname": "pi-sensor-01",
  "os": {
    "system": "Linux",
    "release": "6.1.0-rpi7-rpi-v8",
    "arch": "aarch64",
    "distro": "Debian GNU/Linux 12 (bookworm)"
  },
  "cpu": {
    "cores_logical": 4,
    "model": "Cortex-A76",
    "board_model": "Raspberry Pi 5 Model B Rev 1.0",
    "temp_celsius": 42.3
  },
  "memory": {
    "total_kb": 8048576,
    "available_kb": 6201344
  },
  "disks": [ ... ],
  "network": [ ... ],
  "uptime": { "seconds": 432000, "days": 5, "human": "5d 0h 0m" },
  "load": { "1min": 0.12, "5min": 0.08, "15min": 0.05 },
  "services": [ ... ]
}
```

## Querying from a Central System

```bash
# Ping a single host
curl -s http://pi-sensor-01:7442/ping | python3 -m json.tool

# Scan all lab hosts
for host in pi-01 pi-02 server-01 server-02; do
  echo "=== $host ==="
  curl -s --connect-timeout 2 "http://${host}:7442/ping" | python3 -m json.tool
done
```
