"""
助教专用 MCP 工具 - 知识库管理
提供查看源文档列表、上传文档、删除文档等功能
"""

from typing import Optional, List
from pathlib import Path
from fastmcp import FastMCP
from loguru import logger

# 创建助教知识库管理 MCP Server
assistant_knowledge_mcp = FastMCP(name="assistant_knowledge")


@assistant_knowledge_mcp.tool(
    name="knowledge_list_sources",
    description="""查看知识库中的源文档列表（chunk前的原始文档）。

使用场景：
- 用户问"知识库里有哪些文档"时
- 需要查看已上传的文档列表
- 准备删除某个文档前查看列表

参数说明：
- include_system: 是否包含系统文档（默认True）
- doc_type: 按类型过滤，可选 "book", "problem", "note", "other"

返回：源文档列表，包含文档ID、名称、类型、上传时间、chunk数量
"""
)
async def knowledge_list_sources(
    user_id: str,
    include_system: bool = True,
    doc_type: Optional[str] = None
) -> str:
    """
    列出知识库源文档
    """
    try:
        from src.rag import RAG
        from src.config import get_config
        from src.ocr import get_ocr_client
        
        # 获取 RAG 实例
        config = get_config()
        ocr_client = get_ocr_client()
        rag = RAG.from_config(
            config.rag,
            config.embedding,
            config.rerank,
            ocr_client=ocr_client
        )
        
        logger.info(f"[Assistant MCP] 用户 {user_id} 查看知识库源文档列表")
        
        # 获取文档列表
        docs = rag.get_user_documents(
            user_id=user_id,
            include_system=include_system
        )
        
        # 按类型过滤
        if doc_type and docs:
            docs = [d for d in docs if d.get("type", "").lower() == doc_type.lower()]
        
        if not docs:
            return "知识库中没有文档。"
        
        # 分离系统文档和用户文档
        system_docs = [d for d in docs if d.get("is_system", False)]
        user_docs = [d for d in docs if not d.get("is_system", False)]
        
        output_parts = []
        
        # 系统文档
        if system_docs and include_system:
            output_parts.append(f"=== 系统文档 ({len(system_docs)}个) ===")
            for doc in system_docs:
                name = doc.get("name") or doc.get("source", "未知")
                doc_type = doc.get("type", "other")
                chunk_count = doc.get("chunk_count", 0)
                upload_time = doc.get("created_at", "")
                output_parts.append(f"  • {name}")
                output_parts.append(f"    类型: {doc_type} | 分块: {chunk_count} | 上传: {upload_time}")
        
        # 用户文档
        if user_docs:
            if output_parts:
                output_parts.append("")
            output_parts.append(f"=== 我的文档 ({len(user_docs)}个) ===")
            for doc in user_docs:
                name = doc.get("name") or doc.get("source", "未知")
                doc_type = doc.get("type", "other")
                chunk_count = doc.get("chunk_count", 0)
                doc_id = doc.get("doc_id", "")
                upload_time = doc.get("created_at", "")
                output_parts.append(f"  • {name}")
                output_parts.append(f"    ID: {doc_id}")
                output_parts.append(f"    类型: {doc_type} | 分块: {chunk_count} | 上传: {upload_time}")
        
        return "\n".join(output_parts)
        
    except Exception as e:
        logger.error(f"[Assistant MCP] 获取知识库列表失败: {e}")
        return f"获取知识库列表失败: {str(e)}"


async def knowledge_upload(
    file_path: str,
    user_id: str,
    doc_type: str = "other",
    confirmed: bool = False
) -> str:
    """
    上传文档到知识库
    """
    try:
        import os
        from src.rag import RAG
        from src.rag.core.schemas import DocumentType
        from src.config import get_config
        from src.ocr import get_ocr_client
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return f"错误：文件不存在 '{file_path}'"
        
        if not os.path.isfile(file_path):
            return f"错误：路径不是文件 '{file_path}'"
        
        file_name = Path(file_path).name
        file_size = os.path.getsize(file_path)
        
        # 如果未确认，返回确认提示
        if not confirmed:
            return f"即将上传文件到知识库：\n" \
                   f"  文件名: {file_name}\n" \
                   f"  大小: {file_size / 1024:.1f} KB\n" \
                   f"  类型: {doc_type}\n\n" \
                   f"请向用户确认：是否上传此文件？如果用户确认，请再次调用此工具并设置 confirmed=true"
        
        # 获取 RAG 实例
        config = get_config()
        ocr_client = get_ocr_client()
        rag = RAG.from_config(
            config.rag,
            config.embedding,
            config.rerank,
            ocr_client=ocr_client
        )
        
        logger.info(f"[Assistant MCP] 用户 {user_id} 上传文档: {file_path}")
        
        # 转换文档类型
        try:
            doc_type_enum = DocumentType(doc_type.lower())
        except ValueError:
            doc_type_enum = DocumentType.OTHER
        
        # 构建元数据
        metadata = {
            "creator": user_id,
            "source": file_path,
            "uploaded_by": "assistant"
        }
        
        # 添加文档
        success = rag.add_document(
            source=file_path,
            doc_type=doc_type_enum,
            metadata=metadata
        )
        
        if success:
            logger.info(f"[Assistant MCP] 文档 {file_name} 上传成功")
            return f"✅ 文档 '{file_name}' 已成功上传到知识库，正在处理中..."
        else:
            logger.error(f"[Assistant MCP] 文档上传失败")
            return "❌ 文档上传失败，请检查文件格式是否正确"
        
    except Exception as e:
        logger.error(f"[Assistant MCP] 上传文档异常: {e}")
        return f"上传失败: {str(e)}"


async def knowledge_delete(
    doc_id: str,
    user_id: str,
    confirmed: bool = False
) -> str:
    """
    删除知识库文档
    """
    try:
        from src.rag import RAG
        from src.config import get_config
        from src.ocr import get_ocr_client
        
        # 获取 RAG 实例
        config = get_config()
        ocr_client = get_ocr_client()
        rag = RAG.from_config(
            config.rag,
            config.embedding,
            config.rerank,
            ocr_client=ocr_client
        )
        
        logger.info(f"[Assistant MCP] 用户 {user_id} 请求删除文档: {doc_id}, confirmed={confirmed}")
        
        # 获取文档信息用于确认提示
        if not confirmed:
            docs = rag.get_user_documents(user_id=user_id, include_system=False)
            target_doc = None
            for doc in docs:
                if doc.get("doc_id") == doc_id:
                    target_doc = doc
                    break
            
            if not target_doc:
                return f"错误：找不到文档 ID '{doc_id}'"
            
            doc_name = target_doc.get("name") or target_doc.get("source", "未知")
            return f"⚠️ 即将从知识库删除文档：\n" \
                   f"  名称: {doc_name}\n" \
                   f"  ID: {doc_id}\n\n" \
                   f"此操作不可恢复！请向用户确认：是否确定删除？如果用户确认，请再次调用此工具并设置 confirmed=true"
        
        # 检查权限并删除
        can_delete, message = rag.can_delete_document(doc_id, user_id)
        
        if not can_delete:
            logger.warning(f"[Assistant MCP] 删除被拒绝: {message}")
            return f"❌ 删除失败: {message}"
        
        # 执行删除
        success, message = rag.delete_user_document(doc_id, user_id)
        
        if success:
            logger.info(f"[Assistant MCP] 文档 {doc_id} 删除成功")
            return f"✅ 文档已成功从知识库删除"
        else:
            logger.error(f"[Assistant MCP] 文档删除失败: {message}")
            return f"❌ 删除失败: {message}"
        
    except Exception as e:
        logger.error(f"[Assistant MCP] 删除文档异常: {e}")
        return f"删除失败: {str(e)}"


async def knowledge_get_detail(
    doc_id: str,
    user_id: str
) -> str:
    """
    获取文档详情
    """
    try:
        from src.rag import RAG
        from src.config import get_config
        from src.ocr import get_ocr_client
        
        # 获取 RAG 实例
        config = get_config()
        ocr_client = get_ocr_client()
        rag = RAG.from_config(
            config.rag,
            config.embedding,
            config.rerank,
            ocr_client=ocr_client
        )
        
        logger.info(f"[Assistant MCP] 用户 {user_id} 查看文档详情: {doc_id}")
        
        # 获取文档详情
        doc_detail = rag.get_document_detail(doc_id, user_id)
        
        if not doc_detail:
            return f"找不到文档 ID '{doc_id}'"
        
        # 格式化输出
        output_parts = ["文档详细信息：\n"]
        output_parts.append("=" * 50)
        output_parts.append(f"名称: {doc_detail.get('name', '未知')}")
        output_parts.append(f"ID: {doc_id}")
        output_parts.append(f"类型: {doc_detail.get('type', 'other')}")
        output_parts.append(f"上传时间: {doc_detail.get('created_at', '')}")
        output_parts.append(f"分块数量: {doc_detail.get('chunk_count', 0)}")
        output_parts.append(f"创建者: {doc_detail.get('creator', '')}")
        
        # 添加前几个chunk预览
        chunks = doc_detail.get('chunks', [])
        if chunks:
            output_parts.append(f"\n内容预览（前{min(3, len(chunks))}个分块）：")
            for i, chunk in enumerate(chunks[:3], 1):
                content = chunk.get('content', '')[:200]
                output_parts.append(f"\n--- 分块 {i} ---")
                output_parts.append(f"{content}...")
        
        return "\n".join(output_parts)
        
    except Exception as e:
        logger.error(f"[Assistant MCP] 获取文档详情失败: {e}")
        return f"获取文档详情失败: {str(e)}"


async def knowledge_add_text(
    title: str,
    content: str,
    user_id: str,
    doc_type: str = "note",
    confirmed: bool = False
) -> str:
    """
    将文本内容直接添加到知识库
    """
    try:
        import tempfile
        import os
        from datetime import datetime
        from src.rag import RAG
        from src.rag.core.schemas import DocumentType
        from src.config import get_config
        from src.ocr import get_ocr_client
        
        # 验证参数
        if not title or len(title.strip()) == 0:
            return "错误：标题不能为空"
        
        if not content or len(content.strip()) == 0:
            return "错误：内容不能为空"
        
        if len(title) > 100:
            return "错误：标题长度不能超过100个字符"
        
        # 如果未确认，返回确认提示
        if not confirmed:
            content_preview = content[:200] + "..." if len(content) > 200 else content
            return f"即将保存以下内容到知识库：\n" \
                   f"  标题: {title}\n" \
                   f"  类型: {doc_type}\n" \
                   f"  内容长度: {len(content)} 字符\n" \
                   f"  内容预览: {content_preview}\n\n" \
                   f"请向用户确认：是否保存到知识库？如果用户确认，请再次调用此工具并设置 confirmed=true"
        
        # 获取 RAG 实例
        config = get_config()
        ocr_client = get_ocr_client()
        rag = RAG.from_config(
            config.rag,
            config.embedding,
            config.rerank,
            ocr_client=ocr_client
        )
        
        logger.info(f"[Assistant MCP] 用户 {user_id} 添加文本到知识库: {title}")
        
        # 转换文档类型
        try:
            doc_type_enum = DocumentType(doc_type.lower())
        except ValueError:
            doc_type_enum = DocumentType.NOTE
        
        # 创建临时文件
        # 使用标题作为文件名（清理特殊字符）
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')[:50]  # 限制长度
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}.md"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            # 写入标题和内容
            f.write(f"# {title}\n\n")
            f.write(f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"创建者: {user_id}\n")
            f.write(f"来源: AI总结\n\n")
            f.write("---\n\n")
            f.write(content)
            temp_path = f.name
        
        try:
            # 构建元数据
            metadata = {
                "creator": user_id,
                "source": f"ai_summary://{title}",
                "uploaded_by": "assistant",
                "title": title,
                "created_at": datetime.now().isoformat()
            }
            
            # 添加文档到知识库
            success = rag.add_document(
                source=temp_path,
                doc_type=doc_type_enum,
                metadata=metadata
            )
            
            if success:
                logger.info(f"[Assistant MCP] 文本内容 '{title}' 保存成功")
                return f"✅ 内容已成功保存到知识库！\n" \
                       f"  标题: {title}\n" \
                       f"  类型: {doc_type}\n" \
                       f"  您可以在知识库中查看和管理此文档。"
            else:
                logger.error(f"[Assistant MCP] 文本内容保存失败")
                return "❌ 保存失败，请稍后重试"
        
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
        
    except Exception as e:
        logger.error(f"[Assistant MCP] 添加文本到知识库异常: {e}")
        return f"保存失败: {str(e)}"


if __name__ == "__main__":
    assistant_knowledge_mcp.run(transport="sse")
