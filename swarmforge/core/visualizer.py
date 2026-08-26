"""Workflow visualization — generates Mermaid flowcharts from workflow definitions."""

from __future__ import annotations
from typing import Any

from swarmforge.core.workflow import Workflow


AGENT_SHAPE_MAP: dict[str, str] = {
    "llm": ("([", "])"),
    "tool": ("[", "]"),
    "router": ("{", "}"),
    "aggregate": ("{{", "}}"),
    "python": ("[[", "]]"),
    "http": ("/[", "/]"),
    "conditional": ("{", "}"),
}


class WorkflowVisualizer:
    """Generates Mermaid flowchart diagrams from Workflow definitions."""

    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self._step_names: set[str] = {s.name for s in workflow.steps}
        self._agent_types: dict[str, str] = {
            a.name: a.agent_type for a in workflow.agents
        }

    def _sanitize_id(self, name: str) -> str:
        return name.replace("-", "_").replace(" ", "_").replace(".", "_")

    def _node_label(self, name: str, agent_type: str) -> str:
        label = f"{name}"
        type_label = f"\\n[{agent_type}]"
        left, right = AGENT_SHAPE_MAP.get(agent_type, ("[", "]"))
        return f"{left}{label}{type_label}{right}"

    def _resolve_agent_for_step(self, step_name: str) -> str:
        for step in self.workflow.steps:
            if step.name == step_name:
                return step.agent
        return ""

    def generate(self) -> str:
        lines = ["flowchart TD"]

        node_defs = []
        connections = []
        parallel_groups: list[list[str]] = []

        {s.name: s for s in self.workflow.steps}
        completed: set[str] = set()
        remaining = list(self.workflow.steps)

        while remaining:
            ready = []
            for step in remaining:
                deps = set(step.depends_on) - completed
                if not deps:
                    ready.append(step)
            if not ready:
                parallel_groups.append([s.name for s in remaining])
                break
            parallel_groups.append([s.name for s in ready])
            completed.update(s.name for s in ready)
            remaining = [s for s in remaining if s.name not in completed]

        for group in parallel_groups:
            if len(group) > 1:
                lines.append(
                    "    subgraph parallel_group_" + str(parallel_groups.index(group))
                )
                lines.append("        direction LR")
                for step_name in group:
                    agent_type = self._agent_types.get(
                        self._resolve_agent_for_step(step_name), "llm"
                    )
                    node_id = self._sanitize_id(step_name)
                    label = self._node_label(step_name, agent_type)
                    node_defs.append(f"    {node_id}{label}")
                lines.append("    end")
            else:
                step_name = group[0]
                agent_type = self._agent_types.get(
                    self._resolve_agent_for_step(step_name), "llm"
                )
                node_id = self._sanitize_id(step_name)
                label = self._node_label(step_name, agent_type)
                node_defs.append(f"    {node_id}{label}")

        for step in self.workflow.steps:
            node_id = self._sanitize_id(step.name)
            for dep in step.depends_on:
                dep_id = self._sanitize_id(dep)
                connections.append(f"    {dep_id} --> {node_id}")

        for step in self.workflow.steps:
            node_id = self._sanitize_id(step.name)
            if step.condition:
                lines.append(f'    {node_id} -.->|"condition"| {node_id}')

        for i, group in enumerate(parallel_groups):
            if len(group) > 1:
                for step_name in group:
                    node_id = self._sanitize_id(step_name)
                    connections.append(f'    {node_id} --> |"data"| _merge_{i}')
                merge_id = f"_merge_{i}"
                node_defs.append(f'    {merge_id}(["Merge"])')
                next_steps = []
                for s in self.workflow.steps:
                    if any(d in group for d in s.depends_on):
                        next_steps.append(s.name)
                for next_step in next_steps:
                    next_id = self._sanitize_id(next_step)
                    connections.append(f"    {merge_id} --> {next_id}")

        if not connections:
            if self.workflow.steps:
                first_id = self._sanitize_id(self.workflow.steps[0].name)
                lines.append(f"    START(( )) --> {first_id}")
                last_id = self._sanitize_id(self.workflow.steps[-1].name)
                lines.append(f"    {last_id} --> END(( ))")

        lines.extend(node_defs)
        lines.extend(connections)

        return "\n".join(lines)

    def generate_markdown(self) -> str:
        mermaid = self.generate()
        return f"## Workflow: {self.workflow.name}\n\n```mermaid\n{mermaid}\n```"

    def get_parallel_groups(self) -> list[list[str]]:
        {s.name: s for s in self.workflow.steps}
        completed: set[str] = set()
        remaining = list(self.workflow.steps)
        groups: list[list[str]] = []

        while remaining:
            ready = []
            for step in remaining:
                deps = set(step.depends_on) - completed
                if not deps:
                    ready.append(step)
            if not ready:
                groups.append([s.name for s in remaining])
                break
            groups.append([s.name for s in ready])
            completed.update(s.name for s in ready)
            remaining = [s for s in remaining if s.name not in completed]

        return groups

    def get_data_flow(self) -> list[dict[str, Any]]:
        flows = []
        for step in self.workflow.steps:
            for param, source in step.input_mapping.items():
                flows.append(
                    {
                        "from": source,
                        "to": step.name,
                        "parameter": param,
                    }
                )
        return flows
