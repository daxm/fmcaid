# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

**fmcaid** — a thin, synchronous Python client for Cisco FMC REST API with an optional MCP (Model Context Protocol) adapter.

- **Core:** `FMCClient` — sync HTTP client using `requests`. Handles auth, token lifecycle, domain UUID resolution, self-signed certs.
- **Optional:** MCP adapter exposes 6 generic tools (connect, get, post, put, delete, deploy) over stdio for AI assistants.

## Architecture

```
fmcaid/
├── __init__.py          # Exports FMCClient + version
├── __main__.py          # Entry point: python -m fmcaid (starts MCP server)
├── __version__.py       # Version: 0.YYYYMMDD.N
├── client.py            # FMCClient - thin sync HTTP client
└── mcp_server.py        # MCP adapter with 6 generic tools
```

### FMCClient (`client.py`)

Synchronous client using `requests`. Key features:
- Auth via Basic Auth to `/api/fmc_platform/v1/auth/generatetoken`
- Token refresh (30-min expiry, max 3 refreshes, then re-auth)
- Domain UUID parsed from `DOMAINS` response header
- Generic `request(method, path, params, json)` + convenience wrappers
- `get_api_spec()` fetches OpenAPI spec from FMC
- `deploy()` triggers deployment to managed devices
- Context manager and plain library usage patterns
- Credentials from constructor args, env vars, or Cisco defaults (in that order)

### MCP Adapter (`mcp_server.py`)

6 tools exposed over MCP stdio:
1. `fmc_connect` — test connection, return version info
2. `fmc_get` — GET any API path
3. `fmc_post` — POST with JSON body
4. `fmc_put` — PUT with JSON body
5. `fmc_delete` — DELETE by path
6. `fmc_deploy` — trigger deployment

Sync client calls wrapped with `asyncio.to_thread()` for MCP's async requirement.
Client instance created at startup from env vars.

### Authentication Flow
```
Credentials from env vars (FMC_HOST, FMC_USERNAME, FMC_PASSWORD, FMC_DOMAIN, FMC_VERIFY_SSL)
    ↓
FMCClient.connect() → POST /auth/generatetoken with Basic Auth
    ↓
Parse tokens + domain UUID from response headers
    ↓
Auto-refresh before expiry (< 5 min remaining)
    ↓
After 3 refreshes → full re-authentication
```

## API Path Convention

- Relative paths (e.g., `object/networks`) are prefixed with `/api/fmc_config/v1/domain/{uuid}/`
- Absolute paths starting with `/api/` are used as-is
- AI figures out which paths to call (FMC API Explorer or `get_api_spec()` for reference)

## Dependencies

- `requests` — sync HTTP client
- `urllib3` — SSL warning suppression
- `mcp` — MCP SDK (for the adapter only)

## Commands

```bash
# Install (editable)
pip install -e .

# Run MCP server
python -m fmcaid
# or
fmcaid

# Docker build
docker build -t fmcaid .

# Docker run
docker run --rm -i --env-file .env fmcaid
```

## Code Standards

- Synchronous code in `client.py` (no async)
- Type hints on all function signatures
- Context managers for connections
- Errors: raise `Exception` with descriptive messages
- MCP adapter: return plain text or formatted JSON to AI
- Logs to stderr (stdout reserved for MCP protocol)

## Adding Custom Tools

Add new tools to the `TOOLS` list in `mcp_server.py` and handle them in `_handle_tool()`. Use `FMCClient` methods for API calls. Keep tool count minimal — AI composes complex operations from generic primitives.

## FMC API Reference

- **Token lifetime:** 30 minutes, max 3 refreshes
- **Rate limit:** 120 req/min, 10 simultaneous connections per IP
- **Payload limit:** 20,480 bytes
- **API Explorer:** `https://<fmc>/api/api-explorer`
- **OpenAPI Spec:** `https://<fmc>/api/api-explorer/openapi.json`

## Common Issues

- **Same user on GUI + API:** FMC logs out one session. Use a dedicated API user.
- **Domain not found:** Case-sensitive. Try "Global".
- **Self-signed certs:** Set `FMC_VERIFY_SSL=false` (default).

## Publishing to PyPI

```bash
# Update version in fmcaid/__version__.py (format: 0.YYYYMMDD.N)
poetry build
poetry publish
git tag v0.YYYYMMDD.N
git push origin v0.YYYYMMDD.N
```

## License

MIT License. Copyright (c) 2025 Dax Mickelson.
