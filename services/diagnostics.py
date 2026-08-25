"""Yerel kurulum ve bağlantı ön-koşullarını denetler."""

from __future__ import annotations

import importlib.util
import os
import shutil

import utils.config as config


def run_diagnostics() -> list[dict]:
    checks = []

    def add(name: str, ok: bool, detail: str):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add(
        "Groq API anahtarı",
        bool(config.GROQ_API_KEY),
        "Hazır" if config.GROQ_API_KEY else ".env içinde GROQ_API_KEY eksik",
    )
    credentials = os.path.join(config.BASE_DIR, "credentials.json")
    token = os.path.join(config.MEMORY_DIR, "token.dat")
    add(
        "Google OAuth kimliği",
        os.path.exists(credentials),
        "Hazır" if os.path.exists(credentials) else "credentials.json eksik",
    )
    add(
        "Google oturumu",
        os.path.exists(token),
        "Bağlı" if os.path.exists(token) else "İlk kullanımda giriş istenecek",
    )
    add(
        "FFmpeg",
        bool(shutil.which("ffmpeg")),
        shutil.which("ffmpeg") or "PATH içinde bulunamadı",
    )
    add(
        "Mikrofon altyapısı",
        importlib.util.find_spec("sounddevice") is not None,
        "sounddevice hazır" if importlib.util.find_spec("sounddevice") else "sounddevice eksik",
    )
    add(
        "Google API kitaplıkları",
        importlib.util.find_spec("googleapiclient") is not None,
        "Hazır" if importlib.util.find_spec("googleapiclient") else "Paketler eksik",
    )
    add(
        "Hatırlatıcı deposu",
        os.access(config.MEMORY_DIR, os.W_OK),
        config.MEMORY_DIR,
    )
    return checks
