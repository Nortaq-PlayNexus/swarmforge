"""SwarmEngine — executes workflows by running agents in sequence or parallel."""

from __future__ import annotations
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from swarmforge.core.workflow import Workflow, StepDef
from swarmforge.agents.base import create_agent, BaseAgent
from swarmforge.memory.shared import SharedMemory
from swarmforge.core.bus import MessageBus


class SwarmEngine:
    def __init__(self, workflow: Workflow, display: Any = None, config: dict | None = None):
        self.workflow = workflow
        self.display = display
        self.config = config or {}
        self.memory = SharedMemory(
            backend=self.config.get("memory_backend", "local"),
            redis_url=self.config.get("redis_url", ""),
        )
        self.bus = MessageBus()
        self.agents: dict[str, BaseAgent] = {}
        self._results: dict[str, Any] = {}
        self._steps_completed = 0
        self._start_time: datetime | None = None

        self._init_agents()

    def _init_agents(self):
        api_key = self.config.get("openai_api_key", "")
        base_url = self.config.get("llm_base_url", "https://api.openai.com/v1")

        for agent_def in self.workflow.agents:
            agent_config = dict(agent_def.config)
            if agent_def.model:
                agent_config["model"] = agent_def.model
            if agent_def.system_prompt:
                agent_config["system_prompt"] = agent_def.system_prompt
            if api_key and "api_key" not in agent_config:
                agent_config["api_key"] = api_key
            if base_url and "base_url" not in agent_config:
                agent_config["base_url"] = base_url

            agent = create_agent(agent_def.name, agent_def.agent_type, agent_config)
            agent.attach(self.memory, self.bus)
            self.agents[agent_def.name] = agent

        for ch in self.workflow.channels:
            self.bus.create_channel(ch.name)

    def run(self) -> dict[str, Any]:
        self._start_time = datetime.now(timezone.utc)

        if self.display:
            self.display.print_workflow_start(self.workflow.name, len(self.workflow.steps))

        self._resolve_variables()

        for step in self.workflow.steps:
            if step.condition and not self._evaluate_condition(step.condition):
                if self.display:
                    self.display.print_step_skip(step.name, step.condition)
                continue

            self._run_step(step)
            self._steps_completed += 1

        elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        result = {
            "success": True,
            "workflow": self.workflow.name,
            "steps_completed": self._steps_completed,
            "elapsed_seconds": round(elapsed, 2),
            "results": self._results,
            "memory_snapshot": self.memory.snapshot(),
        }

        if self.display:
            self.display.print_workflow_complete(result)

        return result

    def _resolve_variables(self):
        for key, value in self.workflow.variables.items():
            self.memory.set(f"var.{key}", value, source="system")

    def _run_step(self, step: StepDef):
        agent = self.agents.get(step.agent)
        if not agent:
            if self.display:
                self.display.print_step_error(step.name, f"Agent '{step.agent}' not found")
            return

        input_data = {}
        for param_key, mem_key in step.input_mapping.items():
            input_data[param_key] = self.memory.get(mem_key, self._results.get(mem_key, ""))

        if not input_data:
            input_data = dict(self.memory.items())

        if self.display:
            self.display.print_step_start(step.name, step.agent)

        output = agent.run(input_data)

        output_key = step.output_key or step.name
        self._results[output_key] = output
        self.memory.set(output_key, output, source=step.agent)

        if output.get("success") and "response" in output:
            self.memory.set(f"{step.agent}_context", output["response"], source=step.agent)

        if self.display:
            self.display.print_step_complete(step.name, output.get("success", False))

    def _evaluate_condition(self, condition: str) -> bool:
        if condition.startswith("var."):
            return bool(self.memory.get(condition))
        if "." in condition:
            parts = condition.split(".", 1)
            result = self._results.get(parts[0], {})
            if isinstance(result, dict):
                return bool(result.get(parts[1], False))
        return bool(self.memory.get(condition, False))
