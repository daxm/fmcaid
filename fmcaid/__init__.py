"""fmcaid - Thin FMC client with optional MCP adapter."""

from fmcaid.__version__ import __version__
from fmcaid.client import FMCClient

__all__ = ["FMCClient", "__version__"]
