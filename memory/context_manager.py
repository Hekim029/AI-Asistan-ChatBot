import json
import os


class ContextManager:

    def __init__(self, max_messages: int = 20, save_path: str = "memory/history.json"):
        self._history: list[dict] = []
        self._max_messages = max_messages
        self._save_path = save_path
        self._load()

    def add_message(self, role: str, content: str):
        self._history.append({"role": role, "content": content})
        if len(self._history) > self._max_messages:
            self._history.pop(0)
        self._save()

    def get_history(self) -> list[dict]:
        return self._history.copy()

    def clear(self):
        self._history.clear()
        self._save()

    def _save(self):
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)

    def _load(self):
        if os.path.exists(self._save_path):
            try:
                with open(self._save_path, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
            except Exception:
                self._history = []