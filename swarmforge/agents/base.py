"""Base agent class and built-in agent types."""

from __future__ import annotations
import json
import re
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
        self.input_schema: dict[str, Any] | None = self.config.get("input_schema")
        self.output_schema: dict[str, Any] | None = self.config.get("output_schema")

    def attach(self, memory: SharedMemory, bus: MessageBus):
        self.memory = memory
        self.bus = bus

    @abstractmethod
    def run(self, input_data: dict[str, Any]) -> dict[str, Any]: ...

    def validate_input(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        if not self.input_schema:
            return errors
        required = self.input_schema.get("required", [])
        for field in required:
            if field not in input_data:
                errors.append(f"Missing required input field: {field}")
        properties = self.input_schema.get("properties", {})
        for key, prop in properties.items():
            if key in input_data:
                expected_type = prop.get("type")
                if expected_type == "string" and not isinstance(input_data[key], str):
                    errors.append(f"Field '{key}' must be a string")
                elif expected_type == "number" and not isinstance(input_data[key], (int, float)):
                    errors.append(f"Field '{key}' must be a number")
                elif expected_type == "array" and not isinstance(input_data[key], list):
                    errors.append(f"Field '{key}' must be an array")
                elif expected_type == "object" and not isinstance(input_data[key], dict):
                    errors.append(f"Field '{key}' must be an object")
        return errors

    def validate_output(self, output: dict[str, Any]) -> list[str]:
        errors = []
        if not self.output_schema:
            return errors
        required = self.output_schema.get("required", [])
        for field in required:
            if field not in output:
                errors.append(f"Missing required output field: {field}")
        return errors

    def _memory_get(self, key: str, default: Any = None) -> Any:
        if self.memory:
            return self.memory.get(key, default)
        return default

    def _memory_set(self, key: str, value: Any):
        if self.memory:
            self.memory.set(key, value, source=self.name)

    def _send_message(self, channel: str, receiver: str, payload: Any) -> str:
        if self.bus:
            return self.bus.send(
                Message(
                    channel=channel,
                    sender=self.name,
                    receiver=receiver,
                    payload=payload,
                )
            )
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
                headers=headers,
                json=payload,
                timeout=120,
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
            return {
                "result": None,
                "success": False,
                "error": f"Unknown tool: {tool_name}",
            }


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


class PythonAgent(BaseAgent):
    """Agent that executes Python code snippets."""

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        super().__init__(name, config)
        self.allowed_modules = self.config.get("allowed_modules", ["json", "math", "re"])

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        code = input_data.get("code", "")
        if not code:
            return {"response": "", "success": False, "error": "No code provided"}

        safe_globals = {"__builtins__": {}}
        for mod_name in self.allowed_modules:
            try:
                import importlib

                safe_globals[mod_name] = importlib.import_module(mod_name)
            except ImportError:
                pass

        try:
            exec_result = {}
            safe_locals = {"input_data": input_data, "result": exec_result}
            exec(code, safe_globals, safe_locals)
            result = safe_locals.get("result", exec_result)
            return {
                "response": json.dumps(result, default=str),
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {"response": "", "success": False, "error": f"Execution error: {e}"}


class HTTPAgent(BaseAgent):
    """Agent that makes HTTP requests."""

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        super().__init__(name, config)
        self.base_url = self.config.get("base_url", "")
        self.default_headers = self.config.get("headers", {})

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        method = input_data.get("method", "GET").upper()
        url = input_data.get("url", "")
        if not url and self.base_url:
            url = self.base_url
        if not url:
            return {"response": "", "success": False, "error": "No URL provided"}

        headers = {**self.default_headers, **input_data.get("headers", {})}
        payload = input_data.get("payload")
        timeout = input_data.get("timeout", 30)

        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            try:
                body = resp.json()
            except ValueError:
                body = resp.text
            return {
                "response": json.dumps(body, default=str)
                if isinstance(body, (dict, list))
                else str(body),
                "status_code": resp.status_code,
                "success": True,
            }
        except Exception as e:
            return {"response": "", "success": False, "error": str(e)}


class ConditionalAgent(BaseAgent):
    """Agent that routes based on input content matching patterns."""

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        super().__init__(name, config)
        self.routes: dict[str, str] = self.config.get("routes", {})
        self.match_field = self.config.get("match_field", "input")
        self.match_type = self.config.get("match_type", "contains")

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        text = input_data.get(self.match_field, "")
        if isinstance(text, dict):
            text = json.dumps(text)
        text = str(text).lower()

        matched_route = self.routes.get("default", "")

        for pattern, route in self.routes.items():
            if pattern == "default":
                continue
            if self.match_type == "contains" and pattern.lower() in text:
                matched_route = route
                break
            elif self.match_type == "regex" and re.search(pattern, text):
                matched_route = route
                break
            elif self.match_type == "exact" and pattern.lower() == text:
                matched_route = route
                break

        if matched_route and self.bus:
            self._send_message("routing", matched_route, input_data)

        return {"routed_to": matched_route, "success": bool(matched_route)}


AGENT_TYPES = {
    "llm": LLMAgent,
    "tool": ToolAgent,
    "router": RouterAgent,
    "aggregate": AggregateAgent,
    "python": PythonAgent,
    "http": HTTPAgent,
    "conditional": ConditionalAgent,
}


def create_agent(name: str, agent_type: str, config: dict[str, Any]) -> BaseAgent:
    cls = AGENT_TYPES.get(agent_type, LLMAgent)
    return cls(name=name, config=config)
