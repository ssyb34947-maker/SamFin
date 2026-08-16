"""
Runtime for the AI education company communication graph.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from agents import (
    ModelSettings,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)

from src.config import Config

from .schemas import CompanyRunResult
from .graph import AGENT_COMMUNICATION_LOG_KEY, CompanyGraph, build_company_graph
from .team_context import (
    TEAM_PROGRESS_KEY,
    append_work_log,
    set_learning_context_window,
    update_learning_progress,
)
from .team_manager import TeamGraphManager
from .trace import TraceRecorder
from src.user_system import UserSystemClient

DIRECTOR_AGENT_NAME = 'AcademicDirectorAgent'
HANDOFF_CLAIM_TERMS = (
    '交接已完成',
    '已完成交接',
    '已完成对接',
    '已正式移交',
    '已移交',
    '已经移交',
    '已联系',
    '已经联系',
    '已为你联系',
    '已为您联系',
    '已正式接手',
    '已接手',
)
FALSE_HANDOFF_CORRECTION = (
    '我需要更正：我还没有完成与班主任的真实对接。'
    '目前只能确认你的入口信息已经齐全，我会继续联系对应教学团队的班主任；'
    '班主任回应后，才算正式交接完成。'
)


class EducationCompanyRuntime:
    """Public runtime facade for the AI education company."""

    def __init__(self, impl: 'BaseCompanyRuntime'):
        self._impl = impl

    @classmethod
    def from_config(cls, config: Config, *, enable_external_tools: bool = True) -> 'EducationCompanyRuntime':
        company_config = getattr(config, 'swarm', None)
        trace_enabled = True if company_config is None else company_config.trace_enabled
        manager = TeamGraphManager.from_config(config)

        if company_config is not None and not company_config.enabled:
            impl: BaseCompanyRuntime = DisabledCompanyRuntime(trace_enabled=trace_enabled)
        else:
            impl = AgentsCompanyRuntime(
                config=config,
                team_manager=manager,
                trace_enabled=trace_enabled,
                enable_external_tools=enable_external_tools,
            )
        return cls(impl)

    async def chat(self, message: str, session_id: Optional[str] = None) -> CompanyRunResult:
        return await self._impl.chat(message, session_id=session_id)

    def chat_sync(self, message: str, session_id: Optional[str] = None) -> CompanyRunResult:
        return asyncio.run(self.chat(message, session_id=session_id))

    @property
    def runtime_name(self) -> str:
        return self._impl.runtime_name

    def graph_summary(self) -> Dict[str, Any]:
        return self._impl.graph_summary()

    def progress_snapshot(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        return self._impl.progress_snapshot(session_id=session_id)

    def communication_log(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._impl.communication_log(session_id=session_id)

    def flush_learning_context(self, session_id: str, user_id: Optional[str] = None, class_id: Optional[str] = None) -> Dict[str, Any]:
        return self._impl.flush_learning_context(session_id=session_id, user_id=user_id, class_id=class_id)


class BaseCompanyRuntime:
    runtime_name = 'base'

    async def chat(self, message: str, session_id: Optional[str] = None) -> CompanyRunResult:
        raise NotImplementedError

    def graph_summary(self) -> Dict[str, Any]:
        return {}

    def progress_snapshot(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        return {}

    def communication_log(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    def flush_learning_context(self, session_id: str, user_id: Optional[str] = None, class_id: Optional[str] = None) -> Dict[str, Any]:
        return {"flushed_records": 0}


class DisabledCompanyRuntime(BaseCompanyRuntime):
    runtime_name = 'disabled_company_runtime'

    def __init__(self, trace_enabled: bool = True):
        self.trace_enabled = trace_enabled

    async def chat(self, message: str, session_id: Optional[str] = None) -> CompanyRunResult:
        session_id = session_id or f'company_{uuid.uuid4().hex[:12]}'
        trace = TraceRecorder(enabled=self.trace_enabled)
        final_output = 'AI 教育公司当前未启用，暂时无法分配教学团队。'
        trace.add('final_output', agent_name=DIRECTOR_AGENT_NAME, content=final_output)
        return CompanyRunResult(final_output=final_output, session_id=session_id, active_team=None, trace=trace.events)


class DisabledUserSystemClient:
    """No-op user system client for tests with external tools disabled."""

    def __init__(self):
        self.pending_records: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
        self.recent_records: Dict[tuple[str, str], List[Dict[str, Any]]] = {}

    def append_learning_progress(self, *, user_id: str, class_id: str, team_id: str, source_agent: str, record_type: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        key = (user_id, class_id)
        item = {
            'record_id': f'pending_{len(self.pending_records.get(key, [])) + 1}',
            'user_id': user_id,
            'class_id': class_id,
            'team_id': team_id,
            'source_agent': source_agent,
            'record_type': record_type,
            'content': content,
            'metadata': metadata or {},
            'created_at': 'pending',
        }
        self.pending_records.setdefault(key, []).append(item)
        return item

    def query_learning_progress(self, *, user_id: str, class_id: str, team_id: str, recent_limit: int = 8) -> Dict[str, Any]:
        key = (user_id, class_id)
        return {
            'learning_class': {
                'user_id': user_id,
                'class_id': class_id,
                'team_id': team_id,
                'learning_goal': team_id,
                'status': 'active',
                'started_at': 'disabled',
                'ended_at': None,
            },
            'recent_records': self.recent_records.get(key, [])[-recent_limit:],
            'summaries': [],
            'pending_records': list(self.pending_records.get(key, [])),
        }

    def flush_learning_context(self, *, user_id: str, class_id: str) -> Dict[str, Any]:
        key = (user_id, class_id)
        pending = self.pending_records.get(key, [])
        self.recent_records.setdefault(key, []).extend(pending)
        count = len(pending)
        self.pending_records[key] = []
        return {'flushed_records': count}


class AgentsCompanyRuntime(BaseCompanyRuntime):
    """
    Production runtime backed by a real Agency Swarm communication graph.

    The graph defines access edges. Routing remains model-driven through prompts,
    team config, and tool results.
    """

    runtime_name = 'agents_company_runtime'

    def __init__(
        self,
        config: Config,
        team_manager: TeamGraphManager,
        *,
        trace_enabled: bool = True,
        enable_external_tools: bool = True,
    ):
        self.config = config
        self.team_manager = team_manager
        self.trace_enabled = trace_enabled
        self.enable_external_tools = enable_external_tools
        self._sessions: Dict[str, List[Dict[str, str]]] = {}
        self._session_recipient_agents: Dict[str, str] = {}
        user_system_config = getattr(config, "user_system", None)
        if self.enable_external_tools:
            self.user_system_client = UserSystemClient(
                mode=getattr(user_system_config, "mode", "remote"),
                base_url=getattr(user_system_config, "base_url", ""),
                timeout=getattr(user_system_config, "request_timeout", 10.0),
            )
        else:
            self.user_system_client = DisabledUserSystemClient()

        set_tracing_disabled(True)
        self._client = AsyncOpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
        )
        self._model = OpenAIChatCompletionsModel(
            model=config.llm.model_name,
            openai_client=self._client,
            buffer_streamed_tool_calls=True,
        )
        self._model_settings = ModelSettings(
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
            parallel_tool_calls=True,
        )
        self.graph: CompanyGraph = build_company_graph(
            team_manager=self.team_manager,
            model=self._model,
            model_settings=self._model_settings,
        )

    async def chat(self, message: str, session_id: Optional[str] = None) -> CompanyRunResult:
        session_id = session_id or f'company_{uuid.uuid4().hex[:12]}'
        self._sessions.setdefault(session_id, []).append({'role': 'user', 'content': message})

        trace = TraceRecorder(enabled=self.trace_enabled)
        recipient_agent = self._session_recipient_agents.get(session_id, DIRECTOR_AGENT_NAME)
        communication_count_before = len(self.communication_log(session_id=session_id))
        trace.add(
            'agent_start',
            agent_name=recipient_agent,
            content='教务总监启动公司接待。' if recipient_agent == DIRECTOR_AGENT_NAME else '团队班主任继续接待。',
            metadata={**self.graph.to_summary(), 'recipient_agent': recipient_agent},
        )

        result = await self.graph.agency.get_response(
            message,
            recipient_agent=recipient_agent,
            context_override={'session_id': session_id},
            max_turns=self.config.harness.max_agent_turns,
        )
        final_output = str(result.final_output or '')
        self._record_handoff_events(result=result, session_id=session_id)
        active_team = self._extract_active_team(session_id)
        new_communications = self.communication_log(session_id=session_id)[communication_count_before:]
        final_agent_name = getattr(getattr(result, 'last_agent', None), 'name', recipient_agent)
        handed_off_team = self._team_for_head_teacher(final_agent_name)
        if handed_off_team:
            active_team = active_team or handed_off_team
            self._session_recipient_agents[session_id] = final_agent_name
        elif active_team:
            head_teacher = self.team_manager.get_head_teacher_agent_name(active_team)
            self._session_recipient_agents[session_id] = head_teacher
        elif recipient_agent == DIRECTOR_AGENT_NAME and self._looks_like_handoff_claim(final_output):
            final_output = FALSE_HANDOFF_CORRECTION
            trace.add(
                'error',
                agent_name=recipient_agent,
                content='拦截未发生真实 agent 通信的交接话术。',
                metadata={'communication_count_before': communication_count_before},
            )

        self._sessions[session_id].append({'role': 'assistant', 'content': final_output})

        trace.add(
            'final_output',
            agent_name=final_agent_name,
            content=final_output,
            metadata={
                'active_team': active_team,
                'new_agent_calls': len(new_communications),
                'recipient_agent': recipient_agent,
            },
        )
        return CompanyRunResult(
            final_output=final_output,
            session_id=session_id,
            active_team=active_team,
            trace=trace.events,
        )


    def _record_handoff_events(self, *, result: Any, session_id: str) -> None:
        new_items = list(getattr(result, 'new_items', []) or [])
        call_args_by_id: Dict[str, Dict[str, Any]] = {}
        for item in new_items:
            if getattr(item, 'type', None) != 'handoff_call_item':
                continue
            raw_item = getattr(item, 'raw_item', None)
            call_id = str(getattr(raw_item, 'call_id', '') or '')
            if not call_id:
                continue
            call_args_by_id[call_id] = self._parse_json_args(str(getattr(raw_item, 'arguments', '') or '{}'))

        existing_call_ids = {
            str(event.get('call_id'))
            for event in self.communication_log(session_id=session_id)
            if event.get('call_id')
        }
        for item in new_items:
            if getattr(item, 'type', None) != 'handoff_output_item':
                continue
            source_agent = getattr(getattr(item, 'source_agent', None), 'name', None)
            target_agent = getattr(getattr(item, 'target_agent', None), 'name', None)
            if source_agent != DIRECTOR_AGENT_NAME or not target_agent:
                continue
            team_id = self._team_for_head_teacher(str(target_agent))
            if not team_id:
                continue
            raw_item = getattr(item, 'raw_item', {}) or {}
            call_id = str(raw_item.get('call_id') if isinstance(raw_item, dict) else getattr(raw_item, 'call_id', '') or '')
            if call_id and call_id in existing_call_ids:
                continue
            args = call_args_by_id.get(call_id, {})
            exam_target = str(args.get('exam_target', '') or '')
            exam_time = str(args.get('exam_time', '') or '')
            updates = {}
            if exam_target:
                updates['exam_target'] = exam_target
            if exam_time:
                updates['exam_time'] = exam_time
            if updates:
                self._append_user_learning_record(
                    session_id=session_id,
                    team_id=team_id,
                    source_agent=source_agent,
                    record_type='handoff',
                    content=f'入口交接到 {target_agent}，考试目标：{exam_target}，备考时间：{exam_time}',
                    metadata={
                        'exam_target': exam_target,
                        'exam_time': exam_time,
                        'target_agent': target_agent,
                        'call_id': call_id,
                    },
                )
                self._refresh_learning_context_window(session_id=session_id, team_id=team_id)
                update_learning_progress(
                    user_context=self.team_manager.user_context,
                    team_id=team_id,
                    session_id=session_id,
                    source_agent=DIRECTOR_AGENT_NAME,
                    updates=updates,
                    note='入口教务总监完成前台必填信息收集并转接班主任。',
                )
            append_work_log(
                user_context=self.team_manager.user_context,
                team_id=team_id,
                session_id=session_id,
                source_agent=DIRECTOR_AGENT_NAME,
                content='入口教务总监转接团队班主任。',
                metadata={
                    'recipient_agent': target_agent,
                    'exam_target': exam_target,
                    'exam_time': exam_time,
                    'call_id': call_id,
                    'mode': 'handoff',
                },
            )
            self.team_manager.user_context.setdefault(AGENT_COMMUNICATION_LOG_KEY, []).append(
                {
                    'timestamp': datetime.now().isoformat(),
                    'session_id': session_id,
                    'from_agent': source_agent,
                    'to_agent': target_agent,
                    'team_id': team_id,
                    'exam_target': exam_target,
                    'exam_time': exam_time,
                    'status': 'completed',
                    'mode': 'handoff',
                    'call_id': call_id,
                }
            )
            if call_id:
                existing_call_ids.add(call_id)

    def _parse_json_args(self, raw_args: str) -> Dict[str, Any]:
        try:
            value = json.loads(raw_args or '{}')
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def _resolve_user_id(self, session_id: str) -> str:
        return str(self.team_manager.user_context.get('user_id') or f'visitor:{session_id}')

    def _resolve_class_id(self, session_id: str, team_id: Optional[str] = None) -> str:
        class_ids = self.team_manager.user_context.setdefault('active_class_ids', {})
        if team_id:
            return str(class_ids.setdefault(team_id, session_id))
        return session_id

    def _append_user_learning_record(
        self,
        *,
        session_id: str,
        team_id: str,
        source_agent: str,
        record_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        user_id = self._resolve_user_id(session_id)
        class_id = self._resolve_class_id(session_id, team_id)
        return self.user_system_client.append_learning_progress(
            user_id=user_id,
            class_id=class_id,
            team_id=team_id,
            source_agent=source_agent,
            record_type=record_type,
            content=content,
            metadata=metadata or {},
        )

    def _refresh_learning_context_window(self, *, session_id: str, team_id: str, recent_limit: int = 5) -> Dict[str, Any]:
        user_id = self._resolve_user_id(session_id)
        class_id = self._resolve_class_id(session_id, team_id)
        window = self.user_system_client.query_learning_progress(
            user_id=user_id,
            class_id=class_id,
            team_id=team_id,
            recent_limit=recent_limit,
        )
        set_learning_context_window(
            user_context=self.team_manager.user_context,
            team_id=team_id,
            session_id=session_id,
            window=window,
        )
        return window

    def flush_learning_context(self, session_id: str, user_id: Optional[str] = None, class_id: Optional[str] = None) -> Dict[str, Any]:
        resolved_user_id = user_id or self._resolve_user_id(session_id)
        resolved_class_id = class_id or session_id
        return self.user_system_client.flush_learning_context(
            user_id=resolved_user_id,
            class_id=resolved_class_id,
        )

    def _looks_like_handoff_claim(self, text: str) -> bool:
        return '班主任' in text and any(term in text for term in HANDOFF_CLAIM_TERMS)

    def _team_for_head_teacher(self, agent_name: str) -> Optional[str]:
        if not agent_name:
            return None
        try:
            return self.team_manager.find_team_by_head_teacher_agent(agent_name).team_id
        except ValueError:
            return None

    def graph_summary(self) -> Dict[str, Any]:
        return self.graph.to_summary()

    def progress_snapshot(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        progress = self.team_manager.user_context.get(TEAM_PROGRESS_KEY, {})
        if session_id is None:
            return progress
        return {
            team_id: sessions[session_id]
            for team_id, sessions in progress.items()
            if isinstance(sessions, dict) and session_id in sessions
        }

    def communication_log(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        events = self.team_manager.user_context.get(AGENT_COMMUNICATION_LOG_KEY, [])
        if session_id is None:
            return list(events)
        return [event for event in events if event.get('session_id') == session_id]

    def _extract_active_team(self, session_id: str) -> Optional[str]:
        progress = self.team_manager.user_context.get(TEAM_PROGRESS_KEY, {})
        for team_id, sessions in progress.items():
            if isinstance(sessions, dict) and session_id in sessions:
                return str(team_id)
        return None

