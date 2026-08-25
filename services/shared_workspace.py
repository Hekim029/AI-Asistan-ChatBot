"""Sohbet oturumlarının birbirinin sonuçlarını görebildiği ortak olay deposu."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime

from utils.config import MEMORY_DIR
from services.security import (
    bounded_json_load,
    redact_sensitive_data,
    secure_write_json,
)


class SharedWorkspace:
    def __init__(self, save_path: str | None = None):
        self.save_path = save_path or os.path.join(MEMORY_DIR, "shared_workspace.json")
        self._lock = threading.RLock()
        self._events: list[dict] = []
        self._load()

    def publish(self, session_id: str, kind: str, title: str, content: str) -> dict:
        event = {
            "id": uuid.uuid4().hex[:10],
            "session_id": session_id,
            "kind": kind,
            "title": redact_sensitive_data((title or kind).strip())[:300],
            "content": redact_sensitive_data((content or "").strip())[:6000],
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        with self._lock:
            self._events.append(event)
            self._events = self._events[-300:]
            self._save()
        return dict(event)

    def recent(self, limit: int = 20, exclude_session: str = "") -> list[dict]:
        with self._lock:
            values = [dict(item) for item in self._events]
        if exclude_session:
            values = [item for item in values if item.get("session_id") != exclude_session]
        return list(reversed(values[-max(1, limit):]))

    def formatted_context(self, session_id: str, limit: int = 8) -> str:
        events = self.recent(limit=limit, exclude_session=session_id)
        if not events:
            return ""
        lines = ["Diğer açık/önceki sohbetlerden ilgili son çalışma etkinlikleri:"]
        for item in reversed(events):
            lines.append(
                f"- [{item.get('session_id')}] {item.get('title')}: "
                f"{item.get('content', '')[:500]}"
            )
        return "\n".join(lines)

    def _load(self):
        try:
            data = bounded_json_load(self.save_path)
            if isinstance(data, list):
                self._events = [item for item in data if isinstance(item, dict)]
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
            self._events = []

    def _save(self):
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        secure_write_json(self.save_path, self._events)
