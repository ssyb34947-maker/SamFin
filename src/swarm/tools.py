"""
External assistant-style tools exposed to the teaching team.

Interactive senior assistants and professor-callable sub assistants live in the Swarm communication graph. This module only keeps deterministic external tool facades.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AssistantToolResult:
    tool_name: str
    summary: str
    sources: List[Dict[str, Any]]
    raw: Optional[str] = None

    def to_text(self) -> str:
        payload = {
            "tool_name": self.tool_name,
            "summary": self.summary,
            "sources": self.sources,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


class TeachingAssistantTools:
    """
    Tool facade for external research, question preparation, and grading capabilities.

    The implementation reuses existing MCP tools when available. It degrades to
    deterministic summaries so tests and CLI bootstrapping do not require
    external services.
    """

    def __init__(self, user_id: str = "swarm_cli", enable_external: bool = True):
        self.user_id = user_id
        self.enable_external = enable_external

    def research_assistant_tool(self, task: str, query: str, top_k: int = 5) -> AssistantToolResult:
        sources: List[Dict[str, Any]] = []
        raw: Optional[str] = None

        if self.enable_external:
            try:
                from src.config import get_config
                from src.harness.tool_service_client import MCPNetworkToolClient

                mcp_config = get_config().tool.mcp
                manager = MCPNetworkToolClient(
                    endpoint=mcp_config.endpoint,
                    timeout=mcp_config.timeout,
                    user_id=self.user_id,
                    role="professor",
                )
                raw = manager.call_tool(
                    "rag_rag_search",
                    {
                        "query": query,
                        "top_k": top_k,
                        "doc_types": ["book", "problem", "note", "other"],
                    },
                )
                sources = self._parse_rag_sources(raw)
            except Exception as exc:
                raw = f"external research unavailable: {exc}"

        if not sources:
            sources = [
                {
                    "source": "CPA会计教学团队内置教研框架",
                    "score": 0.0,
                    "content": f"围绕任务「{task}」检索/整理：{query}",
                }
            ]

        summary = (
            f"助教已围绕「{task}」完成资料检索。建议教授优先覆盖："
            "考试口径、核心概念、会计处理路径、典型题目陷阱和课后练习。"
        )
        return AssistantToolResult("research_assistant_tool", summary, sources, raw=raw)

    def question_assistant_tool(
        self,
        topic: str,
        difficulty: str = "基础到强化",
        purpose: str = "课后巩固",
    ) -> AssistantToolResult:
        sources = [
            {
                "source": "CPA会计题目设计SOP",
                "score": 0.0,
                "content": (
                    f"围绕「{topic}」准备{difficulty}练习，目的：{purpose}。"
                    "题目应覆盖概念辨析、分录处理、计算分析和易错判断。"
                ),
            }
        ]
        summary = f"助教已生成「{topic}」练习设计建议：先概念判断，再分录，再综合题。"
        return AssistantToolResult("question_assistant_tool", summary, sources)

    def grading_assistant_tool(self, answer: str, rubric: str) -> AssistantToolResult:
        sources = [
            {
                "source": "CPA会计批改规则",
                "score": 0.0,
                "content": f"批改依据：{rubric}；学生答案摘要：{answer[:200]}",
            }
        ]
        summary = "助教已完成批改准备：重点检查准则适用、科目方向、金额逻辑和表述完整性。"
        return AssistantToolResult("grading_assistant_tool", summary, sources)

    def _parse_rag_sources(self, raw: Optional[str]) -> List[Dict[str, Any]]:
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        results = payload.get("results", []) if isinstance(payload, dict) else []
        parsed = []
        for item in results[:5]:
            parsed.append(
                {
                    "source": item.get("source") or item.get("doc_name") or "未知来源",
                    "score": item.get("score", 0),
                    "content": item.get("content", "")[:500],
                }
            )
        return parsed
