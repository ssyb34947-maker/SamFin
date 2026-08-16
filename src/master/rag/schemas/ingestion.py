"""
数据入库 Schema
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class DocumentType(str, Enum):
    """文档类型"""
    BOOK = "book"
    PROBLEM = "problem"
    NOTE = "note"
    OTHER = "other"


class IngestStatus(str, Enum):
    """入库状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class IngestRequest(BaseModel):
    """
    数据入库请求

    支持两种方式：
    1. 直接提供文件路径列表
    2. 提供文件内容和元数据（用于直接上传）
    """
    file_paths: Optional[List[str]] = Field(
        default=None,
        description="文件路径列表"
    )
    doc_type: DocumentType = Field(
        default=DocumentType.OTHER,
        description="文档类型"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="额外元数据"
    )


class DocumentInfo(BaseModel):
    """文档信息"""
    source: str
    name: str
    doc_type: DocumentType
    chunk_count: int
    status: IngestStatus
    message: Optional[str] = None


class IngestResponse(BaseModel):
    """数据入库响应"""
    success: bool
    message: str
    task_id: Optional[str] = None
    total_files: int
    processed_files: int
    failed_files: int
    documents: List[DocumentInfo]
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None