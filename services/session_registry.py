"""Sohbet oturumlarının kullanıcı tarafından verilen kalıcı adlarını saklar."""

import json
import os

from utils.config import MEMORY_DIR
from services.security import bounded_json_load, secure_write_json


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
            data = bounded_json_load(self.save_path, max_bytes=512_000)
            if isinstance(data, dict):
                self._names = {str(k): str(v) for k, v in data.items() if v}
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
            self._names = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        secure_write_json(self.save_path, self._names)
