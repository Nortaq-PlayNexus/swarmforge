"""Workflow definition — parses and validates workflow YAML specs."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentDef:
    name: str
    agent_type: str
    model: str = ""
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepDef:
    name: str
    agent: str
    input_mapping: dict[str, str] = field(default_factory=dict)
    output_key: str = ""
    condition: str = ""


@dataclass
class ChannelDef:
    name: str
    source: str
    target: str
    schema: str = "json"


@dataclass
class Workflow:
    name: str
    description: str
    agents: list[AgentDef]
    steps: list[StepDef]
    channels: list[ChannelDef] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    entry_point: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Workflow:
        name = data.get("name", "unnamed")
        desc = data.get("description", "")
        variables = data.get("variables", {})

        agents = []
        for a in data.get("agents", []):
            agents.append(AgentDef(
                name=a["name"],
                agent_type=a.get("type", "llm"),
                model=a.get("model", ""),
                system_prompt=a.get("system_prompt", ""),
                tools=a.get("tools", []),
                config=a.get("config", {}),
            ))

        steps = []
        for s in data.get("steps", []):
            steps.append(StepDef(
                name=s["name"],
                agent=s["agent"],
                input_mapping=s.get("input", {}),
                output_key=s.get("output", s["name"]),
                condition=s.get("condition", ""),
            ))

        channels = []
        for c in data.get("channels", []):
            channels.append(ChannelDef(
                name=c["name"],
                source=c["source"],
                target=c["target"],
                schema=c.get("schema", "json"),
            ))

        return cls(
            name=name,
            description=desc,
            agents=agents,
            steps=steps,
            channels=channels,
            variables=variables,
            entry_point=data.get("entry_point", ""),
        )
