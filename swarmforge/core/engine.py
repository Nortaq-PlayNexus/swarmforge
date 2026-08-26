"""SwarmEngine — executes workflows by running agents in sequence or parallel."""

from __future__ import annotations
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
    TimeoutError as FuturesTimeout,
)
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from swarmforge.core.workflow import Workflow, StepDef
from swarmforge.agents.base import create_agent, BaseAgent
from swarmforge.memory.shared import SharedMemory
from swarmforge.core.bus import MessageBus


@dataclass
class StepResult:
    name: str
    success: bool
    output: dict[str, Any]
    elapsed_seconds: float
    retries_used: int
    skipped: bool = False
    error: str = ""


class SwarmEngine:
    def __init__(
        self, workflow: Workflow, display: Any = None, config: dict | None = None
    ):
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
        self._execution_history: list[StepResult] = []
        self._abort = False

        self._init_agents()

    @property
    def execution_history(self) -> list[StepResult]:
        return list(self._execution_history)

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
        self._abort = False

        if self.display:
            self.display.print_workflow_start(
                self.workflow.name, len(self.workflow.steps)
            )

        self._resolve_variables()

        execution_groups = self._build_execution_groups()

        for group in execution_groups:
            if self._abort:
                break
            if len(group) == 1:
                result = self._run_step_with_policy(group[0])
                if result and not result.success:
                    if group[0].on_failure == "abort":
                        self._abort = True
                        break
            else:
                self._run_parallel_group(group)

        elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        result = {
            "success": not self._abort,
            "workflow": self.workflow.name,
            "steps_completed": self._steps_completed,
            "elapsed_seconds": round(elapsed, 2),
            "results": self._results,
            "execution_history": [
                {
                    "name": h.name,
                    "success": h.success,
                    "elapsed_seconds": h.elapsed_seconds,
                    "retries_used": h.retries_used,
                    "skipped": h.skipped,
                    "error": h.error,
                }
                for h in self._execution_history
            ],
            "memory_snapshot": self.memory.snapshot(),
        }

        if self.display:
            self.display.print_workflow_complete(result)

        return result

    def _resolve_variables(self):
        for key, value in self.workflow.variables.items():
            self.memory.set(f"var.{key}", value, source="system")

    def _build_execution_groups(self) -> list[list[StepDef]]:
        """Build groups of steps that can execute in parallel using dependency info."""
        {s.name: s for s in self.workflow.steps}
        completed: set[str] = set()
        groups: list[list[StepDef]] = []

        remaining = list(self.workflow.steps)
        while remaining:
            ready = []
            for step in remaining:
                deps = set(step.depends_on) - completed
                if not deps:
                    ready.append(step)
            if not ready:
                groups.append(remaining)
                break
            groups.append(ready)
            completed.update(s.name for s in ready)
            remaining = [s for s in remaining if s.name not in completed]

        return groups

    def _run_parallel_group(self, steps: list[StepDef]):
        max_workers = self.config.get("max_workers", len(steps))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_step = {}
            for step in steps:
                if step.condition and not self._evaluate_condition(step.condition):
                    if self.display:
                        self.display.print_step_skip(step.name, step.condition)
                    result = StepResult(
                        name=step.name,
                        success=True,
                        output={},
                        elapsed_seconds=0,
                        retries_used=0,
                        skipped=True,
                    )
                    self._execution_history.append(result)
                    self._steps_completed += 1
                    continue
                future = executor.submit(self._run_step_with_policy, step)
                future_to_step[future] = step

            for future in as_completed(future_to_step):
                step = future_to_step[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = StepResult(
                        name=step.name,
                        success=False,
                        output={},
                        elapsed_seconds=0,
                        retries_used=0,
                        error=str(e),
                    )
                if result and not result.success:
                    if step.on_failure == "abort":
                        self._abort = True
                        executor.shutdown(wait=False, cancel_futures=True)
                        return

    def _run_step_with_policy(self, step: StepDef) -> StepResult:
        """Execute a step with retry, timeout, and error policy support."""
        retries = 0
        last_error = ""
        max_attempts = step.retry_count + 1

        for attempt in range(max_attempts):
            start = time.monotonic()
            datetime.now(timezone.utc)

            if step.condition and not self._evaluate_condition(step.condition):
                if self.display:
                    self.display.print_step_skip(step.name, step.condition)
                elapsed = time.monotonic() - start
                return StepResult(
                    name=step.name,
                    success=True,
                    output={},
                    elapsed_seconds=round(elapsed, 3),
                    retries_used=retries,
                    skipped=True,
                )

            agent = self.agents.get(step.agent)
            if not agent:
                elapsed = time.monotonic() - start
                error_msg = f"Agent '{step.agent}' not found"
                if self.display:
                    self.display.print_step_error(step.name, error_msg)
                return StepResult(
                    name=step.name,
                    success=False,
                    output={},
                    elapsed_seconds=round(elapsed, 3),
                    retries_used=retries,
                    error=error_msg,
                )

            input_data = {}
            for param_key, mem_key in step.input_mapping.items():
                input_data[param_key] = self.memory.get(
                    mem_key, self._results.get(mem_key, "")
                )
            if not input_data:
                input_data = dict(self.memory.items())

            if self.display:
                self.display.print_step_start(step.name, step.agent)

            try:
                if step.timeout:
                    with ThreadPoolExecutor(max_workers=1) as inner:
                        future = inner.submit(agent.run, input_data)
                        output = future.result(timeout=step.timeout)
                else:
                    output = agent.run(input_data)
            except FuturesTimeout:
                elapsed = time.monotonic() - start
                error_msg = f"Step timed out after {step.timeout}s"
                if self.display:
                    self.display.print_step_error(step.name, error_msg)
                if attempt < max_attempts - 1:
                    retries += 1
                    time.sleep(step.retry_backoff * (2**attempt))
                    continue
                result = StepResult(
                    name=step.name,
                    success=False,
                    output={},
                    elapsed_seconds=round(elapsed, 3),
                    retries_used=retries,
                    error=error_msg,
                )
                self._execution_history.append(result)
                return result
            except Exception as e:
                elapsed = time.monotonic() - start
                error_msg = str(e)
                if attempt < max_attempts - 1:
                    retries += 1
                    if self.display:
                        self.display.print_step_error(
                            step.name,
                            f"{error_msg} (retry {retries}/{step.retry_count})",
                        )
                    time.sleep(step.retry_backoff * (2**attempt))
                    continue
                if self.display:
                    self.display.print_step_error(step.name, error_msg)
                result = StepResult(
                    name=step.name,
                    success=False,
                    output={},
                    elapsed_seconds=round(elapsed, 3),
                    retries_used=retries,
                    error=error_msg,
                )
                self._execution_history.append(result)
                return result

            elapsed = time.monotonic() - start
            success = output.get("success", False)

            if not success and attempt < max_attempts - 1:
                retries += 1
                last_error = output.get("error", "Unknown error")
                if self.display:
                    self.display.print_step_error(
                        step.name, f"{last_error} (retry {retries}/{step.retry_count})"
                    )
                time.sleep(step.retry_backoff * (2**attempt))
                continue

            output_key = step.output_key or step.name
            self._results[output_key] = output
            self.memory.set(output_key, output, source=step.agent)

            if output.get("success") and "response" in output:
                self.memory.set(
                    f"{step.agent}_context", output["response"], source=step.agent
                )

            if self.display:
                self.display.print_step_complete(step.name, success)

            self._steps_completed += 1

            if not success and step.on_failure == "skip":
                pass
            elif not success and step.on_failure == "fallback":
                fallback = (
                    step.config.get("fallback_step")
                    if hasattr(step, "config")
                    else None
                )
                if fallback:
                    self._results[output_key] = {
                        "response": f"Fallback from {step.name}",
                        "success": True,
                    }

            result = StepResult(
                name=step.name,
                success=success,
                output=output,
                elapsed_seconds=round(elapsed, 3),
                retries_used=retries,
                error="" if success else last_error,
            )
            self._execution_history.append(result)
            return result

        elapsed = time.monotonic() - start
        result = StepResult(
            name=step.name,
            success=False,
            output={},
            elapsed_seconds=round(elapsed, 3),
            retries_used=retries,
            error=last_error or "Exhausted retries",
        )
        self._execution_history.append(result)
        return result

    def _evaluate_condition(self, condition: str) -> bool:
        if condition.startswith("var."):
            return bool(self.memory.get(condition))
        if "." in condition:
            parts = condition.split(".", 1)
            result = self._results.get(parts[0], {})
            if isinstance(result, dict):
                return bool(result.get(parts[1], False))
        return bool(self.memory.get(condition, False))
