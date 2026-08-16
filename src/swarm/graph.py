"""
Agency Swarm communication graph builders for the AI education company.

The graph defines who can talk to whom. It does not encode a workflow; business
decisions still live in agent prompts, team config, and tool results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal, Type

from agency_swarm import Agency, Agent, Handoff as AgencyHandoff
from agents import FunctionTool, Model, ModelSettings, handoff
from pydantic import Field, create_model

from .prompts import build_academic_director_instructions
from .team_context import append_work_log, update_learning_progress

AGENT_COMMUNICATION_LOG_KEY = "agent_communication_log"
from .team_manager import TeamDefinition, TeamGraphManager


@dataclass
class CompanyGraph:
    agency: Agency
    director: Agent
    agents_by_name: Dict[str, Agent]
    company_edges: List[tuple[str, str]]
    team_edges: Dict[str, List[tuple[str, str]]]
    communication_edges: List[Dict[str, Any]]

    def to_summary(self) -> Dict[str, Any]:
        return {
            "entry_agent": self.director.name,
            "agents": sorted(self.agents_by_name),
            "company_edges": [
                {"from": sender, "to": receiver}
                for sender, receiver in self.company_edges
            ],
            "team_edges": {
                team_id: [
                    {"from": sender, "to": receiver}
                    for sender, receiver in edges
                ]
                for team_id, edges in sorted(self.team_edges.items())
            },
            "communication_edges": self.communication_edges,
        }


def build_company_graph(
    *,
    team_manager: TeamGraphManager,
    model: Model,
    model_settings: ModelSettings,
) -> CompanyGraph:
    agents_by_name: Dict[str, Agent] = {}
    company_edges: List[tuple[str, str]] = []
    team_edges: Dict[str, List[tuple[str, str]]] = {}
    communication_edges: List[Dict[str, Any]] = []
    communication_flows: List[Any] = []

    director = Agent(
        name="AcademicDirectorAgent",
        instructions=build_academic_director_instructions(team_manager.format_director_context()),
        description="山姆财经学院教务总监，前台入口，负责收集考试目标和备考时间并分流到团队班主任。",
        model=model,
        model_settings=model_settings,
        tools=_build_director_tools(team_manager),
    )
    agents_by_name[director.name] = director

    director_to_head_teacher_handoff = _build_director_to_head_teacher_handoff(team_manager)
    for team in team_manager.list_enabled_teams():
        team_agents = _build_team_agents(team=team, model=model, model_settings=model_settings)
        agents_by_name.update({agent.name: agent for agent in team_agents})

        agent_by_name = {agent.name: agent for agent in team_agents}
        head_teacher = agent_by_name[str(team.head_teacher["agent_name"])]
        company_edges.append((director.name, head_teacher.name))
        communication_edges.append(
            {
                "from": director.name,
                "to": head_teacher.name,
                "team_id": team.team_id,
                "mode": "handoff",
                "relationship": "company_entry_to_head_teacher",
                "ownership": "transfer_session_to_head_teacher",
            }
        )
        communication_flows.append((director, head_teacher, director_to_head_teacher_handoff))

        formal_agents = _team_formal_agents(team=team, agent_by_name=agent_by_name)
        professor_agents = _team_professor_agents(team=team, agent_by_name=agent_by_name)
        assistant_pool_agents = _team_assistant_pool_agents(team=team, agent_by_name=agent_by_name)
        member_edges = _fully_connected_edges(formal_agents)
        assistant_pool_edges = [
            (professor, assistant)
            for professor in professor_agents
            for assistant in assistant_pool_agents
        ]
        edges = member_edges + assistant_pool_edges
        team_edges[team.team_id] = [(sender.name, receiver.name) for sender, receiver in edges]
        communication_edges.extend(
            _format_send_message_edges(
                team_id=team.team_id,
                edges=member_edges,
                relationship="team_member_collaboration",
            )
        )
        communication_edges.extend(
            _format_send_message_edges(
                team_id=team.team_id,
                edges=assistant_pool_edges,
                relationship="professor_to_assistant_pool",
                parallel_allowed=True,
            )
        )
        communication_flows.extend(edges)

    agency = Agency(
        director,
        communication_flows=communication_flows,
        name="Sam Finance Education Company",
        user_context=team_manager.user_context,
    )
    return CompanyGraph(
        agency=agency,
        director=director,
        agents_by_name=agents_by_name,
        company_edges=company_edges,
        team_edges=team_edges,
        communication_edges=communication_edges,
    )


def _build_team_agents(*, team: TeamDefinition, model: Model, model_settings: ModelSettings) -> List[Agent]:
    entries = [team.head_teacher]
    for collection_name in ("members", "assistant_pool"):
        collection = team.raw.get(collection_name) or []
        if isinstance(collection, list):
            entries.extend(entry for entry in collection if isinstance(entry, dict))

    return [_build_agent(entry=entry, model=model, model_settings=model_settings) for entry in entries]


def _build_agent(*, entry: Dict[str, Any], model: Model, model_settings: ModelSettings) -> Agent:
    return Agent(
        name=str(entry["agent_name"]),
        instructions=str(entry.get("instructions", "")),
        description=str(entry.get("description", "")),
        model=model,
        model_settings=model_settings,
    )


def _team_formal_agents(*, team: TeamDefinition, agent_by_name: Dict[str, Agent]) -> List[Agent]:
    names = [str(team.head_teacher["agent_name"])]
    members = team.raw.get("members") or []
    if isinstance(members, list):
        names.extend(str(member["agent_name"]) for member in members if isinstance(member, dict))
    return [agent_by_name[name] for name in names if name in agent_by_name]


def _team_professor_agents(*, team: TeamDefinition, agent_by_name: Dict[str, Agent]) -> List[Agent]:
    professors: List[Agent] = []
    members = team.raw.get("members") or []
    if not isinstance(members, list):
        return professors
    for member in members:
        if not isinstance(member, dict):
            continue
        role = str(member.get("role", ""))
        if "教授" in role:
            agent = agent_by_name.get(str(member.get("agent_name", "")))
            if agent is not None:
                professors.append(agent)
    return professors


def _team_assistant_pool_agents(*, team: TeamDefinition, agent_by_name: Dict[str, Agent]) -> List[Agent]:
    assistant_pool = team.raw.get("assistant_pool") or []
    if not isinstance(assistant_pool, list):
        return []
    return [
        agent_by_name[str(entry["agent_name"])]
        for entry in assistant_pool
        if isinstance(entry, dict) and str(entry.get("agent_name", "")) in agent_by_name
    ]


def _format_send_message_edges(
    *,
    team_id: str,
    edges: List[tuple[Agent, Agent]],
    relationship: str,
    parallel_allowed: bool = False,
) -> List[Dict[str, Any]]:
    return [
        {
            "from": sender.name,
            "to": receiver.name,
            "team_id": team_id,
            "mode": "send_message",
            "relationship": relationship,
            "ownership": "caller_keeps_session_control",
            "parallel_allowed": parallel_allowed,
        }
        for sender, receiver in edges
    ]


def _fully_connected_edges(agents: List[Agent]) -> List[tuple[Agent, Agent]]:
    return [
        (sender, receiver)
        for sender in agents
        for receiver in agents
        if sender.name != receiver.name
    ]


def _build_director_tools(team_manager: TeamGraphManager) -> List[FunctionTool]:
    async def list_enabled_teams(_ctx, _raw_args: str) -> str:
        summaries = [item.to_dict() for item in team_manager.list_enabled_team_summaries()]
        return json.dumps({"enabled_teams": summaries}, ensure_ascii=False, indent=2)

    async def get_team_detail(_ctx, raw_args: str) -> str:
        args = _parse_tool_args(raw_args)
        team_id = str(args.get("team_id", ""))
        detail = team_manager.get_team_detail(team_id)
        return json.dumps(detail, ensure_ascii=False, indent=2)

    return [
        FunctionTool(
            name="list_enabled_teams",
            description="查看当前公司已启用教学团队的摘要。入口默认只能看到摘要，必要时再查看详情。",
            params_json_schema={"type": "object", "properties": {}, "required": []},
            on_invoke_tool=list_enabled_teams,
            strict_json_schema=False,
        ),
        FunctionTool(
            name="get_team_detail",
            description="渐进式查看某个教学团队的完整详情，用于判断是否适合用户需求。",
            params_json_schema={
                "type": "object",
                "properties": {"team_id": {"type": "string"}},
                "required": ["team_id"],
            },
            on_invoke_tool=get_team_detail,
            strict_json_schema=False,
        ),
    ]


def _build_director_to_head_teacher_handoff(team_manager: TeamGraphManager) -> Type[AgencyHandoff]:
    class DirectorToHeadTeacherHandoff(AgencyHandoff):
        """Transfer the user conversation from the academic director to a team head teacher."""

        def create_handoff(self, recipient_agent: Agent):
            team = team_manager.find_team_by_head_teacher_agent(recipient_agent.name)
            input_type = create_model(
                f"{recipient_agent.name}HandoffInput",
                recipient_agent=(Literal[recipient_agent.name], Field(description="接手学生的班主任 agent。")),
                exam_target=(str, Field(description="用户的考试目标，例如 CPA。")),
                exam_time=(str, Field(description="用户的备考时间或考试时间，例如 1 年。")),
            )

            async def on_handoff(ctx, handoff_input) -> None:
                session_id = "default"
                if ctx.context is not None:
                    session_id = str(ctx.context.user_context.get("session_id") or "default")
                    update_learning_progress(
                        user_context=ctx.context,
                        team_id=team.team_id,
                        session_id=session_id,
                        source_agent="AcademicDirectorAgent",
                        updates={
                            "exam_target": handoff_input.exam_target,
                            "exam_time": handoff_input.exam_time,
                        },
                        note="入口教务总监完成前台必填信息收集并转接班主任。",
                    )
                    append_work_log(
                        user_context=ctx.context,
                        team_id=team.team_id,
                        session_id=session_id,
                        source_agent="AcademicDirectorAgent",
                        content="入口教务总监转接团队班主任。",
                        metadata={
                            "recipient_agent": recipient_agent.name,
                            "exam_target": handoff_input.exam_target,
                            "exam_time": handoff_input.exam_time,
                        },
                    )
                    ctx.context.user_context.setdefault(AGENT_COMMUNICATION_LOG_KEY, []).append(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "session_id": session_id,
                            "from_agent": "AcademicDirectorAgent",
                            "to_agent": recipient_agent.name,
                            "team_id": team.team_id,
                            "exam_target": handoff_input.exam_target,
                            "exam_time": handoff_input.exam_time,
                            "status": "completed",
                            "mode": "handoff",
                        }
                    )

            base_handoff = super().create_handoff(recipient_agent=recipient_agent)
            handoff_object = handoff(
                agent=recipient_agent,
                on_handoff=on_handoff,
                input_type=input_type,
                input_filter=base_handoff.input_filter,
                tool_description_override=recipient_agent.description,
                tool_name_override=base_handoff.tool_name,
            )
            handoff_object._agency_swarm_tool_class = type(self)
            return handoff_object

    return DirectorToHeadTeacherHandoff


def _parse_tool_args(raw_args: str) -> Dict[str, Any]:
    try:
        return json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return {}
