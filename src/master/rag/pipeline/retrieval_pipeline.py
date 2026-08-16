"""
检索 Pipeline

负责执行 RAG 检索流程和知识管理
"""

import time
from typing import List, Optional, Dict, Any

from loguru import logger

from src.rag.rag import RAG
from src.rag.core.schemas import DocumentType as RAGDocType, RetrievalResult as RAGRetrievalResult
from src.master.rag.schemas.retrieval import (
    RetrieveRequest,
    RetrieveResponse,
    RetrievalResult,
    RetrievalType,
    ContextResponse,
    KnowledgeItem,
    KnowledgeListResponse,
    DeleteKnowledgeResponse
)


class RetrievalPipeline:
    """
    检索 Pipeline

    职责：
    1. 接收查询请求
    2. 调用 RAG 系统执行检索
    3. 格式化返回结果
    """

    def __init__(self, rag: RAG):
        """
        初始化 Pipeline

        Args:
            rag: RAG 系统实例
        """
        self.rag = rag

    def search(
        self,
        request: RetrieveRequest,
        creator_filter: Optional[str] = None
    ) -> RetrieveResponse:
        """
        执行检索

        Args:
            request: 检索请求
            creator_filter: 创建者过滤（用于权限控制）

        Returns:
            RetrieveResponse: 检索结果
        """
        start_time = time.time()

        logger.info(f"[RetrievalPipeline] Search query: {request.query}, top_k={request.top_k}")

        try:
            # 转换文档类型
            doc_types = None
            if request.doc_types:
                doc_types = [self._convert_doc_type(dt) for dt in request.doc_types]

            # 构建过滤条件
            filters = request.filters.copy() if request.filters else {}

            # 添加创建者过滤（如果指定）
            if creator_filter:
                filters["creator"] = creator_filter

            # 执行检索
            results = self.rag.search(
                query=request.query,
                top_k=request.top_k,
                filters=filters if filters else None,
                doc_types=doc_types,
                use_rerank=request.use_rerank
            )

            # 转换结果格式
            api_results = self._convert_results(results)

            # 确定检索类型
            retrieval_type = self._determine_retrieval_type(results)

            elapsed_time = (time.time() - start_time) * 1000  # 转换为毫秒

            logger.info(
                f"[RetrievalPipeline] Search completed in {elapsed_time:.2f}ms, "
                f"found {len(results)} results"
            )

            return RetrieveResponse(
                success=True,
                query=request.query,
                total_results=len(api_results),
                results=api_results,
                retrieval_type=retrieval_type,
                processing_time_ms=elapsed_time
            )

        except Exception as e:
            logger.error(f"[RetrievalPipeline] Search error: {e}")
            return RetrieveResponse(
                success=False,
                query=request.query,
                total_results=0,
                results=[],
                retrieval_type=RetrievalType.HYBRID,
                processing_time_ms=None
            )

    def generate_context(
        self,
        request: RetrieveRequest,
        creator_filter: Optional[str] = None
    ) -> ContextResponse:
        """
        生成检索上下文

        Args:
            request: 检索请求
            creator_filter: 创建者过滤

        Returns:
            ContextResponse: 上下文结果
        """
        logger.info(f"[RetrievalPipeline] Generate context for: {request.query}")

        try:
            # 先执行检索
            search_response = self.search(request, creator_filter)

            if not search_response.success or not search_response.results:
                return ContextResponse(
                    success=True,
                    query=request.query,
                    context="",
                    sources=[],
                    chunk_count=0,
                    total_length=0
                )

            # 构建上下文
            context_parts = []
            sources = []
            current_length = 0

            for i, result in enumerate(search_response.results, 1):
                # 构建块文本
                part = f"[文档 {i}]\n"
                if result.doc_name:
                    part += f"来源: {result.doc_name}\n"
                elif result.source:
                    part += f"来源: {result.source}\n"
                part += f"内容: {result.content}\n"
                part += f"相关度: {result.score:.3f}\n\n"

                # 检查长度限制
                if current_length + len(part) > request.max_context_length:
                    break

                context_parts.append(part)
                current_length += len(part)

                # 收集来源
                source = result.doc_name or result.source or "未知来源"
                if source not in sources:
                    sources.append(source)

            context = "".join(context_parts)

            logger.info(
                f"[RetrievalPipeline] Context generated, "
                f"chunks={len(search_response.results)}, length={len(context)}"
            )

            return ContextResponse(
                success=True,
                query=request.query,
                context=context,
                sources=sources,
                chunk_count=len(search_response.results),
                total_length=len(context)
            )

        except Exception as e:
            logger.error(f"[RetrievalPipeline] Context generation error: {e}")
            return ContextResponse(
                success=False,
                query=request.query,
                context="",
                sources=[],
                chunk_count=0,
                total_length=0
            )

    def _convert_results(
        self,
        rag_results: List[RAGRetrievalResult]
    ) -> List[RetrievalResult]:
        """
        转换 RAG 结果到 API 结果

        Args:
            rag_results: RAG 检索结果

        Returns:
            List[RetrievalResult]: API 格式的结果
        """
        api_results = []

        for i, result in enumerate(rag_results, 1):
            chunk = result.chunk

            api_result = RetrievalResult(
                chunk_id=chunk.id,
                doc_id=chunk.doc_id,
                content=chunk.content,
                score=result.score,
                rank=i,
                retrieval_type=self._map_retrieval_type(result.retrieval_type),
                metadata=chunk.metadata,
                source=chunk.metadata.get("source"),
                doc_name=chunk.metadata.get("doc_name")
            )
            api_results.append(api_result)

        return api_results

    def _map_retrieval_type(self, retrieval_type: str) -> RetrievalType:
        """映射检索类型"""
        mapping = {
            "vector": RetrievalType.VECTOR,
            "bm25": RetrievalType.BM25,
            "hybrid": RetrievalType.HYBRID,
            "hybrid+rerank": RetrievalType.HYBRID_RERANK
        }
        return mapping.get(retrieval_type, RetrievalType.HYBRID)

    def _determine_retrieval_type(
        self,
        results: List[RAGRetrievalResult]
    ) -> RetrievalType:
        """确定检索类型"""
        if not results:
            return RetrievalType.HYBRID

        # 从第一个结果获取检索类型
        first_type = results[0].retrieval_type
        return self._map_retrieval_type(first_type)

    def _convert_doc_type(self, doc_type: str) -> RAGDocType:
        """转换文档类型"""
        mapping = {
            "book": RAGDocType.BOOK,
            "problem": RAGDocType.PROBLEM,
            "note": RAGDocType.NOTE,
            "other": RAGDocType.OTHER
        }
        return mapping.get(doc_type.lower(), RAGDocType.OTHER)

    def get_knowledge_list(
        self,
        user_id: str,
        include_system: bool = True,
        doc_type: Optional[str] = None
    ) -> KnowledgeListResponse:
        """
        获取用户知识列表

        Args:
            user_id: 用户ID
            include_system: 是否包含系统知识
            doc_type: 文档类型过滤

        Returns:
            KnowledgeListResponse: 知识列表响应
        """
        logger.info(f"[RetrievalPipeline] Get knowledge list for user: {user_id}")

        try:
            # 转换文档类型
            rag_doc_type = None
            if doc_type:
                rag_doc_type = self._convert_doc_type(doc_type)

            # 获取文档列表
            docs = self.rag.get_user_documents(
                user_id=user_id,
                include_system=include_system,
                doc_type=rag_doc_type
            )

            # 转换为 API 格式
            knowledge_items = []
            for doc in docs:
                item = KnowledgeItem(
                    doc_id=doc["doc_id"],
                    name=doc.get("name") or doc.get("source", ""),
                    source=doc.get("source", ""),
                    doc_type=doc.get("type", "other"),
                    creator=doc.get("creator", ""),
                    is_system=doc.get("is_system", False),
                    chunk_count=doc.get("chunk_count", 0),
                    update_time=doc.get("update_time", "")
                )
                knowledge_items.append(item)

            # 分离系统知识和用户知识
            system_knowledge = [k for k in knowledge_items if k.is_system]
            user_knowledge = [k for k in knowledge_items if not k.is_system]

            logger.info(
                f"[RetrievalPipeline] Found {len(system_knowledge)} system "
                f"and {len(user_knowledge)} user knowledge items"
            )

            return KnowledgeListResponse(
                success=True,
                total=len(knowledge_items),
                system_knowledge=system_knowledge,
                user_knowledge=user_knowledge
            )

        except Exception as e:
            logger.error(f"[RetrievalPipeline] Get knowledge list error: {e}")
            return KnowledgeListResponse(
                success=False,
                total=0,
                system_knowledge=[],
                user_knowledge=[],
                message=str(e)
            )

    def delete_knowledge(
        self,
        doc_id: str,
        user_id: str
    ) -> DeleteKnowledgeResponse:
        """
        删除知识

        Args:
            doc_id: 文档ID
            user_id: 用户ID

        Returns:
            DeleteKnowledgeResponse: 删除响应
        """
        logger.info(f"[RetrievalPipeline] Delete knowledge: {doc_id} by user: {user_id}")

        try:
            # 检查权限并删除
            success, message = self.rag.delete_user_document(doc_id, user_id)

            if success:
                logger.info(f"[RetrievalPipeline] Knowledge {doc_id} deleted successfully")
                return DeleteKnowledgeResponse(
                    success=True,
                    doc_id=doc_id,
                    message=message
                )
            else:
                logger.warning(f"[RetrievalPipeline] Failed to delete {doc_id}: {message}")
                return DeleteKnowledgeResponse(
                    success=False,
                    doc_id=doc_id,
                    message=message
                )

        except Exception as e:
            logger.error(f"[RetrievalPipeline] Delete knowledge error: {e}")
            return DeleteKnowledgeResponse(
                success=False,
                doc_id=doc_id,
                message=f"删除失败: {str(e)}"
            )