"""MCP service application assembly."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, Tuple

from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.routing import Route

from .tools.assistant_knowledge import assistant_knowledge_mcp
from .tools.rag import rag_server
from .tools.sandbox import sandbox_mcp
from .tools.websearch import websearch_mcp


MCP_SERVICE_NAME = "SamFin MCP Tool Service"
MCP_TOOL_MOUNTS: Tuple[Tuple[str, FastMCP], ...] = (
    ("websearch", websearch_mcp),
    ("rag", rag_server),
    ("assistant_knowledge", assistant_knowledge_mcp),
    ("sandbox", sandbox_mcp),
)


def create_mcp_service(name: str = MCP_SERVICE_NAME) -> FastMCP:
    """Create an unmounted MCP service instance."""
    return FastMCP(name=name)


def setup_mcp_service(mcp: FastMCP) -> FastMCP:
    """Mount all configured tool namespaces once."""
    mounted = getattr(mcp, "_samfin_mounted_namespaces", None)
    if mounted is None:
        mounted = set()
        setattr(mcp, "_samfin_mounted_namespaces", mounted)

    for namespace, tool_server in MCP_TOOL_MOUNTS:
        if namespace in mounted:
            continue
        mcp.mount(tool_server, namespace=namespace)
        mounted.add(namespace)
    return mcp


@lru_cache(maxsize=1)
def get_mcp() -> FastMCP:
    """Return the process-wide MCP service singleton."""
    return setup_mcp_service(create_mcp_service())


async def setup() -> FastMCP:
    """Compatibility setup hook for existing local clients."""
    return setup_mcp_service(get_mcp())


def mounted_namespaces(mcp: FastMCP) -> Iterable[str]:
    """Return namespaces mounted by this service assembler."""
    return tuple(getattr(mcp, "_samfin_mounted_namespaces", set()))


def create_asgi_app(path: str = "/sse", health_path: str = "/health", transport: str = "sse"):
    """Create an ASGI app for the MCP service with a health endpoint."""
    mcp = get_mcp()
    app = mcp.http_app(path=path, transport=transport)

    async def health(_request):
        payload: Dict[str, object] = {
            "status": "ok",
            "service": MCP_SERVICE_NAME,
            "transport": transport,
            "mcp_path": path,
            "namespaces": sorted(mounted_namespaces(mcp)),
        }
        return JSONResponse(payload)

    app.routes.append(Route(health_path, health, methods=["GET"]))
    return app


main_mcp: FastMCP = get_mcp()
