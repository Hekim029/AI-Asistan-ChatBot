"""Ollama uyumlu, isteğe bağlı yerel sohbet modeli istemcisi."""

from __future__ import annotations

import requests


class LocalModelClient:
    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434"):
        self.model = (model or "").strip()
        self.base_url = base_url.rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.model)

    def chat(self, messages: list[dict]) -> str | None:
        if not self.enabled:
            return None
        clean = [
            {"role": item.get("role", "user"), "content": str(item.get("content", ""))}
            for item in messages
            if item.get("role") in {"system", "user", "assistant"}
        ]
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": clean, "stream": False},
                timeout=60,
            )
            response.raise_for_status()
            return (response.json().get("message", {}).get("content") or "").strip() or None
        except requests.RequestException:
            return None
