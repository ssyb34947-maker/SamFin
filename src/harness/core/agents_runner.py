"""
OpenAI Agents runner adapter for project tools.

This delegates the single-agent tool loop to OpenAI Agents:
model call -> tool calls/handoffs -> tool outputs -> final output.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Protocol

from loguru import logger
from openai import AsyncOpenAI

from agents import (
    Agent,
    FunctionTool,
    ModelSettings,
    OpenAIChatCompletionsModel,
    Runner,
    set_tracing_disabled,
)

from src.config import LLMConfig


class ToolProvider(Protocol):
    role: str
    agent_type: int

    def get_tools(self) -> List[Dict[str, Any]]:
        ...

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        ...


class AgentsLoopRunner:
    """
    Adapter from a project ToolProvider and LLMConfig to OpenAI Agents.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        tool_manager: ToolProvider,
        *,
        max_turns: int = 5,
        verbose: bool = False,
        stream: bool = True,
    ):
        self.llm_config = llm_config
        self.tool_manager = tool_manager
        self.max_turns = max_turns
        self.verbose = verbose
        self.stream = stream
        self._tools: Optional[List[FunctionTool]] = None

        # Tracing requires OpenAI platform credentials. This project commonly
        # uses OpenAI-compatible providers such as DeepSeek, so disable it by
        # default for provider compatibility.
        set_tracing_disabled(True)

        self._client = AsyncOpenAI(
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
        )
        self._model = OpenAIChatCompletionsModel(
            model=llm_config.model_name,
            openai_client=self._client,
            buffer_streamed_tool_calls=True,
        )

    def run(
        self,
        *,
        context_messages: List[Dict[str, str]],
        thinking_callback=None,
        token_callback=None,
    ) -> str:
        system_prompt, input_items = self._split_messages(context_messages)
        agent = self._build_agent(system_prompt)

        if self.stream:
            return self._run_streamed(agent, input_items, thinking_callback, token_callback)

        result = Runner.run_sync(
            agent,
            input_items,
            max_turns=self.max_turns,
        )
        final_output = str(result.final_output or "")
        if token_callback and final_output:
            token_callback(final_output)
        return final_output

    def _run_streamed(self, agent: Agent, input_items: List[Dict[str, Any]], thinking_callback, token_callback) -> str:
        import asyncio

        async def _consume() -> str:
            result = Runner.run_streamed(
                agent,
                input_items,
                max_turns=self.max_turns,
            )
            full_text = ""

            async for event in result.stream_events():
                event_type = getattr(event, "type", "")

                if event_type == "raw_response_event":
                    data = getattr(event, "data", None)
                    data_type = getattr(data, "type", "")
                    if data_type == "response.output_text.delta":
                        delta = getattr(data, "delta", "") or ""
                        full_text += delta
                        if token_callback and delta:
                            token_callback(delta)
                    continue

                if event_type == "run_item_stream_event":
                    item = getattr(event, "item", None)
                    item_type = getattr(item, "type", "")
                    if item_type == "tool_call_item":
                        raw_item = getattr(item, "raw_item", None)
                        tool_name = self._extract_tool_name(raw_item)
                        if thinking_callback:
                            thinking_callback(
                                "tool_call",
                                {
                                    "tool_name": tool_name,
                                    "arguments": self._extract_tool_arguments(raw_item),
                                    "result": None,
                                },
                            )
                    elif item_type == "tool_call_output_item":
                        if thinking_callback:
                            thinking_callback(
                                "tool_result",
                                {
                                    "tool_name": getattr(item, "name", None),
                                    "arguments": {},
                                    "result": str(getattr(item, "output", "")),
                                },
                            )
                    continue

                if event_type == "agent_updated_stream_event" and thinking_callback:
                    new_agent = getattr(event, "new_agent", None)
                    thinking_callback(
                        "thinking_step",
                        {
                            "thought": f"Agent updated: {getattr(new_agent, 'name', 'unknown')}",
                            "tool_call": None,
                        },
                    )

            return str(result.final_output or full_text)

        return asyncio.run(_consume())

    def _build_agent(self, system_prompt: str) -> Agent:
        return Agent(
            name=self._agent_name(),
            instructions=system_prompt,
            model=self._model,
            tools=self._get_agent_tools(),
            model_settings=ModelSettings(
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens,
                parallel_tool_calls=True,
            ),
        )

    def _get_agent_tools(self) -> List[FunctionTool]:
        if self._tools is not None:
            return self._tools

        agent_tools: List[FunctionTool] = []
        for tool in self.tool_manager.get_tools():
            name = tool.get("name", "")
            if not name:
                continue
            agent_tools.append(self._build_tool(tool))

        self._tools = agent_tools
        logger.info(f"[AgentsLoopRunner] loaded tools: {[tool.name for tool in agent_tools]}")
        return agent_tools

    def _build_tool(self, tool: Dict[str, Any]) -> FunctionTool:
        name = tool.get("name", "")
        description = tool.get("description", "") or f"Call project tool {name}."
        schema = tool.get(
            "inputSchema",
            {
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

        async def _invoke(_ctx, raw_args: str) -> str:
            try:
                arguments = json.loads(raw_args or "{}")
            except json.JSONDecodeError:
                arguments = {"query": raw_args}
            return self.tool_manager.call_tool(name, arguments)

        return FunctionTool(
            name=name,
            description=description,
            params_json_schema=schema,
            on_invoke_tool=_invoke,
            strict_json_schema=False,
        )

    def _split_messages(self, messages: List[Dict[str, str]]) -> tuple[str, List[Dict[str, Any]]]:
        system_parts = [msg.get("content", "") for msg in messages if msg.get("role") == "system"]
        system_prompt = "\n\n".join(part for part in system_parts if part).strip()
        input_items = [
            {"role": msg.get("role"), "content": msg.get("content", "")}
            for msg in messages
            if msg.get("role") in {"user", "assistant"}
        ]
        return system_prompt, input_items

    def _agent_name(self) -> str:
        role = getattr(self.tool_manager, "role", "agent")
        agent_type = getattr(self.tool_manager, "agent_type", "")
        return f"{role}_{agent_type}_agents_agent"

    def _extract_tool_name(self, raw_item: Any) -> Optional[str]:
        return (
            getattr(raw_item, "name", None)
            or getattr(getattr(raw_item, "function", None), "name", None)
        )

    def _extract_tool_arguments(self, raw_item: Any) -> Dict[str, Any]:
        raw_arguments = (
            getattr(raw_item, "arguments", None)
            or getattr(getattr(raw_item, "function", None), "arguments", None)
            or "{}"
        )
        try:
            return json.loads(raw_arguments)
        except Exception:
            return {"raw": raw_arguments}
