"""
Team subgraph registry for the AI education company.

Teams are configured like skills: each team owns a config.yaml that describes
its service boundary and head-teacher entrypoint. Production routing must read
this registry instead of hardcoding team-specific business branches.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .team_context import append_work_log, snapshot_team_progress, update_learning_progress


@dataclass
class TeamSummary:
    team_id: str
    name: str
    short_description: str
    service_boundary: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "short_description": self.short_description,
            "service_boundary": self.service_boundary,
        }


@dataclass
class TeamDefinition:
    team_id: str
    enabled: bool
    name: str
    short_description: str
    service_boundary: str
    head_teacher: Dict[str, Any]
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "TeamDefinition":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        team = data.get("team", {})
        team_id = str(team.get("id") or path.parent.name)
        head_teacher = team.get("head_teacher") or {}

        if not head_teacher.get("agent_name"):
            raise ValueError(f"团队 {team_id} 缺少 head_teacher.agent_name")

        cls._expand_assistant_pool(team)
        cls._resolve_prompt_references(team, path.parent)

        return cls(
            team_id=team_id,
            enabled=bool(team.get("enabled", True)),
            name=str(team.get("name", team_id)),
            short_description=str(team.get("short_description", "")),
            service_boundary=str(team.get("service_boundary", "")),
            head_teacher=head_teacher,
            raw=team,
        )

    @staticmethod
    def _expand_assistant_pool(team: Dict[str, Any]) -> None:
        assistant_pool = team.get("assistant_pool")
        if isinstance(assistant_pool, list):
            return
        if not isinstance(assistant_pool, dict):
            return

        template = assistant_pool.get("template") or {}
        count = int(assistant_pool.get("count") or 0)
        if count <= 0 or not isinstance(template, dict):
            team["assistant_pool"] = []
            return

        expanded = []
        for index in range(1, count + 1):
            values = {"index": index}
            entry = {
                "agent_name": str(template.get("agent_name_pattern", "AssistantAgent{index:02d}")).format(**values),
                "role": str(template.get("role", "并行子助教")),
                "description": str(template.get("description_template", "并行子助教 {index:02d}")).format(**values),
            }
            prompt_path_pattern = template.get("prompt_path_pattern")
            if prompt_path_pattern:
                entry["prompt_path"] = str(prompt_path_pattern).format(**values)
            expanded.append(entry)
        team["assistant_pool_template"] = assistant_pool
        team["assistant_pool"] = expanded

    @staticmethod
    def _resolve_prompt_references(team: Dict[str, Any], team_dir: Path) -> None:
        def resolve_prompt(entry: Dict[str, Any]) -> None:
            prompt_path = entry.get("prompt_path")
            if not prompt_path:
                return
            path = team_dir / str(prompt_path)
            if not path.exists():
                raise ValueError(f"团队 {team.get('id', team_dir.name)} 的 prompt_path 不存在: {prompt_path}")
            entry["instructions"] = path.read_text(encoding="utf-8").strip()

        head_teacher = team.get("head_teacher")
        if isinstance(head_teacher, dict):
            resolve_prompt(head_teacher)

        for collection_name in ("members", "assistant_pool"):
            entries = team.get(collection_name) or []
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        resolve_prompt(entry)

    def summary(self) -> TeamSummary:
        return TeamSummary(
            team_id=self.team_id,
            name=self.name,
            short_description=self.short_description,
            service_boundary=self.service_boundary,
        )

    def detail(self) -> Dict[str, Any]:
        return self.raw


class TeamGraphManager:
    """Loads enabled team subgraphs and exposes them as director tools."""

    def __init__(
        self,
        teams_dir: str = "team",
        enabled_team_ids: Optional[List[str]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ):
        self.teams_dir = Path(teams_dir)
        self.enabled_team_ids = set(enabled_team_ids or [])
        self.user_context = user_context if user_context is not None else {}
        self._teams = self._load_enabled_teams()

    @classmethod
    def from_config(cls, config) -> "TeamGraphManager":
        company_config = getattr(config, "swarm", None)
        teams_dir = getattr(company_config, "teams_dir", "team")
        enabled_team_ids = getattr(company_config, "enabled_team_ids", [])
        return cls(teams_dir=teams_dir, enabled_team_ids=enabled_team_ids)

    def list_enabled_team_summaries(self) -> List[TeamSummary]:
        return [team.summary() for team in self._teams.values()]

    def list_enabled_teams(self) -> List[TeamDefinition]:
        return list(self._teams.values())

    def get_team_detail(self, team_id: str) -> Dict[str, Any]:
        team = self._get_team(team_id)
        return team.detail()

    def find_team_by_head_teacher_agent(self, agent_name: str) -> TeamDefinition:
        for team in self._teams.values():
            if team.head_teacher.get("agent_name") == agent_name:
                return team
        available = ", ".join(
            str(team.head_teacher.get("agent_name"))
            for team in self._teams.values()
        ) or "none"
        raise ValueError(f"班主任 agent 未注册到启用团队: {agent_name}; available={available}")

    def get_head_teacher_agent_name(self, team_id: str) -> str:
        team = self._get_team(team_id)
        return str(team.head_teacher["agent_name"])

    def contact_head_teacher(
        self,
        team_id: str,
        request: str,
        exam_target: str,
        exam_time: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        missing_fields = [
            field_name
            for field_name, value in {
                "exam_target": exam_target,
                "exam_time": exam_time,
            }.items()
            if not str(value or "").strip()
        ]
        if missing_fields:
            return json.dumps(
                {
                    "status": "missing_required_intake",
                    "missing_fields": missing_fields,
                    "instruction": "入口教务总监必须先只补齐缺失的考试目标和备考时间，再联系团队班主任。",
                },
                ensure_ascii=False,
                indent=2,
            )

        team = self._get_team(team_id)
        context = context or {}
        update_learning_progress(
            user_context=self.user_context,
            team_id=team.team_id,
            session_id=session_id,
            source_agent="AcademicDirectorAgent",
            updates={
                "exam_target": exam_target,
                "exam_time": exam_time,
                "director_request": request,
            },
            note="入口教务总监完成前台必填信息收集并移交班主任。",
        )
        append_work_log(
            user_context=self.user_context,
            team_id=team.team_id,
            session_id=session_id,
            source_agent="AcademicDirectorAgent",
            content="入口教务总监联系团队班主任。",
            metadata={
                "request": request,
                "exam_target": exam_target,
                "exam_time": exam_time,
            },
        )
        team_progress = snapshot_team_progress(self.user_context, team.team_id, session_id)
        response = {
            "status": "contacted_head_teacher",
            "team_id": team.team_id,
            "team_name": team.name,
            "head_teacher": team.head_teacher,
            "request": request,
            "director_intake": {
                "exam_target": exam_target,
                "exam_time": exam_time,
            },
            "context": context,
            "team_progress": team_progress,
            "response_guidance": (
                "请由班主任承接该需求：先判断是否属于团队服务边界；"
                "入口只负责收集考试目标和备考时间；"
                "如适合，由班主任继续问清基础、薄弱点、当前阶段和期望服务，并组织团队形成下一步安排；"
                "如不适合，明确说明不应强行推荐本团队。"
            ),
        }
        return json.dumps(response, ensure_ascii=False, indent=2)

    def format_director_context(self) -> str:
        summaries = [summary.to_dict() for summary in self.list_enabled_team_summaries()]
        return json.dumps({"enabled_teams": summaries}, ensure_ascii=False, indent=2)

    def _load_enabled_teams(self) -> Dict[str, TeamDefinition]:
        if not self.teams_dir.exists():
            return {}

        teams: Dict[str, TeamDefinition] = {}
        for config_path in sorted(self.teams_dir.glob("*/config.yaml")):
            team = TeamDefinition.from_yaml(config_path)
            if self.enabled_team_ids and team.team_id not in self.enabled_team_ids:
                continue
            if not team.enabled:
                continue
            teams[team.team_id] = team
        return teams

    def _get_team(self, team_id: str) -> TeamDefinition:
        if team_id not in self._teams:
            available = ", ".join(sorted(self._teams)) or "none"
            raise ValueError(f"团队未启用或不存在: {team_id}; available={available}")
        return self._teams[team_id]
