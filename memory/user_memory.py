import json
import os


class UserMemory:

    _SAVE_PATH = "memory/user_memory.json"

    def __init__(self):
        self._memories: list[str] = []
        self._load()

    def add(self, memory: str):
        if memory not in self._memories:
            self._memories.append(memory)
            self._save()

    def get_all(self) -> list[str]:
        return self._memories.copy()

    def clear(self):
        self._memories.clear()
        self._save()

    def formatted(self) -> str:
        if not self._memories:
            return ""
        items = "\n".join(f"- {m}" for m in self._memories)
        return f"Kullanıcı hakkında bildiklerin:\n{items}"

    def _save(self):
        with open(self._SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(self._memories, f, ensure_ascii=False, indent=2)

    def _load(self):
        if os.path.exists(self._SAVE_PATH):
            try:
                with open(self._SAVE_PATH, "r", encoding="utf-8") as f:
                    self._memories = json.load(f)
            except Exception:
                self._memories = []