"""Base agent class and built-in agent types."""

from __future__ import annotations
import json
import requests
from abc import ABC, abstractmethod
from typing import Any

from swarmforge.memory.shared import SharedMemory
from swarmforge.core.bus import MessageBus, Message


class BaseAgent(ABC):
    def __init__(self, name: str, config: dict[str, Any] | None = None):
        self.name = name
        self.config = config or {}
        self.memory: SharedMemory | None = None
        self.bus: MessageBus | None = None

    def attach(self, memory: SharedMemory, bus: MessageBus):
        self.memory = memory
        self.bus = bus

    @abstractmethod
    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        ...

    def _memory_get(self, key: str, default: Any = None) -> Any:
        if self.memory:
            return self.memory.get(key, default)
        return default

    def _memory_set(self, key: str, value: Any):
        if self.memory:
            self.memory.set(key, value, source=self.name)

    def _send_message(self, channel: str, target: str, payload: Any) -> str:
        if self.bus:
            return self.bus.send(Message(
                channel=channel, sender=self.name, target=target, payload=payload
            ))
        return ""

    def _receive_message(self, channel: str, timeout: float = 5.0) -> Message | None:
        if self.bus:
            return self.bus.receive(channel, timeout)
        return None


class LLMAgent(BaseAgent):
    """Agent powered by an LLM (OpenAI-compatible API)."""

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        super().__init__(name, config)
        self.model = self.config.get("model", "gpt-4o")
        self.system_prompt = self.config.get("system_prompt", "You are a helpful AI assistant.")
        self.temperature = self.config.get("temperature", 0.7)
        self.base_url = self.config.get("base_url", "https://api.openai.com/v1")
        self.api_key = self.config.get("api_key", "")

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        user_content = self._build_prompt(input_data)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": self.temperature,
            "max_tokens": self.config.get("max_tokens", 4096),
        }

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=payload, timeout=120
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return {"response": content, "success": True}
        except Exception as e:
            return {"response": "", "success": False, "error": str(e)}

    def _build_prompt(self, input_data: dict[str, Any]) -> str:
        context = self._memory_get(f"{self.name}_context", "")
        parts = []
        if context:
            parts.append(f"Context from previous steps:\n{context}")
        for k, v in input_data.items():
            if isinstance(v, str):
                parts.append(f"{k}: {v}")
            else:
                parts.append(f"{k}: {json.dumps(v, indent=2)}")
        return "\n\n".join(parts) if parts else "Execute your task."


class ToolAgent(BaseAgent):
    """Agent that executes tools/functions."""

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        super().__init__(name, config)
        self.tools: dict[str, callable] = {}

    def register_tool(self, name: str, func: callable):
        self.tools[name] = func

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        tool_name = input_data.get("tool", "")
        tool_args = input_data.get("args", {})

        if tool_name in self.tools:
            try:
                result = self.tools[tool_name](**tool_args)
                return {"result": result, "success": True}
            except Exception as e:
                return {"result": None, "success": False, "error": str(e)}
        else:
            return {"result": None, "success": False, "error": f"Unknown tool: {tool_name}"}


class RouterAgent(BaseAgent):
    """Agent that routes messages based on conditions."""

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        super().__init__(name, config)
        self.routes: dict[str, str] = config.get("routes", {}) if config else {}

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        condition = input_data.get("condition", "")
        target = self.routes.get(condition, self.routes.get("default", ""))

        if target and self.bus:
            self._send_message("routing", target, input_data)

        return {"routed_to": target, "success": bool(target)}


class AggregateAgent(BaseAgent):
    """Agent that collects and merges outputs from multiple sources."""

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        super().__init__(name, config)

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        sources = input_data.get("sources", [])
        merged = {}
        for src in sources:
            if isinstance(src, dict):
                merged.update(src)
            elif isinstance(src, list):
                merged.setdefault("items", []).extend(src)
            else:
                merged.setdefault("values", []).append(src)

        self._memory_set(f"{self.name}_result", merged)
        return {"merged": merged, "count": len(sources), "success": True}


AGENT_TYPES = {
    "llm": LLMAgent,
    "tool": ToolAgent,
    "router": RouterAgent,
    "aggregate": AggregateAgent,
}


def create_agent(name: str, agent_type: str, config: dict[str, Any]) -> BaseAgent:
    cls = AGENT_TYPES.get(agent_type, LLMAgent)
    return cls(name=name, config=config)
