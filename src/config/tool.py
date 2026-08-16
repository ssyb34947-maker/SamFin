"""
工具配置数据类
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class WebSearchConfig:
    """
    网页搜索工具配置

    功能：存储网页搜索工具配置
    输入：配置参数
    输出：配置数据类实例
    """
    enabled: bool = False
    api_url: str = ""
    api_key: str = ""


@dataclass
class SandboxToolConfig:
    """Remote sandbox service config for MCP tools."""
    endpoint: str = ""
    timeout: float = 30.0


@dataclass
class MCPServiceConfig:
    """MCP tool service connection config."""
    mode: str = "local"  # local | remote
    endpoint: str = ""
    timeout: float = 30.0
    auto_setup_local: bool = True
    host: str = ""
    port: int = 0
    transport: str = "sse"
    health_path: str = "/health"


@dataclass
class ToolConfig:
    """
    工具配置

    功能：存储所有工具配置
    输入：配置参数
    输出：配置数据类实例
    """
    websearch: WebSearchConfig = field(default_factory=WebSearchConfig)
    sandbox: SandboxToolConfig = field(default_factory=SandboxToolConfig)
    mcp: MCPServiceConfig = field(default_factory=MCPServiceConfig)
