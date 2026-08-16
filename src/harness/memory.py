"""
记忆管理模块
负责管理对话历史和上下文记忆
支持滑动窗口机制，只保留最近 n 轮对话
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class Message:
    """
    消息数据类

    功能：存储单条消息
    输入：角色和内容
    输出：消息对象
    """
    role: str  # "system", "user", "assistant"
    content: str


class MemoryManager:
    """
    记忆管理器

    功能：管理对话历史，提供上下文记忆能力
    特点：
    - 滑动窗口机制：只保留最近 max_history 轮对话（用户+助手）
    - 系统消息始终保留
    - 支持从数据库加载历史消息
    
    输入：最大历史轮数（可选，默认10轮）
    输出：提供记忆存储和检索接口
    """

    def __init__(self, max_history: int = 10):
        """
        初始化记忆管理器
        
        Args:
            max_history: 最大保留的对话轮数（一轮 = 用户消息 + 助手回复）
        """
        self.max_history = max_history
        self.messages: List[Message] = []
        logger.debug(f"[MemoryManager] 初始化，最大历史轮数: {max_history}")

    def add_message(self, role: str, content: str, persist: bool = True) -> None:
        """
        添加消息到记忆

        输入：
            role: 角色（system/user/assistant）
            content: 消息内容
            persist: 是否持久化到数据库（从DB加载历史时设为False）
        输出：无
        """
        self.messages.append(Message(role=role, content=content))

        # 应用滑动窗口：只保留最近 max_history 轮对话
        self._apply_sliding_window()

    def _apply_sliding_window(self) -> None:
        """
        应用滑动窗口机制
        
        保留系统消息，只保留最近 max_history 轮对话（用户+助手）
        一轮对话 = 1条用户消息 + 1条助手消息
        """
        # 分离系统消息和对话消息
        system_messages = [m for m in self.messages if m.role == "system"]
        conversation_messages = [m for m in self.messages if m.role != "system"]

        # 计算最大消息数（一轮 = 2条消息）
        max_messages = self.max_history * 2

        # 如果对话消息超过限制，只保留最近的
        if len(conversation_messages) > max_messages:
            # 保留最近的消息
            conversation_messages = conversation_messages[-max_messages:]
            
            # 记录日志
            removed_count = len(self.messages) - len(system_messages) - len(conversation_messages)
            logger.debug(f"[MemoryManager] 滑动窗口触发，丢弃 {removed_count} 条旧消息，"
                        f"保留最近 {len(conversation_messages)} 条对话消息")

        # 重新组合：系统消息 + 对话消息
        self.messages = system_messages + conversation_messages

    def get_messages(self) -> List[Dict[str, str]]:
        """
        获取所有消息（OpenAI 格式）

        输入：无
        输出：消息列表，格式为 [{"role": "user", "content": "..."}, ...]
        """
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def get_conversation_messages(self) -> List[Dict[str, str]]:
        """
        获取对话消息（不包含系统消息）
        
        输入：无
        输出：对话消息列表
        """
        return [{"role": m.role, "content": m.content} for m in self.messages if m.role != "system"]

    def get_history(self) -> List[Message]:
        """
        获取对话历史（包含所有消息）

        输入：无
        输出：消息对象列表
        """
        return self.messages.copy()

    def get_conversation_rounds(self) -> int:
        """
        获取当前对话轮数
        
        输入：无
        输出：对话轮数（一轮 = 用户 + 助手）
        """
        conversation_count = len([m for m in self.messages if m.role != "system"])
        return conversation_count // 2

    def clear(self) -> None:
        """
        清空记忆（保留系统消息）

        输入：无
        输出：无
        """
        system_messages = [m for m in self.messages if m.role == "system"]
        self.messages = system_messages
        logger.debug("[MemoryManager] 记忆已清空（保留系统消息）")

    def set_system_message(self, content: str) -> None:
        """
        设置系统消息

        输入：content - 系统消息内容
        输出：无
        """
        # 移除旧的系统消息
        self.messages = [m for m in self.messages if m.role != "system"]
        # 添加新的系统消息到开头
        self.messages.insert(0, Message(role="system", content=content))
        logger.debug(f"[MemoryManager] 系统消息已设置，长度: {len(content)}")

    def get_system_message(self) -> Optional[str]:
        """
        获取系统消息内容
        
        输入：无
        输出：系统消息内容，如果没有则返回 None
        """
        for m in self.messages:
            if m.role == "system":
                return m.content
        return None

    def __len__(self) -> int:
        """
        返回消息总数
        """
        return len(self.messages)

    def __repr__(self) -> str:
        """
        返回内存状态的字符串表示
        """
        system_count = len([m for m in self.messages if m.role == "system"])
        user_count = len([m for m in self.messages if m.role == "user"])
        assistant_count = len([m for m in self.messages if m.role == "assistant"])
        rounds = self.get_conversation_rounds()
        
        return (f"MemoryManager(messages={len(self.messages)}, "
                f"system={system_count}, user={user_count}, assistant={assistant_count}, "
                f"rounds={rounds}/{self.max_history})")
