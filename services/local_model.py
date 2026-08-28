"""Ollama uyumlu, isteğe bağlı yerel sohbet modeli istemcisi."""

from __future__ import annotations

from pathlib import Path
import re

import requests

from services.security import (
    bounded_json_load,
    safe_error,
    secure_write_json,
    validate_loopback_url,
)


MODEL_PATTERN = re.compile(r"[A-Za-z0-9._:/-]{1,120}")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def validate_model_name(model: str, *, allow_empty: bool = True) -> str:
    candidate = (model or "").strip()
    if not candidate and allow_empty:
        return ""
    if not MODEL_PATTERN.fullmatch(candidate):
        raise ValueError(
            "Model adı yalnızca harf, rakam ve . _ : / - karakterlerini içerebilir."
        )
    return candidate


def save_local_model_settings(path: str | Path, model: str, base_url: str) -> dict:
    """Yerel model tercihini hassas olmayan, atomik bir yerel kayda yazar."""
    clean_model = validate_model_name(model)
    clean_url = validate_loopback_url(base_url).rstrip("/")
    data = {"model": clean_model, "base_url": clean_url}
    secure_write_json(path, data)
    return data


def load_local_model_settings(
    path: str | Path,
    *,
    default_model: str = "",
    default_url: str = DEFAULT_OLLAMA_URL,
) -> dict:
    target = Path(path)
    fallback = {
        "model": validate_model_name(default_model),
        "base_url": validate_loopback_url(default_url).rstrip("/"),
    }
    if not target.exists():
        return fallback
    try:
        data = bounded_json_load(target, max_bytes=16_384)
        if not isinstance(data, dict):
            return fallback
        return {
            "model": validate_model_name(data.get("model", "")),
            "base_url": validate_loopback_url(
                data.get("base_url", fallback["base_url"])
            ).rstrip("/"),
        }
    except (OSError, TypeError, ValueError):
        return fallback


def probe_ollama(model: str, base_url: str, timeout: float = 4.0) -> dict:
    """Ollama'ya yalnızca loopback üzerinden bağlanıp kurulu modelleri listeler."""
    clean_model = validate_model_name(model)
    clean_url = validate_loopback_url(base_url).rstrip("/")
    session = requests.Session()
    session.trust_env = False
    try:
        response = session.get(
            f"{clean_url}/api/tags",
            timeout=max(1.0, min(float(timeout), 10.0)),
            allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("models", []) if isinstance(payload, dict) else []
        models = sorted(
            {
                str(item.get("name", "")).strip()
                for item in rows
                if isinstance(item, dict) and item.get("name")
            },
            key=str.casefold,
        )
    except (requests.RequestException, ValueError, TypeError) as exc:
        return {
            "ok": False,
            "message": f"Ollama bağlantısı kurulamadı: {safe_error(exc)}",
            "models": [],
        }

    if clean_model and clean_model.casefold() not in {
        item.casefold() for item in models
    }:
        return {
            "ok": False,
            "message": (
                f"Ollama çalışıyor ancak ‘{clean_model}’ bu bilgisayarda yüklü değil."
            ),
            "models": models,
        }
    if clean_model:
        message = f"Bağlantı hazır. ‘{clean_model}’ kullanılabilir."
    elif models:
        message = "Ollama çalışıyor. Kullanmak istediğin modeli seçebilirsin."
    else:
        message = "Ollama çalışıyor ancak henüz yüklü bir model bulunamadı."
    return {"ok": True, "message": message, "models": models}


class LocalModelClient:
    def __init__(self, model: str, base_url: str = DEFAULT_OLLAMA_URL):
        candidate_model = (model or "").strip()
        self.model = candidate_model if MODEL_PATTERN.fullmatch(candidate_model) else ""
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
