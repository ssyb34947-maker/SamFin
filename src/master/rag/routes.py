"""
RAG API 路由

提供数据入库、检索和知识管理接口
"""

import os
import tempfile
import shutil
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Form
from loguru import logger
from typing import Optional, List

from src.master.rag.schemas.ingestion import IngestRequest, IngestResponse, DocumentType
from src.master.rag.schemas.retrieval import (
    RetrieveRequest,
    RetrieveResponse,
    ContextResponse,
    KnowledgeListResponse,
    DeleteKnowledgeResponse
)
from src.master.rag.pipeline import IngestionPipeline, RetrievalPipeline

router = APIRouter(tags=["RAG"])


def _disabled_auth_dependency() -> dict:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="RAG API is not mounted until user-system authentication is wired",
    )


def get_ingestion_pipeline(request: Request) -> IngestionPipeline:
    """获取 IngestionPipeline 实例"""
    if not hasattr(request.app.state, "ingestion_pipeline"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG ingestion pipeline not initialized"
        )
    return request.app.state.ingestion_pipeline


def get_retrieval_pipeline(request: Request) -> RetrievalPipeline:
    """获取 RetrievalPipeline 实例"""
    if not hasattr(request.app.state, "retrieval_pipeline"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG retrieval pipeline not initialized"
        )
    return request.app.state.retrieval_pipeline


@router.post("/api/rag/ingest", response_model=IngestResponse)
async def ingest_documents(
    files: List[UploadFile] = File(..., description="上传的文件列表"),
    doc_type: str = Form(default="other", description="文档类型: book, problem, note, other"),
    metadata: Optional[str] = Form(default=None, description="JSON格式的元数据"),
    current_user: dict = Depends(_disabled_auth_dependency),
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
):
    """
    数据入库接口（支持文件上传）

    将文档文件导入 RAG 系统，支持以下格式：
    - PDF（自动 OCR）
    - Word (.docx)
    - Excel (.xlsx, .xls)
    - CSV (.csv)
    - 文本 (.txt, .md)
    - JSON (.json)
    - 图片 (.png, .jpg, .jpeg, .tiff)（自动 OCR）

    Args:
        files: 上传的文件列表
        doc_type: 文档类型 (book, problem, note, other)
        metadata: JSON格式的元数据字符串
        current_user: 当前登录用户
        pipeline: IngestionPipeline 实例

    Returns:
        IngestResponse: 入库结果，包含处理状态和文档信息
    """
    logger.info(f"[RAG API] Ingest request from user {current_user['id']}: {len(files)} files")

    temp_dir = None
    try:
        # 创建临时目录保存上传的文件
        temp_dir = tempfile.mkdtemp(prefix="rag_upload_")
        file_paths = []

        # 保存上传的文件到临时目录
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            file_paths.append(file_path)
            logger.info(f"[RAG API] Saved uploaded file: {file_path}")

        # 解析元数据
        import json
        meta_dict = {}
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning(f"[RAG API] Invalid metadata JSON: {metadata}")

        # 构建请求
        request = IngestRequest(
            file_paths=file_paths,
            doc_type=DocumentType(doc_type),
            metadata=meta_dict
        )

        # 执行入库流程
        response = pipeline.process(
            request=request,
            creator=str(current_user['id'])
        )

        return response

    except Exception as e:
        logger.error(f"[RAG API] Ingest error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )
    finally:
        # 清理临时文件
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"[RAG API] Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"[RAG API] Failed to cleanup temp dir: {e}")


@router.post("/api/rag/search", response_model=RetrieveResponse)
async def search_documents(
    request: RetrieveRequest,
    current_user: dict = Depends(_disabled_auth_dependency),
    pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline)
):
    """
    文档检索接口

    使用混合检索（向量 + BM25）搜索相关文档块

    Args:
        request: 检索请求，包含查询文本和参数
        current_user: 当前登录用户
        pipeline: RetrievalPipeline 实例

    Returns:
        RetrieveResponse: 检索结果列表

    Example:
        ```json
        {
            "query": "什么是机器学习？",
            "top_k": 10,
            "filters": {"type": "book"},
            "use_rerank": true
        }
        ```
    """
    logger.info(f"[RAG API] Search request from user {current_user['id']}: {request.query}")

    try:
        # 执行检索流程
        response = pipeline.search(
            request=request,
            creator_filter=str(current_user['id'])  # 只检索自己的数据
        )

        return response

    except Exception as e:
        logger.error(f"[RAG API] Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/api/rag/context", response_model=ContextResponse)
async def generate_context(
    request: RetrieveRequest,
    current_user: dict = Depends(_disabled_auth_dependency),
    pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline)
):
    """
    生成检索上下文接口

    检索相关文档并格式化为上下文文本，适用于提供给 LLM

    Args:
        request: 检索请求
        current_user: 当前登录用户
        pipeline: RetrievalPipeline 实例

    Returns:
        ContextResponse: 格式化的上下文文本

    Example:
        ```json
        {
            "query": "解释牛顿第二定律",
            "top_k": 5,
            "max_context_length": 3000
        }
        ```
    """
    logger.info(f"[RAG API] Context request from user {current_user['id']}: {request.query}")

    try:
        # 执行上下文生成流程
        response = pipeline.generate_context(
            request=request,
            creator_filter=str(current_user['id'])
        )

        return response

    except Exception as e:
        logger.error(f"[RAG API] Context generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Context generation failed: {str(e)}"
        )


@router.get("/api/rag/knowledge", response_model=KnowledgeListResponse)
async def get_knowledge_list(
    include_system: bool = True,
    doc_type: Optional[str] = None,
    current_user: dict = Depends(_disabled_auth_dependency),
    pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline)
):
    """
    获取用户知识列表

    返回该用户上传的知识和系统提供的知识（去重）
    前端可以通过轮询此接口实现实时更新

    Args:
        include_system: 是否包含系统知识（默认 True）
        doc_type: 按文档类型过滤（可选: book, problem, note, other）
        current_user: 当前登录用户
        pipeline: RetrievalPipeline 实例

    Returns:
        KnowledgeListResponse: 知识列表，分为系统知识和用户知识

    Example Response:
        ```json
        {
            "success": true,
            "total": 10,
            "system_knowledge": [...],
            "user_knowledge": [...]
        }
        ```

    Note:
        前端建议每 5-10 秒轮询一次此接口以获取最新状态
        入库操作是异步的，文档处理完成后会出现在列表中
    """
    logger.info(f"[RAG API] Get knowledge list for user {current_user['id']}")

    try:
        response = pipeline.get_knowledge_list(
            user_id=str(current_user['id']),
            include_system=include_system,
            doc_type=doc_type
        )

        return response

    except Exception as e:
        logger.error(f"[RAG API] Get knowledge list error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get knowledge list: {str(e)}"
        )


@router.delete("/api/rag/knowledge/{doc_id}", response_model=DeleteKnowledgeResponse)
async def delete_knowledge(
    doc_id: str,
    current_user: dict = Depends(_disabled_auth_dependency),
    pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline)
):
    """
    删除知识

    删除用户自己上传的知识，系统知识不允许删除

    Args:
        doc_id: 要删除的文档ID
        current_user: 当前登录用户
        pipeline: RetrievalPipeline 实例

    Returns:
        DeleteKnowledgeResponse: 删除结果

    Example:
        DELETE /api/rag/knowledge/doc_123

    Response:
        ```json
        {
            "success": true,
            "doc_id": "doc_123",
            "message": "删除成功"
        }
        ```

    Raises:
        403: 尝试删除系统知识或无权限删除
        404: 文档不存在
    """
    logger.info(f"[RAG API] Delete knowledge {doc_id} by user {current_user['id']}")

    try:
        response = pipeline.delete_knowledge(
            doc_id=doc_id,
            user_id=str(current_user['id'])
        )

        if not response.success:
            # 根据错误类型返回不同状态码
            if "系统知识" in response.message:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=response.message
                )
            elif "不存在" in response.message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=response.message
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=response.message
                )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RAG API] Delete knowledge error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete knowledge: {str(e)}"
        )


@router.get("/api/knowledge/documents/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    current_user: dict = Depends(_disabled_auth_dependency),
    pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline)
):
    """
    获取文档的所有分块内容

    用于知识库管理界面的文档预览功能

    Args:
        doc_id: 文档ID
        current_user: 当前登录用户
        pipeline: RetrievalPipeline 实例

    Returns:
        dict: 包含文档信息和分块列表

    Example Response:
        ```json
        {
            "total": 10,
            "doc_id": "doc_123",
            "doc_name": "Python教程.pdf",
            "doc_type": "book",
            "is_system": false,
            "chunks": [
                {
                    "index": 1,
                    "chunk_id": "chunk_001",
                    "content": "分块内容...",
                    "metadata": {...}
                }
            ]
        }
        ```

    Raises:
        403: 无权访问该文档
        404: 文档不存在
    """
    logger.info(f"[RAG API] Get chunks for document {doc_id} by user {current_user['id']}")

    try:
        # 获取RAG实例
        from src.rag import RAG
        rag = pipeline.rag

        # 验证文档是否存在且用户有权限访问
        docs = rag.get_user_documents(
            user_id=str(current_user['id']),
            include_system=True
        )
        doc_info = next((d for d in docs if d["doc_id"] == doc_id), None)

        if not doc_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在或无权访问"
            )

        # 获取文档分块
        chunks = rag.get_document_chunks(
            doc_id=doc_id,
            user_id=str(current_user['id'])
        )

        return {
            "total": len(chunks),
            "doc_id": doc_id,
            "doc_name": doc_info.get("name", "未知文档"),
            "doc_type": doc_info.get("type", "other"),
            "is_system": doc_info.get("is_system", False),
            "chunks": chunks
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RAG API] Get document chunks error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document chunks: {str(e)}"
        )


@router.get("/api/rag/health")
async def health_check(
    request: Request,
    current_user: dict = Depends(_disabled_auth_dependency)
):
    """
    RAG 系统健康检查

    Returns:
        dict: 系统状态信息
    """
    ingestion_ready = hasattr(request.app.state, "ingestion_pipeline")
    retrieval_ready = hasattr(request.app.state, "retrieval_pipeline")

    return {
        "status": "healthy" if (ingestion_ready and retrieval_ready) else "unhealthy",
        "ingestion_pipeline": "ready" if ingestion_ready else "not_ready",
        "retrieval_pipeline": "ready" if retrieval_ready else "not_ready",
        "user_id": current_user['id']
    }