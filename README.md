# fmcaid

A thin Python client for Cisco Firepower Management Center (FMC) REST API, with an optional MCP adapter for AI-driven management.

**"aid" on the surface, "FMC AI daemon" if you look closer.**

## What It Does

Handles the hard parts of FMC API interaction — authentication, token lifecycle, domain resolution, self-signed certs — so AI (or your scripts) can focus on the REST.

The optional MCP adapter exposes 6 generic tools (connect, get, post, put, delete, deploy) instead of 665+ endpoint-specific ones. AI figures out the paths.

## Installation

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

The MCP adapter lets Claude (or any MCP client) interact with FMC conversationally. There are several ways to configure it depending on your setup.

#### Claude Code (CLI)

Use `claude mcp add` to register the server. If running via Docker, you must pass `-e VAR` flags on the `docker run` command to forward environment variables into the container — Docker does not automatically inherit them from the host process.

```bash
claude mcp add fmc-server \
  -e FMC_HOST=fmc.example.com \
  -e FMC_USERNAME=apiuser \
  -e FMC_PASSWORD=SecurePassword \
  -e FMC_DOMAIN=Global \
  -e FMC_VERIFY_SSL=false \
  -- docker run --rm -i \
  -e FMC_HOST -e FMC_USERNAME -e FMC_PASSWORD -e FMC_DOMAIN -e FMC_VERIFY_SSL \
  fmcaid
```

The first set of `-e KEY=VALUE` flags (before `--`) tells Claude Code to set those env vars when spawning the process. The second set of `-e KEY` flags (after `--`, on the `docker run` command) tells Docker to forward those env vars from its own environment into the container. Both are required.

If installed locally (not Docker), it's simpler:

```bash
claude mcp add fmc-server \
  -e FMC_HOST=fmc.example.com \
  -e FMC_USERNAME=apiuser \
  -e FMC_PASSWORD=SecurePassword \
  -e FMC_DOMAIN=Global \
  -e FMC_VERIFY_SSL=false \
  -- python -m fmcaid
```

Verify the server is reachable:

```bash
claude mcp list
```

Then start `claude` and try: "Test my FMC connection"

#### Claude Desktop (GUI)

For a local (non-Docker) install, add to your Claude Desktop config (`claude_desktop_config.json`):

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

For Docker, add `-e` passthrough flags in the args:

```json
{
  "mcpServers": {
    "fmc-server": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "FMC_HOST",
        "-e", "FMC_USERNAME",
        "-e", "FMC_PASSWORD",
        "-e", "FMC_DOMAIN",
        "-e", "FMC_VERIFY_SSL",
        "fmcaid"
      ],
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

### MCP server shows "Failed to connect" in `claude mcp list`

**Docker env vars not reaching the container:** Claude Code sets env vars on the host `docker` process, but Docker does not automatically forward them into the container. You must include `-e VAR` (without a value) flags on the `docker run` command for each variable. See the Claude Code setup section above.

**Passwords with special characters:** If your password contains `\`, `{`, `}`, `$`, or other shell-sensitive characters, wrap the `-e` value in single quotes: `-e 'FMC_PASSWORD=my}weird\pass'`

### Tools hang or timeout when called

**Using default credentials (192.168.45.45):** If the tool tries to contact `192.168.45.45` instead of your FMC, the environment variables aren't making it into the container. See the Docker env var note above.

### Authentication failed (401)

Check credentials (case-sensitive), verify the user has REST API permissions in FMC, and confirm FMC is reachable from the machine (or container) running fmcaid.

### GUI session logged out

FMC doesn't allow the same user on the API and GUI simultaneously. When both use the same account, one session gets terminated. Use a dedicated API user account for fmcaid.

### Domain not found

Domain names are case-sensitive. The default is `Global`. Check available domains in FMC under System > Domains.

### Docker image changes not taking effect

After pulling code changes, you must rebuild the Docker image:

```bash
git pull
docker build -t fmcaid .
```

## License

MIT License - see [LICENSE](LICENSE) for details.

Copyright (c) 2025 Dax Mickelson
