"""
Agent 类型 MCP 管理器
根据 Agent 身份（教授/助教/管理员）管理可用的 MCP 工具
"""

from typing import Dict, List, Set, Optional
from enum import IntEnum
from dataclasses import dataclass, field
from loguru import logger


class AgentType(IntEnum):
    """Agent 类型枚举"""
    PROFESSOR = 1  # 教授
    ASSISTANT = 2  # 助教
    ADMIN = 3      # 管理员


@dataclass
class MCPConfig:
    """MCP 配置"""
    name: str
    description: str
    enabled: bool = True
    namespaces: List[str] = field(default_factory=list)


class AgentTypeMCPManager:
    """
    Agent 类型 MCP 管理器
    
    功能：
    - 按 Agent 身份管理可用的 MCP 工具
    - 支持配置驱动的方式定义每个身份有哪些 MCP
    - 提供按身份获取 MCP 列表的接口
    
    使用示例：
        manager = AgentTypeMCPManager()
        # 为教授配置 MCP
        manager.configure_mcp_for_agent_type(
            AgentType.PROFESSOR,
            ["websearch", "rag", "sandbox"]
        )
        # 获取教授可用的 MCP
        professor_mcp = manager.get_mcp_for_agent_type(AgentType.PROFESSOR)
    """
    
    def __init__(self):
        # 每个 Agent 类型对应的 MCP 名称列表
        self._agent_type_mcp_map: Dict[AgentType, Set[str]] = {
            AgentType.PROFESSOR: set(),
            AgentType.ASSISTANT: set(),
            AgentType.ADMIN: set(),
        }
        # MCP 配置信息
        self._mcp_configs: Dict[str, MCPConfig] = {}
        # 是否已初始化
        self._initialized = False
    
    def register_mcp(self, name: str, description: str, 
                     namespaces: Optional[List[str]] = None) -> None:
        """
        注册一个 MCP 工具
        
        输入：
            name: MCP 名称
            description: MCP 描述
            namespaces: 该 MCP 包含的命名空间列表
        """
        self._mcp_configs[name] = MCPConfig(
            name=name,
            description=description,
            namespaces=namespaces or [name]
        )
        logger.debug(f"[AgentTypeMCPManager] 注册 MCP: {name}")
    
    def configure_mcp_for_agent_type(self, agent_type: AgentType, 
                                      mcp_names: List[str]) -> None:
        """
        为指定 Agent 类型配置可用的 MCP
        
        输入：
            agent_type: Agent 类型
            mcp_names: MCP 名称列表
        """
        # 验证所有 MCP 是否已注册
        for name in mcp_names:
            if name not in self._mcp_configs:
                logger.warning(f"[AgentTypeMCPManager] MCP '{name}' 未注册，但已配置给 {agent_type.name}")
        
        self._agent_type_mcp_map[agent_type] = set(mcp_names)
        logger.info(f"[AgentTypeMCPManager] 配置 {agent_type.name} 的 MCP: {mcp_names}")
    
    def get_mcp_for_agent_type(self, agent_type: AgentType) -> List[MCPConfig]:
        """获取指定 Agent 类型可用的 MCP 配置列表"""
        mcp_names = self._agent_type_mcp_map.get(agent_type, set())
        return [
            self._mcp_configs[name]
            for name in mcp_names
            if name in self._mcp_configs and self._mcp_configs[name].enabled
        ]
    
    def get_mcp_names_for_agent_type(self, agent_type: AgentType) -> List[str]:
        """
        获取指定 Agent 类型可用的 MCP 名称列表
        
        输入：
            agent_type: Agent 类型
        输出：
            MCP 名称列表
        """
        return list(self._agent_type_mcp_map.get(agent_type, set()))
    
    def get_namespaces_for_agent_type(self, agent_type: AgentType) -> List[str]:
        """获取指定 Agent 类型可用的所有命名空间"""
        mcp_configs = self.get_mcp_for_agent_type(agent_type)
        namespaces = []
        for config in mcp_configs:
            namespaces.extend(config.namespaces)
        return namespaces
    
    def is_mcp_available_for_agent_type(self, agent_type: AgentType, 
                                         mcp_name: str) -> bool:
        """
        检查指定 MCP 是否对某个 Agent 类型可用
        
        输入：
            agent_type: Agent 类型
            mcp_name: MCP 名称
        输出：
            是否可用
        """
        return mcp_name in self._agent_type_mcp_map.get(agent_type, set())
    
    def initialize_default_config(self) -> None:
        """初始化默认配置"""
        if self._initialized:
            return

        # 注册所有可用的 MCP
        self.register_mcp("websearch", "网络搜索工具", ["websearch"])
        self.register_mcp("rag", "知识库检索工具", ["rag"])
        self.register_mcp("assistant_knowledge", "助教知识库管理工具", ["assistant_knowledge"])
        self.register_mcp("sandbox", "本地 Docker 沙箱计算工具", ["sandbox"])

        # 配置教授 Agent
        self.configure_mcp_for_agent_type(AgentType.PROFESSOR, ["websearch", "rag", "sandbox"])

        # 配置助教 Agent（不包含 sandbox）
        self.configure_mcp_for_agent_type(AgentType.ASSISTANT, ["assistant_knowledge", "rag"])

        # 配置管理员 Agent
        self.configure_mcp_for_agent_type(AgentType.ADMIN, ["websearch", "rag", "assistant_knowledge", "sandbox"])

        self._initialized = True
        logger.info("[MCPManager] 初始化完成")
    
    def get_agent_type_from_int(self, agent_type_int: int) -> AgentType:
        """
        将整数转换为 AgentType
        
        输入：
            agent_type_int: Agent 类型整数 (1, 2, 3)
        输出：
            AgentType 枚举
        """
        try:
            return AgentType(agent_type_int)
        except ValueError:
            logger.warning(f"[AgentTypeMCPManager] 未知的 Agent 类型: {agent_type_int}，默认使用 PROFESSOR")
            return AgentType.PROFESSOR


# 全局单例
_global_agent_type_mcp_manager: Optional[AgentTypeMCPManager] = None


def get_agent_type_mcp_manager() -> AgentTypeMCPManager:
    """
    获取全局 Agent 类型 MCP 管理器单例
    
    输入：无
    输出：
        AgentTypeMCPManager 实例
    """
    global _global_agent_type_mcp_manager
    if _global_agent_type_mcp_manager is None:
        _global_agent_type_mcp_manager = AgentTypeMCPManager()
        _global_agent_type_mcp_manager.initialize_default_config()
    return _global_agent_type_mcp_manager


def reset_agent_type_mcp_manager() -> None:
    """
    重置全局单例（主要用于测试）
    """
    global _global_agent_type_mcp_manager
    _global_agent_type_mcp_manager = None
