# lab_ping

Lightweight system info gatherer for home lab inventory. Runs on each server or Raspberry Pi and exposes hardware/software information via HTTP, CLI, or **MCP** (Model Context Protocol) for direct AI agent access.

**Zero dependencies** - Python 3 stdlib only.

## Quick Start

```bash
# One-shot dump to stdout
python3 lab_ping.py

# Run as HTTP server (default port 7442)
python3 lab_ping.py serve

# Run as MCP stdio server (for SSH-based remote access)
python3 lab_ping.py mcp

# Run as MCP HTTP/SSE server (default port 7443)
python3 lab_ping.py mcp-sse
```

## Install as Service

```bash
sudo ./install.sh
```

This installs two systemd services that start on boot:
- `lab_ping` - HTTP JSON endpoint on port 7442
- `lab_ping_mcp` - MCP HTTP/SSE server on port 7443

Environment variables:
- `LAB_PING_PORT` - HTTP JSON port (default: 7442)
- `LAB_PING_MCP_PORT` - MCP port (default: 7443)
- `LAB_PING_NO_MCP=1` - skip MCP service install

## Modes

| Mode | Command | Transport | Use Case |
|------|---------|-----------|----------|
| `dump` | `lab_ping.py` | stdout | Scripting, cron jobs |
| `serve` | `lab_ping.py serve` | HTTP JSON | curl, monitoring tools |
| `mcp` | `lab_ping.py mcp` | stdio JSON-RPC | MCP over SSH, local agents |
| `mcp-sse` | `lab_ping.py mcp-sse` | HTTP + SSE | Remote MCP clients, Claude |

## MCP Integration

lab_ping implements the [Model Context Protocol](https://modelcontextprotocol.io/) so AI agents (Claude, etc.) can query your lab hosts directly as tool calls.

### MCP Tools Exposed

| Tool | Description |
|------|-------------|
| `get_system_info` | Complete system snapshot (all fields) |
| `get_cpu_info` | CPU model, cores, temperature, board model |
| `get_memory_info` | RAM and swap usage |
| `get_disk_info` | Mounted filesystems and usage |
| `get_network_info` | Interfaces, IPs, MACs, link state |
| `get_services` | Lab services, Docker containers, systemd units |
| `get_uptime_and_load` | Uptime and load averages |

### Connecting via MCP HTTP (Streamable HTTP)

The `mcp-sse` mode runs an HTTP server implementing MCP's Streamable HTTP transport:

```jsonc
// Claude Desktop / MCP client config
{
  "mcpServers": {
    "pi-sensor-01": {
      "transport": "streamable-http",
      "url": "http://pi-sensor-01:7443/mcp"
    },
    "server-rack-01": {
      "transport": "streamable-http",
      "url": "http://server-rack-01:7443/mcp"
    }
  }
}
```

### Connecting via MCP over SSH (stdio)

For hosts without an open MCP port, use SSH as the transport:

```jsonc
// Claude Desktop / MCP client config
{
  "mcpServers": {
    "pi-sensor-01": {
      "command": "ssh",
      "args": ["user@pi-sensor-01", "python3", "/opt/lab_ping/lab_ping.py", "mcp"]
    }
  }
}
```

### Testing MCP manually

```bash
# stdio mode - send JSON-RPC directly
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python3 lab_ping.py mcp

# HTTP mode
curl -X POST http://localhost:7443/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

# After init, list tools
curl -X POST http://localhost:7443/mcp \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: <session-id-from-init>" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Call a tool
curl -X POST http://localhost:7443/mcp \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: <session-id>" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_cpu_info","arguments":{}}}'
```

## HTTP JSON Endpoints

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

These appear in the `services` array of the response and in the `get_services` MCP tool, making it easy for a central inventory system or AI to know what each machine runs.

## Example Response

```json
{
  "lab_ping_version": "0.2.0",
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
