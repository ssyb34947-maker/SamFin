"""
检索 Schema
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class RetrievalType(str, Enum):
    """检索类型"""
    VECTOR = "vector"
    BM25 = "bm25"
    HYBRID = "hybrid"
    HYBRID_RERANK = "hybrid+rerank"


class RetrieveRequest(BaseModel):
    """
    检索请求
    """
    query: str = Field(
        ...,
        description="查询文本",
        min_length=1
    )
    top_k: int = Field(
        default=10,
        description="返回结果数量",
        ge=1,
        le=100
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="过滤条件，如 {'type': 'book'}"
    )
    doc_types: Optional[List[str]] = Field(
        default=None,
        description="指定文档类型"
    )
    use_rerank: Optional[bool] = Field(
        default=None,
        description="是否使用重排序（默认使用配置值）"
    )
    return_context: bool = Field(
        default=False,
        description="是否返回格式化的上下文"
    )
    max_context_length: int = Field(
        default=3000,
        description="最大上下文长度",
        ge=100,
        le=10000
    )


class RetrievalResult(BaseModel):
    """检索结果项"""
    chunk_id: str
    doc_id: str
    content: str
    score: float
    rank: int
    retrieval_type: RetrievalType
    metadata: Dict[str, Any]
    source: Optional[str] = None
    doc_name: Optional[str] = None


class RetrieveResponse(BaseModel):
    """检索响应"""
    success: bool
    query: str
    total_results: int
    results: List[RetrievalResult]
    retrieval_type: RetrievalType
    processing_time_ms: Optional[float] = None


class ContextResponse(BaseModel):
    """上下文响应"""
    success: bool
    query: str
    context: str
    sources: List[str]
    chunk_count: int
    total_length: int


class KnowledgeItem(BaseModel):
    """知识项"""
    doc_id: str = Field(..., description="文档唯一ID")
    name: str = Field(..., description="文档名称")
    source: str = Field(..., description="文档来源路径")
    doc_type: str = Field(..., description="文档类型")
    creator: str = Field(..., description="创建者用户ID")
    is_system: bool = Field(..., description="是否为系统知识")
    chunk_count: int = Field(default=0, description="分块数量")
    update_time: str = Field(default="", description="更新时间")


class KnowledgeListResponse(BaseModel):
    """知识列表响应"""
    success: bool
    total: int
    system_knowledge: List[KnowledgeItem] = Field(default_factory=list, description="系统知识列表")
    user_knowledge: List[KnowledgeItem] = Field(default_factory=list, description="用户知识列表")
    message: Optional[str] = None


class DeleteKnowledgeResponse(BaseModel):
    """删除知识响应"""
    success: bool
    doc_id: str
    message: str