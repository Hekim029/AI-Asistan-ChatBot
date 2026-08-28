"""Qt/Windows yerel konuşma motoruyla API kullanmadan sesli yanıt üretir."""

from __future__ import annotations

import re
import unicodedata

from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtTextToSpeech import QTextToSpeech
from services.security import redact_sensitive_data


MAX_SPOKEN_CHARS = 900


def prepare_spoken_text(text: object, *, max_chars: int = MAX_SPOKEN_CHARS) -> str:
    """Markdown/kod ağırlıklı yanıtı konuşmaya uygun kısa düz metne çevirir."""
    value = redact_sensitive_data(str(text or ""))
    value = re.sub(
        r"```.*?```",
        " Kod bloğunu ekranda gösterdim. ",
        value,
        flags=re.S,
    )
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", value, flags=re.I)
    value = re.sub(r"https?://\S+", " bağlantı ", value, flags=re.I)
    value = re.sub(r"^\s*(?:#{1,6}|[-*•]+|\d+[.)])\s*", "", value, flags=re.M)
    value = re.sub(r"[*_~>|]", " ", value)
    value = re.sub(r"(?im)^\s*(?:SHA-?256|ONAY_GEREKLİ)\s*:.*$", "", value)
    value = re.sub(
        r"\b(?:ONAY_GEREKLİ|confirm_pending_action|cancel_pending_action)\b",
        "",
        value,
        flags=re.I,
    )
    value = "".join(
        character
        for character in value
        if unicodedata.category(character) not in {"So", "Cs"}
    )
    value = re.sub(r"\s+", " ", value).strip()
    limit = max(120, min(int(max_chars), MAX_SPOKEN_CHARS))
    if len(value) <= limit:
        return value
    shortened = value[: limit - 36].rstrip()
    sentence_end = max(shortened.rfind("."), shortened.rfind("!"), shortened.rfind("?"))
    if sentence_end >= limit // 2:
        shortened = shortened[: sentence_end + 1]
    return shortened + " Yanıtın devamı ekranda."


class SpeechOutputManager(QObject):
    """Tüm sohbet pencerelerinin paylaştığı, çakışmayan tek ses yöneticisi."""

    state_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        *,
        auto_speak: bool = False,
        voice_id: str = "",
        rate: float = 0.0,
        volume: float = 0.85,
        engine_names: tuple[str, ...] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.auto_speak = bool(auto_speak)
        self.voice_id = str(voice_id or "")[:300]
        self.rate = max(-1.0, min(float(rate), 1.0))
        self.volume = max(0.0, min(float(volume), 1.0))
        self._tts = None
        self._voice_rows: list[dict] = []
        self._current_text = ""
        self._status_message = "Ses motoru henüz hazırlanmadı."
        self._engine_names = (
            tuple(str(name)[:40] for name in engine_names)
            if engine_names is not None else None
        )

    @property
    def is_speaking(self) -> bool:
        return bool(
            self._tts
            and self._tts.state() in {
                QTextToSpeech.State.Speaking,
                QTextToSpeech.State.Synthesizing,
                QTextToSpeech.State.Paused,
            }
        )

    @property
    def current_text(self) -> str:
        return self._current_text

    def configure(
        self, *, auto_speak: bool, voice_id: str, rate: float, volume: float
    ) -> None:
        self.auto_speak = bool(auto_speak)
        self.voice_id = str(voice_id or "")[:300]
        self.rate = max(-1.0, min(float(rate), 1.0))
        self.volume = max(0.0, min(float(volume), 1.0))
        if self._ensure_engine():
            self._apply_configuration()

    @staticmethod
    def _voice_key(voice) -> str:
        return "|".join((
            voice.locale().name(),
            voice.name(),
            voice.gender().name,
            voice.age().name,
        ))

    def _collect_voices(self, engine) -> list[dict]:
        rows = {}
        original_locale = engine.locale()
        for locale in engine.availableLocales():
            engine.setLocale(locale)
            for voice in engine.availableVoices():
                key = self._voice_key(voice)
                rows[key] = {
                    "id": key,
                    "name": voice.name(),
                    "locale": voice.locale().name(),
                    "gender": voice.gender().name,
                    "voice": voice,
                }
        engine.setLocale(original_locale)
        return sorted(
            rows.values(),
            key=lambda row: (
                0 if row["locale"].casefold().startswith("tr") else 1,
                row["locale"].casefold(),
                row["name"].casefold(),
            ),
        )

    def _ensure_engine(self) -> bool:
        if self._tts is not None:
            return bool(self._voice_rows)
        if QCoreApplication.instance() is None:
            self._status_message = "Ses motoru için uygulama henüz hazır değil."
            return False

        available = list(QTextToSpeech.availableEngines())
        if self._engine_names is not None:
            ordered = [name for name in self._engine_names if name in available]
        else:
            ordered = [name for name in ("sapi", "winrt") if name in available]
            ordered.extend(
                name for name in available if name not in ordered and name != "mock"
            )
        ready_without_voice = None
        fallback_with_voices = None
        for engine_name in ordered:
            candidate = QTextToSpeech(engine_name, self)
            if candidate.state() == QTextToSpeech.State.Error:
                candidate.deleteLater()
                continue
            voices = self._collect_voices(candidate)
            if voices:
                if any(
                    row["locale"].casefold().startswith("tr") for row in voices
                ):
                    self._tts = candidate
                    self._voice_rows = voices
                    break
                if fallback_with_voices is None:
                    fallback_with_voices = (candidate, voices)
                else:
                    candidate.deleteLater()
                continue
            if ready_without_voice is None:
                ready_without_voice = candidate
            else:
                candidate.deleteLater()

        if self._tts is None and fallback_with_voices is not None:
            self._tts, self._voice_rows = fallback_with_voices
            fallback_with_voices = None

        if (
            self._tts is not None
            and ready_without_voice is not None
            and ready_without_voice is not self._tts
        ):
            ready_without_voice.deleteLater()
        if fallback_with_voices is not None:
            fallback_with_voices[0].deleteLater()

        if self._tts is None and ready_without_voice is not None:
            self._tts = ready_without_voice
            self._voice_rows = []
        if self._tts is None:
            self._status_message = "Windows konuşma motoru başlatılamadı."
            return False
        self._tts.stateChanged.connect(self._on_engine_state)
        self._tts.setRate(self.rate)
        self._tts.setVolume(self.volume)
        if not self._voice_rows:
            self._status_message = (
                "Windows'ta Heko'nun kullanabileceği bir konuşma sesi bulunamadı."
            )
            return False
        self._apply_configuration()
        self._status_message = (
            (
                f"{self._tts.engine()} motoru hazır; "
                f"{len(self._voice_rows)} ses bulundu."
            )
            if any(row["locale"].casefold().startswith("tr") for row in self._voice_rows)
            else (
                f"{self._tts.engine()} motoru hazır ancak Türkçe konuşma sesi "
                "bulunamadı. Türkçe telaffuz için Windows'a Türkçe ses ekle."
            )
        )
        return True

    def _apply_configuration(self) -> None:
        if not self._tts or not self._voice_rows:
            return
        selected = next(
            (row for row in self._voice_rows if row["id"] == self.voice_id),
            self._voice_rows[0],
        )
        self.voice_id = selected["id"]
        self._tts.setVoice(selected["voice"])
        self._tts.setRate(self.rate)
        self._tts.setVolume(self.volume)

    def voice_options(self) -> list[dict]:
        self._ensure_engine()
        return [
            {key: row[key] for key in ("id", "name", "locale", "gender")}
            for row in self._voice_rows
        ]

    def status(self) -> dict:
        available = self._ensure_engine()
        turkish_available = any(
            row["locale"].casefold().startswith("tr") for row in self._voice_rows
        )
        return {
            "available": available,
            "turkish_available": turkish_available,
            "message": self._status_message,
            "engine": self._tts.engine() if self._tts else "",
            "voices": len(self._voice_rows),
        }

    def speak(self, text: object) -> tuple[bool, str]:
        spoken = prepare_spoken_text(text)
        if not spoken:
            return False, "Seslendirilebilecek bir metin bulunamadı."
        if not self._ensure_engine():
            message = self._status_message
            self.error_occurred.emit(message)
            return False, message
        if self.is_speaking:
            self._tts.stop()
        self._apply_configuration()
        self._current_text = spoken
        self._tts.say(spoken)
        return True, "Seslendirme başladı."

    def toggle(self, text: object) -> tuple[bool, str]:
        spoken = prepare_spoken_text(text)
        if self.is_speaking and spoken == self._current_text:
            self.stop()
            return True, "Seslendirme durduruldu."
        return self.speak(spoken)

    def stop(self) -> None:
        if self._tts and self.is_speaking:
            self._tts.stop()
        self._current_text = ""

    def _on_engine_state(self, state) -> None:
        if state in {
            QTextToSpeech.State.Speaking,
            QTextToSpeech.State.Synthesizing,
        }:
            self.state_changed.emit("speaking")
        elif state == QTextToSpeech.State.Paused:
            self.state_changed.emit("paused")
        elif state == QTextToSpeech.State.Error:
            message = self._tts.errorString() or "Ses motorunda bir hata oluştu."
            self._status_message = message
            self.state_changed.emit("error")
            self.error_occurred.emit(message)
        else:
            self._current_text = ""
            self.state_changed.emit("ready")
