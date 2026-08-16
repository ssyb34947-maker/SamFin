"""
MCP Client 模块
用于连接和调用 MCP Server 的工具
支持用户隔离和角色权限控制
"""

import asyncio
from typing import Any, Dict, List, Optional
from fastmcp import Client
from src.mcp import main_mcp
from loguru import logger


class MCPClient:
    """
    MCP Client 客户端类

    功能：
    - 连接到 MCP Server
    - 列出所有可用工具（根据角色过滤）
    - 调用指定工具并返回结果
    - 自动注入 user_id 到 RAG 工具
    
    用户隔离：
    - 每个 Agent 拥有独立的 MCPClient 实例
    - user_id 绑定在 Client 上，调用工具时自动注入
    - 根据角色返回不同的可用工具列表
    """

    def __init__(
        self,
        mcp_server=None,
        user_id: Optional[str] = None,
        role: str = "student",
        endpoint: Optional[str] = None,
        mode: str = "local",
        timeout: float = 30.0,
    ):
        """
        初始化 MCP Client

        输入：
            mcp_server: FastMCP 服务器实例，默认使用 main_mcp
            user_id: 用户ID，用于数据隔离
            role: 用户角色 (professor/assistant/student)
        输出：无
        """
        self.mode = mode
        self.endpoint = endpoint
        if self.mode == "remote" and not self.endpoint:
            raise ValueError("tool.mcp.endpoint is required when tool.mcp.mode is remote")
        self.mcp_server = mcp_server or main_mcp
        transport = endpoint if mode == "remote" else self.mcp_server
        self.client = Client(transport, timeout=timeout)
        self.user_id = user_id
        self.role = role
        self._tools_cache: Optional[List[Dict]] = None
        
        logger.debug(f"[MCPClient] 创建 Client: user_id={user_id}, role={role}, mode={mode}, endpoint={endpoint}")

    async def connect(self):
        """
        连接到 MCP Server

        输入：无
        输出：bool，是否连接成功
        """
        try:
            await self.client.ping()
            logger.info(f"[MCPClient] user_id={self.user_id} 成功连接到 MCP Server")
            return True
        except Exception as e:
            logger.error(f"[MCPClient] 连接 MCP Server 失败：{e}")
            return False

    def _can_use_tool(self, tool_name: str) -> bool:
        """
        检查工具是否可用

        规则：
        - 只暴露 rag_search 给 LLM，其他 RAG 工具不暴露
        """
        # DEBUG: 打印角色信息
        logger.debug(f"[MCPClient._can_use_tool] 检查工具 '{tool_name}', user_id={self.user_id}, role={self.role}")

        # 只暴露 rag_search 给 LLM（考虑 namespace 前缀，如 rag_rag_search）
        if "rag_search" in tool_name:
            logger.debug(f"[MCPClient._can_use_tool] 工具 '{tool_name}' -> 允许 (rag_search)")
            return True
        if tool_name.startswith("rag_"):
            logger.debug(f"[MCPClient._can_use_tool] 工具 '{tool_name}' -> 拒绝 (rag_ 开头但非 rag_search)")
            return False

        # 非 RAG 工具都可用
        logger.debug(f"[MCPClient._can_use_tool] 工具 '{tool_name}' -> 允许 (非 RAG 工具)")
        return True

    async def list_tools(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        列出当前角色可用的工具

        输入：
            use_cache: 是否使用缓存的工具列表
        输出：
            工具列表，根据角色过滤
        """
        if use_cache and self._tools_cache is not None:
            return self._tools_cache

        try:
            tools = await self.client.list_tools()
            # 将 Pydantic 对象转换为字典
            tools_dict = []
            all_tool_names = []
            for tool in tools:
                if hasattr(tool, 'model_dump'):
                    tool_dict = tool.model_dump()
                elif hasattr(tool, 'dict'):
                    tool_dict = tool.dict()
                else:
                    tool_dict = {
                        'name': tool.name,
                        'description': getattr(tool, 'description', ''),
                        'inputSchema': getattr(tool, 'inputSchema', {})
                    }
                all_tool_names.append(tool_dict.get('name', 'unknown'))
                
                # 根据角色过滤
                if self._can_use_tool(tool_dict['name']):
                    tools_dict.append(tool_dict)
            
            self._tools_cache = tools_dict
            logger.info(f"[MCPClient] 从 MCP Server 读取到 {len(tools)} 个工具: {all_tool_names}")
            logger.info(f"[MCPClient] 过滤后剩余 {len(tools_dict)} 个工具: {[t['name'] for t in tools_dict]}")
            return tools_dict
        except Exception as e:
            logger.error(f"[MCPClient] 获取工具列表失败：{e}")
            return []

    async def call_tool(self, tool_name: str, **kwargs) -> str:
        """
        调用指定的工具

        输入：
            tool_name: 工具名称
            **kwargs: 工具所需的参数
        输出：
            工具执行的结果（字符串形式）
        """
        # 权限检查
        if not self._can_use_tool(tool_name):
            error_msg = f"错误：当前角色 '{self.role}' 无权使用工具 '{tool_name}'"
            logger.warning(f"[MCPClient] {error_msg}")
            return error_msg
        
        # 自动为需要 user_id 的工具注入
        if self.user_id:
            kwargs = kwargs.copy()
            # RAG 工具
            if "rag" in tool_name and ("user_id" not in kwargs or not kwargs["user_id"]):
                kwargs["user_id"] = self.user_id
                logger.debug(f"[MCPClient] 自动注入 user_id={self.user_id} 到工具 {tool_name}")
            # 助教知识库工具
            elif "assistant_knowledge" in tool_name and ("user_id" not in kwargs or not kwargs["user_id"]):
                kwargs["user_id"] = self.user_id
                logger.debug(f"[MCPClient] 自动注入 user_id={self.user_id} 到工具 {tool_name}")
            elif "sandbox" in tool_name and ("user_id" not in kwargs or not kwargs["user_id"]):
                kwargs["user_id"] = self.user_id
                logger.debug(f"[MCPClient] 自动注入 user_id={self.user_id} 到工具 {tool_name}")

        try:
            result = await self.client.call_tool(tool_name, kwargs)

            # 处理返回结果
            if isinstance(result, list) and len(result) > 0:
                # fastmcp 返回的是 list of content blocks
                content = result[0]
                if hasattr(content, 'text'):
                    return content.text
                elif isinstance(content, dict) and 'text' in content:
                    return content['text']
                else:
                    return str(content)
            else:
                return str(result)

        except Exception as e:
            error_msg = f"调用工具 {tool_name} 失败：{e}"
            logger.error(f"[MCPClient] {error_msg}")
            return error_msg

    async def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定工具的详细信息

        输入：
            tool_name: 工具名称
        输出：
            工具信息字典，如果工具不存在或无权限则返回 None
        """
        if not self._can_use_tool(tool_name):
            return None
            
        tools = await self.list_tools()
        for tool in tools:
            if tool.get('name') == tool_name:
                return tool
        return None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        return await self.client.__aexit__(exc_type, exc_val, exc_tb)


def get_mcp_client(
    mcp_server=None,
    user_id: Optional[str] = None,
    role: str = "student",
    endpoint: Optional[str] = None,
    mode: str = "local",
    timeout: float = 30.0,
) -> MCPClient:
    """
    工厂函数：创建 MCP Client 实例
    
    注意：每个 Agent 应该创建独立的 Client 实例，以实现用户隔离

    输入：
        mcp_server: FastMCP 服务器实例，默认使用 main_mcp
        user_id: 用户ID
        role: 用户角色 (professor/assistant/student)
    输出：
        MCPClient 实例
    """
    return MCPClient(mcp_server, user_id=user_id, role=role, endpoint=endpoint, mode=mode, timeout=timeout)


# 示例用法
async def demo():
    """
    演示 MCP Client 的基本用法

    输入：无
    输出：无
    """
    from src.mcp import setup

    # 首先初始化服务器（挂载所有工具）
    await setup()

    # 创建教授客户端（只能使用检索工具）
    async with get_mcp_client(user_id="prof_1", role="professor") as prof_client:
        print("=== 教授角色 ===")
        tools = await prof_client.list_tools()
        print(f"可用工具：{[t['name'] for t in tools]}")

    # 创建助教客户端（可以使用所有 RAG 工具）
    async with get_mcp_client(user_id="assist_1", role="assistant") as assist_client:
        print("\n=== 助教角色 ===")
        tools = await assist_client.list_tools()
        print(f"可用工具：{[t['name'] for t in tools]}")


if __name__ == "__main__":
    asyncio.run(demo())
