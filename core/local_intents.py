"""Açık ve risksiz komutları API kullanmadan yerel araçlara yönlendirir."""

from __future__ import annotations

import re


def _normalize(text: str) -> str:
    value = " ".join((text or "").casefold().strip().split())
    return value.strip(" .?!,;:")


def _detect_new_project_file(message: str) -> tuple[str, dict] | None:
    """Açık yeni kod dosyası komutunu model/kota gerektirmeden hazırlar."""
    raw = str(message or "").strip()
    if not raw:
        return None
    folded = raw.casefold()
    if any(
        phrase in folded
        for phrase in (
            "oluşturma", "oluşturmanı istemiyorum", "sakın oluştur",
            "yazma", "yazmanı istemiyorum",
        )
    ):
        return None

    path_pattern = r"(?P<path>(?:[\w.@+\-]+[\\/])*[\w.@+\-]+\.[A-Za-z0-9]{1,10})"
    natural = re.search(
        path_pattern
        + r"\s+(?:adında\s+)?(?:yeni\s+bir\s+)?dosya(?:sını)?\s+oluştur",
        raw,
        re.I,
    )
    explicit = re.search(
        r"proje\s+dosyası\s+oluştur\s*:\s*" + path_pattern,
        raw,
        re.I,
    )
    match = natural or explicit
    if not match:
        return None

    fenced = re.search(r"```(?:[A-Za-z0-9_+.-]+)?\s*\n?(.*?)```", raw, re.S)
    if fenced:
        content = fenced.group(1).strip("\r\n")
    else:
        inline = re.search(
            r"\biçine\s+(.+?)\s+yaz(?:\s+ve\b|[.!?](?:\s|$)|$)",
            raw,
            re.I | re.S,
        )
        content = inline.group(1).strip() if inline else ""
    if not content:
        return None

    return "update_project_file", {
        "path": match.group("path").replace("\\", "/"),
        "content": content.rstrip() + "\n",
        "expected_sha256": "",
    }


def _detect_project_file_delete(message: str) -> tuple[str, dict] | None:
    """Göreli proje yolu verilen açık silme emrini güvenli araca yönlendirir."""
    raw = str(message or "").strip()
    folded = raw.casefold()
    if any(
        phrase in folded
        for phrase in (
            "silme", "silmeni istemiyorum", "silmek istemiyorum", "sakın sil",
        )
    ):
        return None
    match = re.search(
        r"(?:^|\s)(?P<path>(?:[\w.@+\-]+[\\/])+[\w.@+\-]+\."
        r"[A-Za-z0-9]{1,10})\s+dosyasını\s+"
        r"(?:sil|çöp\s+kutusuna\s+taşı)(?:\s|[.!?]|$)",
        raw,
        re.I,
    )
    if not match:
        return None
    return "delete_project_file", {
        "path": match.group("path").replace("\\", "/")
    }


def detect_local_tool(message: str) -> tuple[str, dict] | None:
    """Yalnızca anlamı kesin listeleme/özet komutlarında sonuç döndürür."""
    project_delete = _detect_project_file_delete(message)
    if project_delete:
        return project_delete
    project_create = _detect_new_project_file(message)
    if project_create:
        return project_create
    document_match = re.fullmatch(
        r"\s*(?:pdf|word|belge|doküman)(?:\s+dosyası)?\s+"
        r"(?:oku|incele)\s*:\s*\"?(.+?\.(?:pdf|docx))\"?\s*",
        str(message or ""),
        re.I | re.S,
    )
    if document_match:
        return "read_document", {
            "path": document_match.group(1).strip().strip('"')
        }
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

    if text in {
        "proje dosyalarını listele", "projedeki dosyaları listele",
        "proje yapısını göster", "kod dosyalarını göster",
    }:
        return "list_project_files", {"query": "", "limit": 120}

    project_file_match = re.fullmatch(
        r"(?:proje dosyası oku|proje dosyasını oku|proje kodunu incele)\s*:\s*(.+)",
        text,
    )
    if project_file_match:
        return "read_project_file", {"path": project_file_match.group(1).strip()}

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
