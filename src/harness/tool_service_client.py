"""Agent-side MCP tool client.

This module is intentionally network-only: swarm/harness code must not import
MCP server implementations from src.mcp. Production tool access goes through the
configured MCP endpoint.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastmcp import Client
from loguru import logger


ROLE_NAMESPACE_POLICY = {
    "professor": {"websearch", "rag", "sandbox"},
    "assistant": {"assistant_knowledge", "rag"},
    "admin": {"websearch", "rag", "assistant_knowledge", "sandbox"},
}


def run_async(coro):
    """Run an async MCP client operation from sync agent code."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            def run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(run_in_new_loop).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class MCPNetworkToolClient:
    """Synchronous facade over the remote MCP microservice."""

    def __init__(self, *, endpoint: str, user_id: Optional[str] = None, role: str = "student", timeout: float = 30.0):
        if not endpoint:
            raise ValueError("tool.mcp.endpoint is required for agent-side MCP network calls")
        self.endpoint = endpoint
        self.user_id = user_id
        self.role = role
        self.timeout = timeout
        self.agent_type = {"professor": 1, "assistant": 2, "admin": 3}.get(role, 0)
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

    def list_tools(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        if use_cache and self._tools_cache is not None:
            return self._tools_cache

        async def _list_tools():
            async with Client(self.endpoint, timeout=self.timeout) as client:
                tools = await client.list_tools()
                return [self._tool_to_dict(tool) for tool in tools]

        tools = [tool for tool in run_async(_list_tools()) if self._can_use_tool(tool.get("name", ""))]
        self._tools_cache = tools
        logger.info(f"[MCPNetworkToolClient] loaded tools from endpoint: {[tool.get('name', '') for tool in tools]}")
        return tools

    get_tools = list_tools

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if not self._can_use_tool(tool_name):
            return f"错误：当前角色 '{self.role}' 无权使用工具 '{tool_name}'"
        payload = self._inject_user_id(tool_name, arguments)

        async def _call_tool():
            async with Client(self.endpoint, timeout=self.timeout) as client:
                return await client.call_tool(tool_name, payload)

        try:
            return self._result_to_text(run_async(_call_tool()))
        except Exception as exc:  # network/service failures are surfaced as tool output for agent synthesis
            logger.error(f"[MCPNetworkToolClient] tool call failed: {tool_name}: {exc}")
            return f"工具调用失败：{exc}"

    def _can_use_tool(self, tool_name: str) -> bool:
        namespaces = ROLE_NAMESPACE_POLICY.get(self.role, set())
        if not namespaces:
            return False
        return any(tool_name == namespace or tool_name.startswith(f"{namespace}_") for namespace in namespaces)

    def _inject_user_id(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(arguments or {})
        if self.user_id and any(namespace in tool_name for namespace in ("rag", "assistant_knowledge", "sandbox")):
            payload.setdefault("user_id", self.user_id)
        return payload

    def _tool_to_dict(self, tool) -> Dict[str, Any]:
        if hasattr(tool, "model_dump"):
            return tool.model_dump()
        if hasattr(tool, "dict"):
            return tool.dict()
        return {
            "name": getattr(tool, "name", ""),
            "description": getattr(tool, "description", ""),
            "inputSchema": getattr(tool, "inputSchema", {}),
        }

    def _result_to_text(self, result) -> str:
        if isinstance(result, list) and result:
            first = result[0]
            if hasattr(first, "text"):
                return first.text
            if isinstance(first, dict) and "text" in first:
                return str(first["text"])
        return str(result)
