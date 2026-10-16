"""
MCP (Model Context Protocol) Server for ChemAI
将ChemAI核心功能暴露为MCP工具，供ChemAI Agent调用
"""

from app.mcp.server import router as mcp_router

__all__ = ["mcp_router"]
