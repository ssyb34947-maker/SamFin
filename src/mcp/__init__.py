"""MCP package exports."""

from .app import (
    MCP_TOOL_MOUNTS,
    create_asgi_app,
    create_mcp_service,
    get_mcp,
    main_mcp,
    mounted_namespaces,
    setup,
    setup_mcp_service,
)
from .tools.websearch import websearch_mcp
from .tools.rag import rag_server
from .tools.assistant_knowledge import assistant_knowledge_mcp
from .tools.sandbox import sandbox_mcp

from .client import MCPClient, get_mcp_client
from .sync_client import SyncMCPClient, get_sync_mcp_client
from .agent_type_manager import (
    AgentTypeMCPManager,
    get_agent_type_mcp_manager,
    AgentType,
    MCPConfig,
)

__all__ = [
    "get_mcp",
    "main_mcp",
    "setup",
    "setup_mcp_service",
    "create_mcp_service",
    "create_asgi_app",
    "mounted_namespaces",
    "MCP_TOOL_MOUNTS",
    "websearch_mcp",
    "rag_server",
    "assistant_knowledge_mcp",
    "sandbox_mcp",
    "MCPClient",
    "get_mcp_client",
    "SyncMCPClient",
    "get_sync_mcp_client",
    "AgentTypeMCPManager",
    "get_agent_type_mcp_manager",
    "AgentType",
    "MCPConfig",
]
