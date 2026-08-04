"""Açık ve risksiz komutları API kullanmadan yerel araçlara yönlendirir."""

from __future__ import annotations

import re


def _normalize(text: str) -> str:
    value = " ".join((text or "").casefold().strip().split())
    return value.strip(" .?!,;:")


def detect_local_tool(message: str) -> tuple[str, dict] | None:
    """Yalnızca anlamı kesin listeleme/özet komutlarında sonuç döndürür."""
    text = _normalize(message)
    if not text:
        return None

    if text in {
        "günlük özet", "günlük özetimi göster", "günlük özetimi ver",
        "bugünün özeti", "bugünkü özetimi ver",
    }:
        return "get_daily_briefing", {"city": "İstanbul"}

    if text in {
        "görevlerim", "görevlerimi göster", "görevlerimi listele",
        "yapılacaklar", "yapılacaklarımı göster", "bekleyen görevlerim",
    }:
        return "list_tasks", {}

    if text in {
        "hatırlatıcılarım", "hatırlatıcılarımı göster",
        "hatırlatıcılarımı listele", "bekleyen hatırlatıcılarım",
    }:
        return "list_reminders", {}

    if text in {
        "notlarım", "notlarımı göster", "notlarımı listele",
        "kayıtlı notlarım",
    }:
        return "list_notes", {"query": ""}

    note_query = re.fullmatch(
        r"(.+?) hakkındaki notlarımı (?:göster|listele)", text
    )
    if note_query:
        return "list_notes", {"query": note_query.group(1).strip()}

    if text in {
        "benim hakkımda ne biliyorsun", "hafızanda ne var",
        "hafızanı göster", "beni nasıl tanıyorsun",
    }:
        return "list_user_memory", {}

    if text in {
        "diğer pencerede ne oldu", "diğer sohbetlerde ne oldu",
        "diğer pencerenin sonucunu göster", "ortak çalışma durumunu göster",
        "diğer çalışmalarımı göster",
    }:
        return "get_shared_activity", {"limit": 12}

    note_match = re.fullmatch(r"(?:not al|not ekle)\s*:\s*(.+)", text)
    if note_match:
        return "add_note", {"text": note_match.group(1).strip(), "tags": []}

    task_match = re.fullmatch(
        r"(?:görev ekle\s*:\s*|yapılacaklara\s+)(.+?)(?:\s+ekle)?", text
    )
    if task_match:
        title = task_match.group(1).strip()
        return "add_task", {"title": title, "due_at": ""}

    complete_match = re.fullmatch(r"(.+?)\s+görevini\s+tamamla", text)
    if complete_match:
        return "complete_task", {
            "task_id": "",
            "query": complete_match.group(1).strip(),
        }

    weather_match = re.fullmatch(
        r"([a-zçğıöşüâîû\s]+?)(?:'?(?:da|de|ta|te))?\s+hava durumu(?:nu)?(?: göster)?",
        text,
    )
    if weather_match:
        city = weather_match.group(1).strip()
        if city not in {"bugün", "yarın", "şu an", "hava"}:
            return "get_weather", {"city": city.title(), "period": "today"}

    file_match = re.fullmatch(
        r"(?:dosya oku|dosyayı oku|bu dosyayı incele)\s*:\s*(.+)", text
    )
    if file_match:
        return "read_text_file", {"path": file_match.group(1).strip()}

    return None


def clarification_for(message: str) -> str | None:
    """İşlem niyeti açık fakat zorunlu alanları eksik olan komutları yakalar."""
    text = _normalize(message)
    if text in {"not al", "not ekle", "bir not ekle"}:
        return "Elbette. Not olarak hangi metni kaydetmemi istersin?"
    if text in {"görev ekle", "yapılacaklara ekle", "yeni görev"}:
        return "Görevin başlığı ne olsun? İstersen son tarihini de yazabilirsin."
    if text in {
        "hatırlatıcı oluştur", "hatırlatıcı ekle", "bana hatırlat",
        "bir hatırlatıcı kur",
    }:
        return "Neyi, hangi tarih ve saatte hatırlatmamı istersin?"
    if text in {"mail gönder", "e-posta gönder", "bir mail gönder"}:
        return "Maili kime göndereyim? Alıcıyı, konuyu ve mesajı yazman gerekiyor."
    if text in {"dosyayı sil", "bir dosya sil", "dosya sil"}:
        return "Hangi dosyayı silmemi istiyorsun? Dosya adını ve konumunu yazmalısın."
    if text in {"hava durumu", "havayı göster"}:
        return "Hangi şehrin hava durumuna bakayım?"
    if text in {"dosya oku", "dosyayı oku", "dosyayı incele"}:
        return "İncelememi istediğin metin veya kod dosyasının tam yolunu yazmalısın."
    return None


def pending_slot_for(message: str) -> str | None:
    """Netleştirme cevabının hangi yerel işleme ait olduğunu döndürür."""
    text = _normalize(message)
    if text in {"not al", "not ekle", "bir not ekle"}:
        return "note"
    if text in {"görev ekle", "yapılacaklara ekle", "yeni görev"}:
        return "task"
    if text in {"hava durumu", "havayı göster"}:
        return "weather"
    if text in {"dosya oku", "dosyayı oku", "dosyayı incele"}:
        return "file"
    return None
