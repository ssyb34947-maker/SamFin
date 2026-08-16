"""
MCP Client 同步版本
提供同步接口，方便在非异步环境中使用
支持用户隔离和角色权限控制
"""

import asyncio
from typing import Any, Dict, List, Optional
from functools import wraps
from src.mcp.client import MCPClient, get_mcp_client
from src.mcp import setup
from loguru import logger


def run_async(coro):
    """
    在同步环境中运行异步函数

    输入：
        coro: 协程对象
    输出：
        协程的返回值
    """
    import inspect
    if inspect.iscoroutine(coro):
        try:
            # 检查是否已经有运行中的事件循环
            loop = asyncio.get_event_loop()
            # 如果事件循环正在运行，在新线程中创建新的事件循环
            if loop.is_running():
                import threading
                import concurrent.futures

                def run_in_new_loop():
                    """在新线程中创建并运行事件循环"""
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_new_loop)
                    return future.result()
            else:
                # 事件循环存在但未运行，直接运行
                return loop.run_until_complete(coro)
        except RuntimeError:
            # 没有事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
    return coro


class SyncMCPClient:
    """
    MCP Client 同步版本

    功能：
    - 提供同步接口封装异步的 MCPClient
    - 自动处理事件循环
    - 支持用户隔离和角色权限控制
    - 每个 Agent 独立的 Client 实例
    """

    def __init__(
        self,
        mcp_server=None,
        user_id: Optional[str] = None,
        role: str = "student",
        endpoint: Optional[str] = None,
        mode: str = "local",
        timeout: float = 30.0,
        auto_setup_local: bool = True,
    ):
        """
        初始化同步 MCP Client

        输入：
            mcp_server: FastMCP 服务器实例，默认使用 main_mcp
            user_id: 用户ID，用于数据隔离
            role: 用户角色 (professor/assistant/student)
        输出：无
        """
        self._async_client: Optional[MCPClient] = None
        self._mcp_server = mcp_server
        self._user_id = user_id
        self._role = role
        self._endpoint = endpoint
        self._mode = mode
        self._timeout = timeout
        self._auto_setup_local = auto_setup_local
        self._initialized = False

        logger.debug(f"[SyncMCPClient] 创建 Client: user_id={user_id}, role={role}, mode={mode}, endpoint={endpoint}")

    def _ensure_initialized(self):
        """确保客户端已初始化"""
        if not self._initialized:
            # local 模式初始化进程内服务器；remote 模式连接独立 MCP 服务。
            if self._mode != "remote" and self._auto_setup_local:
                run_async(setup())
            # 创建异步客户端（每个 SyncMCPClient 有自己的实例）
            self._async_client = get_mcp_client(
                self._mcp_server,
                user_id=self._user_id,
                role=self._role,
                endpoint=self._endpoint,
                mode=self._mode,
                timeout=self._timeout,
            )
            self._initialized = True

    @property
    def user_id(self) -> Optional[str]:
        """获取用户ID"""
        return self._user_id

    @property
    def role(self) -> str:
        """获取角色"""
        return self._role

    def connect(self) -> bool:
        """
        连接到 MCP Server

        输入：无
        输出：
            bool，是否连接成功
        """
        self._ensure_initialized()

        async def _connect():
            async with self._async_client as client:
                return await client.connect()

        return run_async(_connect())

    def list_tools(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        列出当前角色可用的工具

        输入：
            use_cache: 是否使用缓存的工具列表
        输出：
            工具列表（根据角色过滤）
        """
        self._ensure_initialized()

        async def _list_tools():
            async with self._async_client as client:
                return await client.list_tools(use_cache)

        return run_async(_list_tools())

    def call_tool(self, tool_name: str, **kwargs) -> str:
        """
        调用指定的工具

        输入：
            tool_name: 工具名称
            **kwargs: 工具所需的参数
        输出：
            工具执行的结果
        """
        self._ensure_initialized()

        async def _call_tool():
            async with self._async_client as client:
                return await client.call_tool(tool_name, **kwargs)

        return run_async(_call_tool())

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定工具的详细信息

        输入：
            tool_name: 工具名称
        输出：
            工具信息字典
        """
        self._ensure_initialized()

        async def _get_tool_info():
            async with self._async_client as client:
                return await client.get_tool_info(tool_name)

        return run_async(_get_tool_info())


def get_sync_mcp_client(
    mcp_server=None,
    user_id: Optional[str] = None,
    role: str = "student",
    endpoint: Optional[str] = None,
    mode: str = "local",
    timeout: float = 30.0,
    auto_setup_local: bool = True,
) -> SyncMCPClient:
    """
    工厂函数：创建同步 MCP Client 实例
    
    注意：每个 Agent 应该创建独立的 Client 实例，以实现用户隔离

    输入：
        mcp_server: FastMCP 服务器实例
        user_id: 用户ID
        role: 用户角色 (professor/assistant/student)
    输出：
        SyncMCPClient 实例
    """
    return SyncMCPClient(
        mcp_server,
        user_id=user_id,
        role=role,
        endpoint=endpoint,
        mode=mode,
        timeout=timeout,
        auto_setup_local=auto_setup_local,
    )


# 示例用法
def demo():
    """
    演示同步 MCP Client 的基本用法

    输入：无
    输出：无
    """
    # 创建教授客户端（只能检索）
    prof_client = get_sync_mcp_client(user_id="prof_1", role="professor")
    print("=== 教授角色 ===")
    tools = prof_client.list_tools()
    print(f"可用工具：{[t['name'] for t in tools]}")

    # 创建助教客户端（可以增删查）
    assist_client = get_sync_mcp_client(user_id="assist_1", role="assistant")
    print("\n=== 助教角色 ===")
    tools = assist_client.list_tools()
    print(f"可用工具：{[t['name'] for t in tools]}")

    # 创建学生客户端（无 RAG 工具）
    student_client = get_sync_mcp_client(user_id="student_1", role="student")
    print("\n=== 学生角色 ===")
    tools = student_client.list_tools()
    print(f"可用工具：{[t['name'] for t in tools]}")


if __name__ == "__main__":
    demo()
