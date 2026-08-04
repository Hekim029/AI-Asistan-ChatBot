"""Yerel görevlerden sabah/akşam özeti üretir ve gösterim durumunu saklar."""

from __future__ import annotations

import json
import os
from datetime import datetime

from utils.config import MEMORY_DIR


class DailyBriefingService:
    MORNING_HOURS = range(5, 12)
    EVENING_HOURS = range(18, 24)

    DEFAULT_SETTINGS = {
        "enabled": True,
        "morning_enabled": True,
        "evening_enabled": True,
        "city": "İstanbul",
    }

    def __init__(
        self,
        task_manager,
        reminder_manager,
        state_path: str | None = None,
        config_path: str | None = None,
    ):
        self.tasks = task_manager
        self.reminders = reminder_manager
        self.state_path = state_path or os.path.join(MEMORY_DIR, "daily_briefing_state.json")
        self.config_path = config_path or os.path.join(MEMORY_DIR, "daily_briefing_config.json")

    def get_settings(self) -> dict:
        settings = dict(self.DEFAULT_SETTINGS)
        try:
            with open(self.config_path, "r", encoding="utf-8") as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                settings.update({key: stored[key] for key in settings if key in stored})
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        settings["city"] = str(settings.get("city") or "İstanbul").strip()
        return settings

    def update_settings(self, **changes) -> dict:
        settings = self.get_settings()
        for key in self.DEFAULT_SETTINGS:
            if key in changes:
                settings[key] = changes[key]
        settings["city"] = str(settings.get("city") or "İstanbul").strip()
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        temp = self.config_path + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, ensure_ascii=False, indent=2)
        os.replace(temp, self.config_path)
        return settings

    @classmethod
    def slot_for(cls, now: datetime | None = None) -> str | None:
        current = now or datetime.now().astimezone()
        if current.hour in cls.MORNING_HOURS:
            return "morning"
        if current.hour in cls.EVENING_HOURS:
            return "evening"
        return None

    def should_show(self, now: datetime | None = None) -> bool:
        current = now or datetime.now().astimezone()
        slot = self.slot_for(current)
        if slot is None:
            return False
        settings = self.get_settings()
        if not settings["enabled"] or not settings[f"{slot}_enabled"]:
            return False
        state = self._load_state()
        return state.get(slot) != current.date().isoformat()

    def mark_shown(self, now: datetime | None = None):
        current = now or datetime.now().astimezone()
        slot = self.slot_for(current)
        if slot is None:
            return
        state = self._load_state()
        state[slot] = current.date().isoformat()
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        temp = self.state_path + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
        os.replace(temp, self.state_path)

    def build(self, now: datetime | None = None, city: str | None = None) -> str:
        current = now or datetime.now().astimezone()
        slot = self.slot_for(current) or "morning"
        city = (city or self.get_settings()["city"]).strip()
        tasks = self.tasks.pending_tasks()
        reminders = self.reminders.pending()

        if slot == "evening":
            heading = "Akşam özeti"
            intro = "Günü kapatmadan önce kalanlara kısa bir bakalım."
        else:
            heading = "Günaydın — günlük planın"
            intro = "Bugün için öne çıkanlar burada."

        lines = [heading, intro, "", f"Bekleyen görev: {len(tasks)}"]
        for item in tasks[:5]:
            due = self._task_due(item.get("due_at", ""), current)
            lines.append(f"• {item['title']}" + (f" — {due}" if due else ""))
        if not tasks:
            lines.append("• Bekleyen görev yok.")

        lines.extend(["", f"Yaklaşan hatırlatıcı: {len(reminders)}"])
        for item in reminders[:5]:
            lines.append(f"• {self._format_due(item['due_at'])} — {item['text']}")
        if not reminders:
            lines.append("• Yaklaşan hatırlatıcı yok.")

        if slot == "morning":
            try:
                from services.weather_service import get_weather

                weather = get_weather(city, "today")
            except Exception:
                weather = "Hava bilgisi şu anda alınamadı."
            lines.extend(["", weather])

        return "\n".join(lines)

    @staticmethod
    def _format_due(value: str) -> str:
        if not value:
            return ""
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%d.%m %H:%M")
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _task_due(value: str, now: datetime) -> str:
        if not value:
            return ""
        try:
            due = datetime.fromisoformat(value).astimezone()
            label = "GECİKMİŞ" if due < now.astimezone() else "son tarih"
            return f"{label}: {due.strftime('%d.%m %H:%M')}"
        except (TypeError, ValueError):
            return str(value)

    def _load_state(self) -> dict:
        try:
            with open(self.state_path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
