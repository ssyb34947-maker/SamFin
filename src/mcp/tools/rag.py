"""
RAG MCP 工具模块
提供知识库检索、删除、添加功能
支持用户隔离：每个用户只能访问自己的知识和系统知识
"""

import json
from typing import Optional, List
from fastmcp import FastMCP
from loguru import logger

# 创建 RAG MCP Server
rag_server = FastMCP(name="rag")

# 全局 RAG 实例（延迟初始化）
_rag_instance = None


def get_rag_instance():
    """
    获取 RAG 实例（单例模式）
    
    注意：RAG 实例是全局的，但数据访问通过 user_id 隔离
    """
    global _rag_instance
    if _rag_instance is None:
        try:
            from src.config import get_config
            from src.rag import RAG
            from src.ocr import get_ocr_client
            
            config = get_config()
            ocr_client = get_ocr_client()
            
            _rag_instance = RAG.from_config(
                config.rag,
                config.embedding,
                config.rerank,
                ocr_client=ocr_client
            )
            logger.info("[RAG MCP] RAG 实例初始化完成")
        except Exception as e:
            logger.error(f"[RAG MCP] RAG 实例初始化失败: {e}")
            raise
    return _rag_instance


@rag_server.tool(
    name="rag_search",
    description="""检索知识库中的相关内容。

使用场景：
- 需要查找知识来回答问题时调用此工具
- 基于检索结果进行推理和解答

可访问的数据：
- 系统知识（公共知识库）
- 当前用户自己上传的知识
- 其他用户的知识不可见（已隔离）

参数说明：
- query: 检索查询文本（必填）
- top_k: 返回结果数量（默认5，最大20）
- doc_types: 文档类型过滤，可选 ["book", "problem", "note", "other"]

注意：不要提供 user_id 参数，系统会自动处理。

返回：格式化的检索结果，包含相关文档内容、来源和相关度分数
"""
)
async def rag_search(
    query: str,
    top_k: int = 5,
    doc_types: Optional[List[str]] = None,
    user_id: str = ""
) -> str:
    """
    检索知识库
    
    自动过滤：只返回系统知识 + 当前用户上传的知识
    """
    try:
        rag = get_rag_instance()
        
        # 限制 top_k 范围
        top_k = max(1, min(top_k, 20))
        
        logger.info(f"[RAG MCP] 用户 {user_id} 执行检索: '{query}', top_k={top_k}")
        
        # 转换文档类型
        from src.rag.core.schemas import DocumentType
        doc_type_enums = None
        if doc_types:
            doc_type_enums = []
            for dt in doc_types:
                try:
                    doc_type_enums.append(DocumentType(dt.lower()))
                except ValueError:
                    pass
        
        # 构建过滤器
        user_filters = {"creator": user_id}
        system_filters = {"creator": "system"}
        
        # 执行检索（用户自己的数据）
        user_results = rag.search(
            query=query,
            top_k=top_k,
            filters=user_filters,
            doc_types=doc_type_enums
        )
        
        # 执行检索（系统数据）
        system_results = rag.search(
            query=query,
            top_k=top_k,
            filters=system_filters,
            doc_types=doc_type_enums
        )
        
        # 合并结果并去重（按 doc_id + chunk_id）
        seen_chunks = set()
        all_results = []
        
        for result in user_results + system_results:
            chunk_key = (result.chunk.doc_id, result.chunk.id)
            if chunk_key not in seen_chunks:
                seen_chunks.add(chunk_key)
                all_results.append(result)
        
        # 按分数排序并取 top_k
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[:top_k]
        
        if not all_results:
            return "未找到相关知识。"
        
        # 格式化结果（返回完整chunk内容用于前端展示）
        import json
        results_data = []
        
        for i, result in enumerate(all_results, 1):
            chunk = result.chunk
            is_system = chunk.metadata.get("creator") == "system" or "system" in str(chunk.metadata.get("creator", ""))
            
            doc_name_val = chunk.metadata.get("doc_name", "未知文档")
            source = chunk.metadata.get("source", "")
            
            result_item = {
                "index": i,
                "doc_name": doc_name_val,
                "source": source or doc_name_val,
                "score": round(result.score, 3),
                "content": chunk.content,  # 返回完整内容
                "chunk_id": chunk.id,
                "doc_id": chunk.doc_id,
                "is_system": is_system,
                "metadata": {
                    "start_pos": chunk.start_pos,
                    "end_pos": chunk.end_pos,
                    **chunk.metadata
                }
            }
            results_data.append(result_item)
        
        # 返回JSON格式，方便前端解析
        return json.dumps({
            "total": len(results_data),
            "results": results_data
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"[RAG MCP] 检索失败: {e}")
        return f"检索失败: {str(e)}"


async def rag_delete(
    doc_id: str,
    user_id: str = ""
) -> str:
    """
    删除知识
    
    只能删除自己上传的知识，系统知识不允许删除
    """
    try:
        rag = get_rag_instance()
        
        logger.info(f"[RAG MCP] 用户 {user_id} 请求删除文档: {doc_id}")
        
        # 检查权限
        can_delete, message = rag.can_delete_document(doc_id, user_id)
        
        if not can_delete:
            logger.warning(f"[RAG MCP] 删除被拒绝: {message}")
            return f"删除失败: {message}"
        
        # 执行删除
        success, message = rag.delete_user_document(doc_id, user_id)
        
        if success:
            logger.info(f"[RAG MCP] 文档 {doc_id} 删除成功")
            return f"删除成功: {message}"
        else:
            logger.error(f"[RAG MCP] 文档 {doc_id} 删除失败: {message}")
            return f"删除失败: {message}"
            
    except Exception as e:
        logger.error(f"[RAG MCP] 删除异常: {e}")
        return f"删除失败: {str(e)}"


@rag_server.tool(
    name="rag_list",
    description="""列出当前用户可访问的知识列表。

使用场景：
- 查看自己上传的知识
- 管理知识库
- 获取文档ID用于删除

返回内容：
- 系统知识列表（只读）
- 用户自己上传的知识（可管理，显示doc_id）

参数说明：
- include_system: 是否包含系统知识（默认True）

注意：不要提供 user_id 参数，系统会自动处理。

返回：知识列表，包含文档名称、类型、分块数等信息
"""
)
async def rag_list(
    include_system: bool = True,
    user_id: str = ""
) -> str:
    """
    列出用户可访问的知识
    
    返回系统知识和用户自己的知识
    """
    try:
        rag = get_rag_instance()
        
        logger.info(f"[RAG MCP] 用户 {user_id} 请求知识列表")
        
        # 获取文档列表
        docs = rag.get_user_documents(
            user_id=user_id,
            include_system=include_system
        )
        
        if not docs:
            return "知识库为空。"
        
        # 分离系统知识和用户知识
        system_docs = [d for d in docs if d.get("is_system", False)]
        user_docs = [d for d in docs if not d.get("is_system", False)]
        
        output_parts = []
        
        # 系统知识
        if system_docs:
            output_parts.append(f"=== 系统知识 ({len(system_docs)}个) ===")
            for doc in system_docs:
                name = doc.get("name") or doc.get("source", "未知")
                doc_type = doc.get("type", "other")
                chunk_count = doc.get("chunk_count", 0)
                output_parts.append(f"  • {name} [{doc_type}] - {chunk_count}块")
        
        # 用户知识
        if user_docs:
            if output_parts:
                output_parts.append("")
            output_parts.append(f"=== 我的知识 ({len(user_docs)}个) ===")
            for doc in user_docs:
                name = doc.get("name") or doc.get("source", "未知")
                doc_type = doc.get("type", "other")
                chunk_count = doc.get("chunk_count", 0)
                doc_id = doc.get("doc_id", "")
                output_parts.append(f"  • {name} [{doc_type}] - {chunk_count}块 (ID: {doc_id})")
        
        return "\n".join(output_parts)
        
    except Exception as e:
        logger.error(f"[RAG MCP] 获取知识列表失败: {e}")
        return f"获取知识列表失败: {str(e)}"


async def rag_add_document(
    file_path: str,
    title: str,
    doc_type: str = "other",
    user_id: str = ""
) -> str:
    """
    添加文档到知识库
    
    通过本地文件路径添加文档
    """
    try:
        import os
        from pathlib import Path
        
        rag = get_rag_instance()
        
        logger.info(f"[RAG MCP] 用户 {user_id} 请求添加文档: {file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return f"错误：文件不存在 '{file_path}'"
        
        if not os.path.isfile(file_path):
            return f"错误：路径不是文件 '{file_path}'"
        
        # 转换文档类型
        from src.rag.core.schemas import DocumentType
        try:
            doc_type_enum = DocumentType(doc_type.lower())
        except ValueError:
            doc_type_enum = DocumentType.OTHER
        
        # 构建元数据
        file_name = Path(file_path).name
        
        # 验证 title 必须是非空字符串
        if not title or not title.strip():
            return f"错误：必须提供文档标题（title 参数不能为空）"
        
        doc_title = title.strip()
        
        metadata = {
            "creator": user_id,
            "source": file_path,
            "doc_name": doc_title  # 用于知识库显示的文档名
        }
        
        # 添加文档
        success = rag.add_document(
            source=file_path,
            doc_type=doc_type_enum,
            metadata=metadata
        )
        
        if success:
            logger.info(f"[RAG MCP] 文档 '{doc_title}' 添加成功")
            return f"文档 '{doc_title}' 添加成功，正在处理中..."
        else:
            logger.error(f"[RAG MCP] 文档添加失败")
            return "文档添加失败，请检查文件格式是否正确"
            
    except Exception as e:
        logger.error(f"[RAG MCP] 添加文档异常: {e}")
        return f"添加文档失败: {str(e)}"


async def rag_get_document_chunks(
    doc_id: str,
    user_id: str = ""
) -> str:
    """
    获取文档的所有分块内容
    """
    try:
        rag = get_rag_instance()
        
        logger.info(f"[RAG MCP] 用户 {user_id} 请求获取文档分块: {doc_id}")
        
        # 获取文档分块
        chunks = rag.get_document_chunks(
            doc_id=doc_id,
            user_id=user_id if user_id else None
        )
        
        if not chunks:
            return json.dumps({
                "total": 0,
                "chunks": [],
                "message": "未找到文档或无权访问"
            }, ensure_ascii=False)
        
        # 获取文档信息
        docs = rag.get_user_documents(user_id=user_id, include_system=True)
        doc_info = next((d for d in docs if d["doc_id"] == doc_id), None)
        
        # 构建响应
        result = {
            "total": len(chunks),
            "doc_id": doc_id,
            "doc_name": doc_info.get("name", "未知文档") if doc_info else "未知文档",
            "doc_type": doc_info.get("type", "other") if doc_info else "other",
            "is_system": doc_info.get("is_system", False) if doc_info else False,
            "chunks": chunks
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"[RAG MCP] 获取文档分块失败: {e}")
        return json.dumps({
            "total": 0,
            "chunks": [],
            "error": str(e)
        }, ensure_ascii=False)


if __name__ == "__main__":
    # 测试运行
    rag_server.run(transport="sse")
