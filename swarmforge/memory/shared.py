"""Shared memory layer — in-process key-value + optional Redis backend."""

from __future__ import annotations
import threading
import json
from typing import Any


class SharedMemory:
    """Thread-safe shared memory for agent communication."""

    def __init__(self, backend: str = "local", redis_url: str = ""):
        self.backend = backend
        self._store: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._history: list[dict] = []
        self._listeners: dict[str, list] = {}
        self._redis = None

        if backend == "redis" and redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url)
            except ImportError:
                self.backend = "local"

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._store.get(key, default)

    def set(self, key: str, value: Any, source: str = ""):
        with self._lock:
            old = self._store.get(key)
            self._store[key] = value
            self._history.append({
                "key": key,
                "value": self._serialize(value),
                "source": source,
                "op": "set",
            })
            if old is not None and old != value:
                self._history.append({
                    "key": key,
                    "old": self._serialize(old),
                    "new": self._serialize(value),
                    "source": source,
                    "op": "update",
                })

        self._notify_listeners(key, value)

        if self._redis:
            try:
                self._redis.set(f"swarmforge:{key}", json.dumps(self._serialize(value)))
            except Exception:
                pass

    def delete(self, key: str, source: str = ""):
        with self._lock:
            self._store.pop(key, None)
            self._history.append({"key": key, "source": source, "op": "delete"})

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._store.keys())

    def items(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._store)

    def get_history(self, key: str | None = None) -> list[dict]:
        if key:
            return [h for h in self._history if h["key"] == key]
        return list(self._history)

    def subscribe(self, key: str, callback):
        with self._lock:
            self._listeners.setdefault(key, []).append(callback)

    def _notify_listeners(self, key: str, value: Any):
        with self._lock:
            listeners = self._listeners.get(key, [])
        for cb in listeners:
            try:
                cb(key, value)
            except Exception:
                pass

    def _serialize(self, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._serialize(v) for v in value]
        return str(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._store)
