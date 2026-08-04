"""Kalıcı yerel hatırlatıcı deposu."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime

from utils.config import MEMORY_DIR


class ReminderManager:
    def __init__(self, save_path: str | None = None):
        self._save_path = save_path or os.path.join(MEMORY_DIR, "reminders.json")
        self._lock = threading.RLock()
        self._items: list[dict] = []
        self._load()

    @staticmethod
    def _parse_due(value: str) -> datetime:
        text = (value or "").strip().replace("Z", "+00:00")
        due = datetime.fromisoformat(text)
        if due.tzinfo is None:
            due = due.astimezone()
        return due

    def add(self, text: str, due_at: str) -> dict:
        message = (text or "").strip()
        if not message:
            raise ValueError("Hatırlatıcı metni boş olamaz.")

        due = self._parse_due(due_at)
        if due <= datetime.now().astimezone():
            raise ValueError("Hatırlatıcı zamanı gelecekte olmalı.")

        item = {
            "id": uuid.uuid4().hex[:8],
            "text": message,
            "due_at": due.isoformat(timespec="seconds"),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": "pending",
        }
        with self._lock:
            self._items.append(item)
            self._save()
        return dict(item)

    def pending(self) -> list[dict]:
        with self._lock:
            items = [dict(item) for item in self._items if item["status"] == "pending"]
        return sorted(items, key=lambda item: self._parse_due(item["due_at"]))

    def cancel(self, reminder_id: str = "", query: str = "") -> dict | None:
        target_id = (reminder_id or "").strip().casefold()
        target_query = (query or "").strip().casefold()
        with self._lock:
            for item in self._items:
                if item["status"] != "pending":
                    continue
                id_match = target_id and item["id"].casefold() == target_id
                text_match = target_query and target_query in item["text"].casefold()
                if id_match or text_match:
                    item["status"] = "cancelled"
                    item["cancelled_at"] = datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    )
                    self._save()
                    return dict(item)
        return None

    def pop_due(self, now: datetime | None = None) -> list[dict]:
        current = now or datetime.now().astimezone()
        if current.tzinfo is None:
            current = current.astimezone()

        due_items = []
        with self._lock:
            for item in self._items:
                if item["status"] != "pending":
                    continue
                if self._parse_due(item["due_at"]) <= current:
                    item["status"] = "delivered"
                    item["delivered_at"] = current.isoformat(timespec="seconds")
                    due_items.append(dict(item))
            if due_items:
                self._save()
        return due_items

    def _load(self):
        try:
            with open(self._save_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                self._items = [item for item in data if isinstance(item, dict)]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._items = []

    def _save(self):
        os.makedirs(os.path.dirname(self._save_path), exist_ok=True)
        temp_path = self._save_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(self._items, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, self._save_path)
