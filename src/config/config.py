"""
配置加载模块
统一加载和管理所有配置
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(".env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from .llm import LLMConfig
from .harness import HarnessConfig
from .tool import (
    ToolConfig, 
    WebSearchConfig, 
    MCPServiceConfig,
    SandboxToolConfig,
)
from .rag import RAGConfig, MilvusConfig
from .embedding import EmbeddingConfig
from .rerank import RerankConfig
from .ocr import OCRConfig
from .swarm import SwarmConfig
from .user_system import JWTConfig, PostgreSQLConfig, RedisConfig, UserSystemConfig


@dataclass
class Config:
    """
    全局配置

    功能：统一管理所有配置
    输入：配置文件路径
    输出：配置实例
    """
    llm: LLMConfig
    harness: HarnessConfig
    tool: ToolConfig
    rag: RAGConfig
    embedding: EmbeddingConfig
    rerank: RerankConfig
    ocr: OCRConfig
    swarm: SwarmConfig
    user_system: UserSystemConfig

    @classmethod
    def from_yaml(cls, config_path: str = "") -> "Config":
        """
        从 YAML 文件加载配置

        输入：config_path - 配置文件路径
        输出：Config 实例
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在：{config_path}")

        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # LLM 配置
        llm_config = LLMConfig(**data["llm"])

        # Harness 配置
        harness_data = data.get("harness", data.get("agent", {}))
        harness_config = HarnessConfig(**harness_data)

        # 工具配置
        websearch_config = WebSearchConfig(**data["tool"]["websearch"])
        
        sandbox_data = data.get("tool", {}).get("sandbox", {})
        sandbox_config = SandboxToolConfig(
            endpoint=os.getenv("SANDBOX_SERVICE_URL", sandbox_data.get("endpoint", "")),
            timeout=sandbox_data.get("timeout", 30.0),
        )
        
        mcp_data = data.get("tool", {}).get("mcp", {})
        mcp_config = MCPServiceConfig(
            mode=mcp_data.get("mode", "local"),
            endpoint=os.getenv("MCP_SERVICE_URL", mcp_data.get("endpoint", "")),
            timeout=mcp_data.get("timeout", 30.0),
            auto_setup_local=mcp_data.get("auto_setup_local", True),
            host=mcp_data.get("host", ""),
            port=mcp_data.get("port", 0),
            transport=mcp_data.get("transport", "sse"),
            health_path=mcp_data.get("health_path", "/health"),
        )

        tool_config = ToolConfig(
            websearch=websearch_config,
            sandbox=sandbox_config,
            mcp=mcp_config,
        )

        # RAG 配置
        rag_data = data.get("rag", {})
        milvus_data = rag_data.get("milvus", {})
        milvus_config = MilvusConfig(**milvus_data)
        rag_config = RAGConfig(
            collection_name=rag_data.get("collection_name", "rag_collection"),
            vector_dim=rag_data.get("vector_dim", 1024),
            chunk_size=rag_data.get("chunk_size", 1024),
            chunk_overlap=rag_data.get("chunk_overlap", 0.1),
            top_k=rag_data.get("top_k", 10),
            milvus=milvus_config
        )

        # Embedding 配置
        embedding_data = data.get("embedding", {})
        embedding_config = EmbeddingConfig(**embedding_data)

        # Rerank 配置
        rerank_data = data.get("rerank", {})
        rerank_config = RerankConfig(**rerank_data)

        # OCR 配置
        ocr_data = data.get("ocr", {})
        ocr_config = OCRConfig(**ocr_data)

        # User system 配置
        user_system_data = data.get("user_system", {})
        redis_data = user_system_data.get("redis", {})
        postgres_data = user_system_data.get("postgres", {})
        jwt_data = user_system_data.get("jwt", {})
        user_system_config = UserSystemConfig(
            enabled=user_system_data.get("enabled", True),
            mode=user_system_data.get("mode", "remote"),
            base_url=os.getenv("USER_SYSTEM_BASE_URL", user_system_data.get("base_url", "")),
            host=user_system_data.get("host", ""),
            port=user_system_data.get("port", 0),
            request_timeout=user_system_data.get("request_timeout", 10.0),
            repository=user_system_data.get("repository", "postgres"),
            jwt=JWTConfig(**jwt_data),
            postgres=PostgreSQLConfig(**postgres_data),
            redis=RedisConfig(**redis_data),
        )

        # Education company 配置（应用层，多 Agent 教学团队）
        swarm_data = data.get("swarm", {})
        swarm_config = SwarmConfig(**swarm_data)

        return cls(
            llm=llm_config,
            harness=harness_config,
            tool=tool_config,
            rag=rag_config,
            embedding=embedding_config,
            rerank=rerank_config,
            ocr=ocr_config,
            swarm=swarm_config,
            user_system=user_system_config
        )


_config_instance = None


def _resolve_config_path(config_path: str) -> str:
    if not config_path or config_path == "config.yaml":
        return os.getenv("CONFIG_PATH", "config/master/config.yaml")
    return config_path


def get_config(config_path: str = "") -> Config:
    """
    获取全局配置实例（单例模式）

    输入：config_path - 配置文件路径
    输出：Config 实例
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config.from_yaml(_resolve_config_path(config_path))
    return _config_instance


def reload_config(config_path: str = "") -> Config:
    """
    重新加载配置

    输入：config_path - 配置文件路径
    输出：Config 实例
    """
    global _config_instance
    _config_instance = Config.from_yaml(_resolve_config_path(config_path))
    return _config_instance
