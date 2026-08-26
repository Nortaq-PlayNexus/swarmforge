"""Message bus — typed channels for agent-to-agent communication."""

from __future__ import annotations
import threading
import queue
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Message:
    channel: str
    sender: str
    receiver: str
    payload: Any
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    msg_id: str = ""
    reply_to: str = ""


class MessageBus:
    """In-process message bus with typed channels."""

    def __init__(self):
        self._queues: dict[str, queue.Queue] = {}
        self._subscribers: dict[str, list] = {}
        self._history: list[Message] = []
        self._lock = threading.Lock()
        self._msg_counter = 0

    def create_channel(self, name: str):
        with self._lock:
            if name not in self._queues:
                self._queues[name] = queue.Queue()

    def send(self, message: Message) -> str:
        self._msg_counter += 1
        message.msg_id = f"msg_{self._msg_counter}"

        with self._lock:
            self._history.append(message)

        if message.channel in self._queues:
            self._queues[message.channel].put(message)

        with self._lock:
            for cb in self._subscribers.get(message.channel, []):
                try:
                    cb(message)
                except Exception:
                    pass

        return message.msg_id

    def receive(self, channel: str, timeout: float = 5.0) -> Message | None:
        if channel not in self._queues:
            return None
        try:
            return self._queues[channel].get(timeout=timeout)
        except queue.Empty:
            return None

    def subscribe(self, channel: str, callback):
        with self._lock:
            self._subscribers.setdefault(channel, []).append(callback)

    def get_history(self, channel: str | None = None) -> list[Message]:
        if channel:
            return [m for m in self._history if m.channel == channel]
        return list(self._history)

    def pending_count(self, channel: str) -> int:
        if channel not in self._queues:
            return 0
        return self._queues[channel].qsize()
