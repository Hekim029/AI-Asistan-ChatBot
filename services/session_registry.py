"""Sohbet oturumlarının kullanıcı tarafından verilen kalıcı adlarını saklar."""

import json
import os

from utils.config import MEMORY_DIR


class SessionRegistry:
    def __init__(self, save_path: str | None = None):
        self.save_path = save_path or os.path.join(MEMORY_DIR, "session_names.json")
        self._names = {}
        self._load()

    def name_for(self, session_id: str, fallback: str = "") -> str:
        return self._names.get(session_id) or fallback or session_id

    def rename(self, session_id: str, name: str) -> str:
        clean = " ".join((name or "").strip().split())[:50]
        if not clean:
            raise ValueError("Sohbet adı boş olamaz.")
        self._names[session_id] = clean
        self._save()
        return clean

    def _load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                self._names = {str(k): str(v) for k, v in data.items() if v}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._names = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        temp = self.save_path + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(self._names, handle, ensure_ascii=False, indent=2)
        os.replace(temp, self.save_path)
