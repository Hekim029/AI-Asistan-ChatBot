"""Ollama uyumlu, isteğe bağlı yerel sohbet modeli istemcisi."""

from __future__ import annotations

import requests
import re

from services.security import validate_loopback_url


class LocalModelClient:
    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434"):
        candidate_model = (model or "").strip()
        self.model = (
            candidate_model
            if re.fullmatch(r"[A-Za-z0-9._:/-]{1,120}", candidate_model)
            else ""
        )
        self.configuration_error = ""
        if candidate_model and not self.model:
            self.configuration_error = "Yerel model adı geçersiz."
        try:
            self.base_url = validate_loopback_url(base_url).rstrip("/")
        except ValueError as exc:
            self.base_url = ""
            self.configuration_error = str(exc)
        self._session = requests.Session()
        self._session.trust_env = False

    @property
    def enabled(self) -> bool:
        return bool(self.model and self.base_url)

    def chat(self, messages: list[dict]) -> str | None:
        if not self.enabled:
            return None
        clean = [
            {"role": item.get("role", "user"), "content": str(item.get("content", ""))}
            for item in messages
            if item.get("role") in {"system", "user", "assistant"}
        ]
        try:
            response = self._session.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": clean, "stream": False},
                timeout=60,
                allow_redirects=False,
            )
            response.raise_for_status()
            return (response.json().get("message", {}).get("content") or "").strip() or None
        except requests.RequestException:
            return None
