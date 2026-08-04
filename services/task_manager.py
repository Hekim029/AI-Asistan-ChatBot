"""Kalıcı yerel görev ve kısa not deposu."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime

from utils.config import MEMORY_DIR


class TaskManager:
    _TAG_HINTS = {
        "proje": {
            "proje", "arayüz", "arayüzün", "tasarım", "uygulama", "özellik",
            "renk", "tema", "kod", "python",
        },
        "tasarım": {"arayüz", "arayüzün", "tasarım", "renk", "tema", "görsel"},
    }

    def __init__(self, save_path: str | None = None):
        self._save_path = save_path or os.path.join(MEMORY_DIR, "tasks.json")
        self._lock = threading.RLock()
        self._data = {"tasks": [], "notes": []}
        self._load()

    def add_task(self, title: str, due_at: str = "") -> dict:
        text = (title or "").strip()
        if not text:
            raise ValueError("Görev başlığı boş olamaz.")
        due = ""
        if due_at:
            parsed = datetime.fromisoformat(due_at.strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.astimezone()
            due = parsed.isoformat(timespec="seconds")
        item = {
            "id": uuid.uuid4().hex[:8],
            "title": text,
            "due_at": due,
            "status": "pending",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        with self._lock:
            self._data["tasks"].append(item)
            self._save()
        return dict(item)

    def pending_tasks(self) -> list[dict]:
        with self._lock:
            items = [
                dict(item)
                for item in self._data["tasks"]
                if item.get("status") == "pending"
            ]
        return sorted(items, key=lambda item: (item.get("due_at") or "9999", item["title"]))

    def complete_task(self, task_id: str = "", query: str = "") -> dict | None:
        target_id = (task_id or "").strip().casefold()
        target_query = (query or "").strip().casefold()
        with self._lock:
            for item in self._data["tasks"]:
                if item.get("status") != "pending":
                    continue
                if (
                    target_id and item["id"].casefold() == target_id
                ) or (
                    target_query and target_query in item["title"].casefold()
                ):
                    item["status"] = "completed"
                    item["completed_at"] = datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    )
                    self._save()
                    return dict(item)
        return None

    def add_note(self, text: str, tags: list[str] | None = None) -> dict:
        content = (text or "").strip()
        if not content:
            raise ValueError("Not boş olamaz.")
        normalized = " ".join(content.casefold().split())
        clean_tags = []
        for tag in tags or []:
            value = str(tag).strip().casefold()
            if value and value not in clean_tags:
                clean_tags.append(value)
        content_words = set(normalized.replace("'", " ").split())
        for inferred_tag, hints in self._TAG_HINTS.items():
            if content_words.intersection(hints) and inferred_tag not in clean_tags:
                clean_tags.append(inferred_tag)
        with self._lock:
            for existing in self._data["notes"]:
                existing_text = " ".join(
                    str(existing.get("text", "")).casefold().split()
                )
                if existing_text == normalized:
                    merged_tags = list(existing.get("tags") or [])
                    for tag in clean_tags:
                        if tag not in merged_tags:
                            merged_tags.append(tag)
                    existing["tags"] = merged_tags[:5]
                    self._save()
                    result = dict(existing)
                    result["_duplicate"] = True
                    return result

            item = {
                "id": uuid.uuid4().hex[:8],
                "text": content,
                "tags": clean_tags[:5],
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            self._data["notes"].append(item)
            self._save()
        return dict(item)

    def notes(self, query: str = "") -> list[dict]:
        needle = (query or "").strip().casefold()
        with self._lock:
            items = [dict(item) for item in self._data["notes"]]
        # Önceki sürümlerde oluşmuş aynı içerikli kayıtları görünümde tekilleştir.
        unique = {}
        for item in items:
            key = " ".join(str(item.get("text", "")).casefold().split())
            if key:
                unique[key] = item
        items = list(unique.values())
        if needle:
            related_terms = {needle}
            related_terms.update(self._TAG_HINTS.get(needle, set()))
            matched = [
                item for item in items
                if any(term in item["text"].casefold() for term in related_terms)
                or any(
                    any(
                        term in str(tag).casefold()
                        or str(tag).casefold() in term
                        for term in related_terms
                    )
                    for tag in item.get("tags", [])
                )
            ]
            if matched:
                return list(reversed(matched))
            # Eski/etiketsiz notları görünmez yapma. Kesin eşleşme yoksa
            # son notları "öneri" olarak döndür; UI bunu açıkça belirtir.
            suggestions = list(reversed(items[-5:]))
            for item in suggestions:
                item["_suggestion"] = True
            return suggestions
        return list(reversed(items))

    def _load(self):
        try:
            with open(self._save_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                self._data["tasks"] = list(data.get("tasks") or [])
                self._data["notes"] = list(data.get("notes") or [])
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def _save(self):
        os.makedirs(os.path.dirname(self._save_path), exist_ok=True)
        temp_path = self._save_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, self._save_path)
