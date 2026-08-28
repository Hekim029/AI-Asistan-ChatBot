"""Yerel kurulum ve bağlantı ön-koşullarını denetler."""

from __future__ import annotations

import importlib.util
import os

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
        "Mikrofon altyapısı",
        importlib.util.find_spec("sounddevice") is not None,
        "sounddevice hazır" if importlib.util.find_spec("sounddevice") else "sounddevice eksik",
    )
    speech_module = importlib.util.find_spec("PySide6.QtTextToSpeech")
    speech_engines = []
    if speech_module is not None:
        try:
            from PySide6.QtTextToSpeech import QTextToSpeech
            speech_engines = [
                name for name in QTextToSpeech.availableEngines() if name != "mock"
            ]
        except (ImportError, RuntimeError):
            speech_engines = []
    add(
        "Yerel sesli yanıt altyapısı",
        bool(speech_engines),
        (
            "Windows motorları: " + ", ".join(speech_engines)
            if speech_engines else "SAPI/WinRT konuşma motoru bulunamadı"
        ),
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
    try:
        from evals.evaluator import run_offline_suite, summarize_results
        quality = summarize_results(run_offline_suite())
        add(
            "Yerel kalite senaryoları",
            quality["failed"] == 0,
            (
                f"%{quality['score']:.1f} — {quality['passed']}/"
                f"{quality['measured']} senaryo başarılı"
            ),
        )
    except (OSError, TypeError, ValueError) as exc:
        from services.security import safe_error
        add("Yerel kalite senaryoları", False, safe_error(exc))
    return checks
