"""Entry point for running fmcaid as a module (starts MCP server)."""

import asyncio
from fmcaid.mcp_server import main

if __name__ == "__main__":
    asyncio.run(main())
