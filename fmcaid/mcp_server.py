"""MCP adapter for FMCClient - exposes 6 generic tools over MCP stdio."""

import asyncio
import json
import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from fmcaid.client import FMCClient

app = Server("fmc-server")

# Shared client instance, created at startup
_client: FMCClient | None = None


def _format_result(data: dict) -> str:
    """Pretty-print JSON response for the AI."""
    return json.dumps(data, indent=2)


# ============================================
# TOOL DEFINITIONS
# ============================================
TOOLS = [
    Tool(
        name="fmc_connect",
        description="Test connection to FMC and return version/domain info. Call this first to verify connectivity.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="fmc_get",
        description=(
            "GET any FMC API path. The path is relative to /api/fmc_config/v1/domain/{domain_uuid}/ "
            "unless it starts with /api/ (absolute). Examples: 'object/networks', 'policy/accesspolicies', "
            "'object/hosts?limit=100'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "API path (e.g. 'object/networks')"},
                "params": {
                    "type": "object",
                    "description": "Optional query parameters (e.g. {\"limit\": 100, \"offset\": 0})",
                    "additionalProperties": True,
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="fmc_post",
        description=(
            "POST to any FMC API path with a JSON body. "
            "Used to create new objects, policies, rules, etc."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "API path (e.g. 'object/networks')"},
                "body": {"type": "object", "description": "JSON body to POST", "additionalProperties": True},
            },
            "required": ["path", "body"],
        },
    ),
    Tool(
        name="fmc_put",
        description=(
            "PUT to any FMC API path with a JSON body. "
            "Used to update existing objects. Must include 'id' in the body."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "API path (e.g. 'object/networks/{id}')"},
                "body": {"type": "object", "description": "JSON body to PUT", "additionalProperties": True},
            },
            "required": ["path", "body"],
        },
    ),
    Tool(
        name="fmc_delete",
        description="DELETE an FMC object by API path.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "API path (e.g. 'object/networks/{id}')"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="fmc_deploy",
        description=(
            "Trigger deployment to FMC-managed devices. "
            "Optionally specify device IDs; otherwise deploys to all devices with pending changes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of device UUIDs to deploy to",
                },
                "force": {
                    "type": "boolean",
                    "description": "Force deploy even if no pending changes",
                    "default": False,
                },
            },
            "required": [],
        },
    ),
]


# ============================================
# MCP HOOKS
# ============================================
@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = await asyncio.to_thread(_handle_tool, name, arguments)
    return [TextContent(type="text", text=result)]


def _handle_tool(name: str, arguments: dict) -> str:
    """Dispatch tool calls to FMCClient (runs in thread)."""
    global _client
    if _client is None:
        return "Error: FMC client not connected. Server failed to initialize."

    try:
        if name == "fmc_connect":
            info = _client.get_server_version()
            items = info.get("items", [])
            if items:
                sv = items[0]
                return (
                    f"Connected to FMC at {_client.host}\n"
                    f"Domain: {_client.domain_name} ({_client.domain_uuid})\n"
                    f"Version: {sv.get('serverVersion', 'Unknown')}\n"
                    f"Build: {sv.get('buildNumber', 'Unknown')}"
                )
            return f"Connected to FMC at {_client.host} (no version info available)"

        elif name == "fmc_get":
            data = _client.get(arguments["path"], params=arguments.get("params"))
            return _format_result(data)

        elif name == "fmc_post":
            data = _client.post(arguments["path"], json=arguments["body"])
            return _format_result(data)

        elif name == "fmc_put":
            data = _client.put(arguments["path"], json=arguments["body"])
            return _format_result(data)

        elif name == "fmc_delete":
            data = _client.delete(arguments["path"])
            return _format_result(data)

        elif name == "fmc_deploy":
            data = _client.deploy(
                device_ids=arguments.get("device_ids"),
                force=arguments.get("force", False),
            )
            return _format_result(data)

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Error: {e}"


# ============================================
# SERVER STARTUP
# ============================================
async def main():
    """Start the MCP server."""
    global _client

    try:
        _client = FMCClient()
        _client.connect()
        print(
            f"Connected to FMC at {_client.host} "
            f"(domain: {_client.domain_name})",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"Failed to connect to FMC: {e}", file=sys.stderr)
        print("Server will start but tools will return errors.", file=sys.stderr)
        _client = None

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
    finally:
        if _client:
            _client.close()
