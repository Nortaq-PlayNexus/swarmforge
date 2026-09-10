"""Workflow definition - parses and validates workflow YAML specs."""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field, field_validator


class AgentDef(BaseModel):
    name: str
    agent_type: str = "llm"
    model: str = "gpt-4o"
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v):
        valid = ["llm", "tool", "orchestrator", "reviewer"]
        if v not in valid:
            raise ValueError(f"agent_type must be one of {valid}")
        return v


class StepDef(BaseModel):
    name: str
    agent: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: str = ""

    @field_validator("agent")
    @classmethod
    def validate_agent_exists(cls, v, info):
        # Will be validated against agents list in Workflow
        return v


class ChannelDef(BaseModel):
    name: str
    source: str
    target: str


class WorkflowSpec(BaseModel):
    name: str
    description: str = ""
    agents: list[AgentDef]
    steps: list[StepDef]
    channels: list[ChannelDef] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)

    @field_validator("agents")
    @classmethod
    def validate_agents_nonempty(cls, v):
        if not v:
            raise ValueError("at least one agent is required")
        return v

    @field_validator("steps")
    @classmethod
    def validate_steps_match_agents(cls, v, info):
        agent_names = {a.name for a in info.data.agents} if hasattr(info, "data") else set()
        for step in v:
            if step.agent not in agent_names:
                raise ValueError(f"step '{step.name}' references unknown agent '{step.agent}'")
        return v


def from_dict(data: dict[str, Any]) -> WorkflowSpec:
    """Parse and validate a workflow YAML dict."""
    return WorkflowSpec.model_validate(data)
