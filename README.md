# fmcaid

A thin Python client for Cisco Firepower Management Center (FMC) REST API, with an optional MCP adapter for AI-driven management.

**"aid" on the surface, "FMC AI daemon" if you look closer.**

## What It Does

Handles the hard parts of FMC API interaction — authentication, token lifecycle, domain resolution, self-signed certs — so AI (or your scripts) can focus on the REST.

The optional MCP adapter exposes 6 generic tools (connect, get, post, put, delete, deploy) instead of 665+ endpoint-specific ones. AI figures out the paths.

## Installation

### PyPI

```bash
pip install fmcaid
```

### From Source

```bash
git clone https://github.com/daxm/fmcmcp.git
cd fmcmcp
pip install -e .
```

### Docker

```bash
git clone https://github.com/daxm/fmcmcp.git
cd fmcmcp
docker build -t fmcaid .
```

## Usage

### As a Python Library

```python
from fmcaid import FMCClient

# Context manager (recommended)
with FMCClient("fmc.example.com", "admin", "password") as fmc:
    networks = fmc.get("object/networks")
    fmc.post("object/networks", json={
        "name": "MyNetwork",
        "value": "10.5.0.0/16",
        "type": "Network",
    })
    fmc.deploy()

# Or explicitly
fmc = FMCClient("fmc.example.com", "admin", "password")
fmc.connect()
result = fmc.get("object/networks")
fmc.close()
```

Credentials fall back to environment variables (`FMC_HOST`, `FMC_USERNAME`, `FMC_PASSWORD`, `FMC_DOMAIN`, `FMC_VERIFY_SSL`), then Cisco defaults.

### Via Docker (no local Python needed)

The Docker image works as a self-contained Python runtime with all dependencies pre-installed. Mount your script and pass credentials via env vars:

```bash
# Create a script (e.g. test_fmc.py)
cat <<'EOF' > test_fmc.py
from fmcaid import FMCClient

with FMCClient() as fmc:
    info = fmc.get_server_version()
    print(info)
    networks = fmc.get("object/networks")
    print(networks)
EOF

# Run it in the container
docker run --rm --env-file .env -v ./test_fmc.py:/app/test_fmc.py fmcaid /app/test_fmc.py
```

Note: when using env vars for credentials, `FMCClient()` with no arguments picks them up automatically.

### As an MCP Server (for Claude)

#### Claude Desktop Config

```json
{
  "mcpServers": {
    "fmc-server": {
      "command": "fmcaid",
      "env": {
        "FMC_HOST": "fmc.example.com",
        "FMC_USERNAME": "apiuser",
        "FMC_PASSWORD": "SecurePassword",
        "FMC_DOMAIN": "Global",
        "FMC_VERIFY_SSL": "false"
      }
    }
  }
}
```

#### Docker

```json
{
  "mcpServers": {
    "fmc-server": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "fmcaid"],
      "env": {
        "FMC_HOST": "fmc.example.com",
        "FMC_USERNAME": "apiuser",
        "FMC_PASSWORD": "SecurePassword",
        "FMC_DOMAIN": "Global",
        "FMC_VERIFY_SSL": "false"
      }
    }
  }
}
```

Restart Claude Desktop (quit from system tray, not just close window), then try:
- "Test my FMC connection"
- "List all network objects"
- "Create a network object for 10.5.0.0/16"
- "Deploy changes to devices"

### MCP Tools

| Tool | Description |
|------|-------------|
| `fmc_connect` | Test connection, return FMC version/domain info |
| `fmc_get` | GET any FMC API path |
| `fmc_post` | POST to any FMC API path |
| `fmc_put` | PUT to any FMC API path |
| `fmc_delete` | DELETE on any FMC API path |
| `fmc_deploy` | Trigger deployment to devices |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FMC_HOST` | `192.168.45.45` | FMC hostname or IP |
| `FMC_USERNAME` | `admin` | FMC username |
| `FMC_PASSWORD` | `Admin123` | FMC password |
| `FMC_DOMAIN` | `Global` | FMC domain name |
| `FMC_VERIFY_SSL` | `false` | Verify SSL certificates |

## Requirements

- Python 3.11+
- FMC 6.4+ (first version with REST API/OpenAPI support)
- Network access to FMC on HTTPS (443)

## Troubleshooting

**Authentication failed (401):** Check credentials, verify user has API permissions, confirm FMC is reachable.

**GUI session logged out:** FMC doesn't allow the same user on API and GUI simultaneously. Use a dedicated API user account.

**Domain not found:** Domain names are case-sensitive. Try "Global".

## License

MIT License - see [LICENSE](LICENSE) for details.

Copyright (c) 2025 Dax Mickelson
