"""Heko'nun hassas olmayan, cihazda tutulan uygulama tercihleri."""

from __future__ import annotations

from pathlib import Path
import re

from services.security import bounded_json_load, secure_write_json


DEFAULT_APP_SETTINGS = {
    "screen_vision_enabled": False,
    "tts_auto_speak": False,
    "tts_voice_id": "",
    "tts_rate": 0.0,
    "tts_volume": 0.85,
    "assistant_mode": "normal",
    "assistant_prompt": "",
    "accent_color": "#4a9eff",
    "ai_color": "#1e242c",
}

ALLOWED_ASSISTANT_MODES = frozenset({"normal", "eğlenceli", "ciddi", "teknik"})
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
_MAX_PROMPT_LENGTH = 12_000


def load_app_settings(path: str | Path) -> dict:
    """Bozuk veya eksik kayıtta güvenli varsayılanlara geri döner."""
    target = Path(path)
    settings = dict(DEFAULT_APP_SETTINGS)
    if not target.exists():
        return settings
    try:
        data = bounded_json_load(target, max_bytes=16_384)
    except (OSError, TypeError, ValueError):
        return settings
    if not isinstance(data, dict):
        return settings
    if isinstance(data.get("screen_vision_enabled"), bool):
        settings["screen_vision_enabled"] = data["screen_vision_enabled"]
    if isinstance(data.get("tts_auto_speak"), bool):
        settings["tts_auto_speak"] = data["tts_auto_speak"]
    voice_id = data.get("tts_voice_id")
    if isinstance(voice_id, str) and len(voice_id) <= 300:
        settings["tts_voice_id"] = voice_id
    for key, minimum, maximum in (
        ("tts_rate", -1.0, 1.0),
        ("tts_volume", 0.0, 1.0),
    ):
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            settings[key] = max(minimum, min(float(value), maximum))
    mode = data.get("assistant_mode")
    if mode in ALLOWED_ASSISTANT_MODES:
        settings["assistant_mode"] = mode
    prompt = data.get("assistant_prompt")
    if isinstance(prompt, str) and len(prompt) <= _MAX_PROMPT_LENGTH:
        settings["assistant_prompt"] = prompt
    for key in ("accent_color", "ai_color"):
        value = data.get(key)
        if isinstance(value, str) and _HEX_COLOR_PATTERN.fullmatch(value):
            settings[key] = value.lower()
    return settings


def save_app_settings(
    path: str | Path,
    *,
    screen_vision_enabled: bool | None = None,
    tts_auto_speak: bool | None = None,
    tts_voice_id: str | None = None,
    tts_rate: float | None = None,
    tts_volume: float | None = None,
    assistant_mode: str | None = None,
    assistant_prompt: str | None = None,
    accent_color: str | None = None,
    ai_color: str | None = None,
) -> dict:
    """Uygulama tercihlerini atomik ve kısıtlı izinli yerel dosyaya yazar."""
    settings = load_app_settings(path)
    if screen_vision_enabled is not None and not isinstance(screen_vision_enabled, bool):
        raise ValueError("Ekran farkındalığı ayarı doğru/yanlış değeri olmalıdır.")
    if tts_auto_speak is not None and not isinstance(tts_auto_speak, bool):
        raise ValueError("Otomatik seslendirme ayarı doğru/yanlış değeri olmalıdır.")
    if tts_voice_id is not None and (
        not isinstance(tts_voice_id, str) or len(tts_voice_id) > 300
    ):
        raise ValueError("Konuşma sesi seçimi geçersiz.")
    if tts_rate is not None and (
        isinstance(tts_rate, bool) or not isinstance(tts_rate, (int, float))
        or not -1.0 <= float(tts_rate) <= 1.0
    ):
        raise ValueError("Konuşma hızı -1 ile 1 arasında olmalıdır.")
    if tts_volume is not None and (
        isinstance(tts_volume, bool) or not isinstance(tts_volume, (int, float))
        or not 0.0 <= float(tts_volume) <= 1.0
    ):
        raise ValueError("Konuşma ses seviyesi 0 ile 1 arasında olmalıdır.")
    if assistant_mode is not None and assistant_mode not in ALLOWED_ASSISTANT_MODES:
        raise ValueError("Asistan konuşma modu geçersiz.")
    if assistant_prompt is not None and (
        not isinstance(assistant_prompt, str)
        or not assistant_prompt.strip()
        or len(assistant_prompt) > _MAX_PROMPT_LENGTH
    ):
        raise ValueError("Asistan kişiliği boş olamaz ve 12.000 karakteri aşamaz.")
    for label, color in (("Kullanıcı", accent_color), ("Heko", ai_color)):
        if color is not None and (
            not isinstance(color, str) or not _HEX_COLOR_PATTERN.fullmatch(color)
        ):
            raise ValueError(f"{label} mesaj rengi geçersiz.")
    updates = {
        "screen_vision_enabled": screen_vision_enabled,
        "tts_auto_speak": tts_auto_speak,
        "tts_voice_id": tts_voice_id,
        "tts_rate": float(tts_rate) if tts_rate is not None else None,
        "tts_volume": float(tts_volume) if tts_volume is not None else None,
        "assistant_mode": assistant_mode,
        "assistant_prompt": assistant_prompt,
        "accent_color": accent_color.lower() if accent_color is not None else None,
        "ai_color": ai_color.lower() if ai_color is not None else None,
    }
    settings.update({key: value for key, value in updates.items() if value is not None})
    secure_write_json(path, settings)
    return settings
