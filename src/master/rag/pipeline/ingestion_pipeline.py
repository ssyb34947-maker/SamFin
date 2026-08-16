"""
数据入库 Pipeline

负责将文档数据导入 RAG 系统
"""

import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from loguru import logger

from src.rag.rag import RAG
from src.rag.core.schemas import DocumentType as RAGDocType
from src.master.rag.schemas.ingestion import (
    IngestRequest,
    IngestResponse,
    IngestStatus,
    DocumentInfo,
    DocumentType
)


class IngestionPipeline:
    """
    数据入库 Pipeline

    职责：
    1. 接收文档路径列表
    2. 调用 RAG 系统处理文档
    3. 返回处理结果和状态
    """

    def __init__(self, rag: RAG):
        """
        初始化 Pipeline

        Args:
            rag: RAG 系统实例
        """
        self.rag = rag

    def process(
        self,
        request: IngestRequest,
        creator: str = ""
    ) -> IngestResponse:
        """
        处理数据入库请求

        Args:
            request: 入库请求
            creator: 创建者用户ID

        Returns:
            IngestResponse: 处理结果
        """
        task_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(f"[IngestionPipeline] Starting task {task_id}, creator={creator}")

        if not request.file_paths:
            return IngestResponse(
                success=False,
                message="No files provided",
                task_id=task_id,
                total_files=0,
                processed_files=0,
                failed_files=0,
                documents=[]
            )

        # 转换文档类型
        doc_type = self._convert_doc_type(request.doc_type)

        # 处理每个文件
        documents: List[DocumentInfo] = []
        processed_count = 0
        failed_count = 0

        for file_path in request.file_paths:
            doc_info = self._process_single_file(
                file_path=file_path,
                doc_type=doc_type,
                metadata=request.metadata,
                creator=creator
            )
            documents.append(doc_info)

            if doc_info.status == IngestStatus.SUCCESS:
                processed_count += 1
            else:
                failed_count += 1

        elapsed_time = time.time() - start_time
        success = failed_count == 0 and processed_count > 0

        logger.info(
            f"[IngestionPipeline] Task {task_id} completed in {elapsed_time:.2f}s, "
            f"processed={processed_count}, failed={failed_count}"
        )

        return IngestResponse(
            success=success,
            message="Processing completed" if success else "Some files failed",
            task_id=task_id,
            total_files=len(request.file_paths),
            processed_files=processed_count,
            failed_files=failed_count,
            documents=documents,
            completed_at=datetime.now()
        )

    def _process_single_file(
        self,
        file_path: str,
        doc_type: RAGDocType,
        metadata: Optional[Dict[str, Any]],
        creator: str
    ) -> DocumentInfo:
        """
        处理单个文件（带详细日志）

        Args:
            file_path: 文件路径
            doc_type: 文档类型
            metadata: 元数据
            creator: 创建者

        Returns:
            DocumentInfo: 文档处理结果
        """
        path = Path(file_path)
        file_name = path.name

        logger.info(f"[IngestionPipeline] ========== 开始处理文件: {file_name} ==========")
        logger.info(f"[IngestionPipeline] 文件路径: {file_path}")
        logger.info(f"[IngestionPipeline] 文档类型: {doc_type.value}")
        logger.info(f"[IngestionPipeline] 创建者: {creator}")

        # 检查文件是否存在
        if not path.exists():
            logger.error(f"[IngestionPipeline] ❌ 文件不存在: {file_path}")
            return DocumentInfo(
                source=file_path,
                name=file_name,
                doc_type=self._reverse_convert_doc_type(doc_type),
                chunk_count=0,
                status=IngestStatus.FAILED,
                message="File not found"
            )

        file_size = path.stat().st_size
        logger.info(f"[IngestionPipeline] 文件大小: {file_size} bytes")

        try:
            # 调用 RAG 添加文档
            # 添加 creator 到 metadata
            file_metadata = metadata.copy() if metadata else {}
            file_metadata["creator"] = creator
            logger.info(f"[IngestionPipeline] 元数据: {file_metadata}")

            logger.info(f"[IngestionPipeline] >>> 调用 RAG.add_document()...")
            success = self.rag.add_document(
                source=file_path,
                doc_type=doc_type,
                metadata=file_metadata
            )

            if success:
                logger.info(f"[IngestionPipeline] ✅ 文件处理成功: {file_name}")
                return DocumentInfo(
                    source=file_path,
                    name=file_name,
                    doc_type=self._reverse_convert_doc_type(doc_type),
                    chunk_count=0,  # 可以从 RAG 获取实际数量
                    status=IngestStatus.SUCCESS,
                    message="Document ingested successfully"
                )
            else:
                logger.error(f"[IngestionPipeline] ❌ RAG.add_document() 返回失败: {file_name}")
                return DocumentInfo(
                    source=file_path,
                    name=file_name,
                    doc_type=self._reverse_convert_doc_type(doc_type),
                    chunk_count=0,
                    status=IngestStatus.FAILED,
                    message="Failed to ingest document"
                )

        except Exception as e:
            logger.error(f"[IngestionPipeline] ❌ 处理异常: {file_path}")
            logger.error(f"[IngestionPipeline] 异常类型: {type(e).__name__}")
            logger.error(f"[IngestionPipeline] 异常信息: {e}")
            import traceback
            logger.error(f"[IngestionPipeline] 堆栈跟踪:\n{traceback.format_exc()}")
            return DocumentInfo(
                source=file_path,
                name=file_name,
                doc_type=self._reverse_convert_doc_type(doc_type),
                chunk_count=0,
                status=IngestStatus.FAILED,
                message=str(e)
            )

    def _convert_doc_type(self, doc_type: DocumentType) -> RAGDocType:
        """转换文档类型"""
        mapping = {
            DocumentType.BOOK: RAGDocType.BOOK,
            DocumentType.PROBLEM: RAGDocType.PROBLEM,
            DocumentType.NOTE: RAGDocType.NOTE,
            DocumentType.OTHER: RAGDocType.OTHER
        }
        return mapping.get(doc_type, RAGDocType.OTHER)

    def _reverse_convert_doc_type(self, doc_type: RAGDocType) -> DocumentType:
        """反向转换文档类型"""
        mapping = {
            RAGDocType.BOOK: DocumentType.BOOK,
            RAGDocType.PROBLEM: DocumentType.PROBLEM,
            RAGDocType.NOTE: DocumentType.NOTE,
            RAGDocType.OTHER: DocumentType.OTHER
        }
        return mapping.get(doc_type, DocumentType.OTHER)