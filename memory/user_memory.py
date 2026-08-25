import json
import os
import threading
from functools import wraps
from datetime import datetime
from uuid import uuid4
from utils.config import MEMORY_DIR
from services.security import contains_sensitive_data, secure_write_json, safe_error


def _locked(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


class UserMemory:

    _SAVE_PATH = os.path.join(MEMORY_DIR, "user_memory.json")
    _VERSION = 2

    # Hangi anahtar kelimelerin hangi kategoriye işaret ettiği
    _CATEGORY_HINTS = {
        "name":        ["adım", "ismim", "benim adım", "bana ... de", "bana ... diyebilirsin"],
        "profession":  ["yazılımcı", "mühendis", "öğrenci", "doktor", "tasarımcı", "mesleğim",
                        "işim", "çalışıyorum", "developer", "engineer"],
        "preferences": ["severim", "seviyorum", "tercih ederim", "hoşlanırım", "beğenirim",
                        "istemiyorum", "sevmiyorum", "rahatsız olurum"],
        "schedule":    ["sabah", "akşam", "gece", "her gün", "haftada", "çalışma saatim",
                        "uyku", "mola"],
        "goals":       ["hedefim", "yapmak istiyorum", "planım", "öğrenmek istiyorum",
                        "geliştirmek istiyorum"],
    }

    def __init__(self):
        self._lock = threading.RLock()
        self._memories: dict = {
            "name":        None,   # tek değer
            "profession":  None,   # tek değer
            "preferences": [],     # liste
            "schedule":    [],     # liste
            "goals":       [],     # liste
            "misc":        [],     # kategorize edilemeyen her şey
        }
        self._metadata: list[dict] = []
        self._load()

    # ─────────────────────────────────────────────
    #  Dışarıdan çağrılan ana metotlar
    # ─────────────────────────────────────────────

    @_locked
    def add(self, memory: str, source: str = "conversation"):
        """
        Hafızaya yeni bir bilgi ekler.
        Kategoriyi otomatik tespit eder, yinelenen girişleri engeller.
        """
        memory = memory.strip()
        if not memory:
            return
        if len(memory) > 5000 or contains_sensitive_data(memory):
            return

        category = self._detect_category(memory)

        if category in ("name", "profession"):
            # Tekil alan: üzerine yaz
            self._memories[category] = memory
        else:
            # Liste alanı: yineleme yoksa ekle
            existing = self._memories[category]
            if not self._is_duplicate(memory, existing):
                existing.append(memory)

        self._record_metadata(category, memory, source)
        self._save()

    @_locked
    def add_to(
        self,
        category: str,
        value: str,
        source: str = "conversation",
        confidence: float = 1.0,
    ):
        """
        Kategoriyi DIŞARIDAN belirterek hafızaya ekler.

        add() metodundan farkı: kategori tahmini yapmaz.
        LLM zaten kategoriyi belirlediği için (remember_about_user aracı),
        tahmin katmanına gerek yok.
        """
        value = (value or "").strip()
        if not value or category not in self._memories:
            return
        if len(value) > 5000 or contains_sensitive_data(value):
            return

        if category in ("name", "profession"):
            # Tekil alan — üzerine yaz
            self._memories[category] = value
        else:
            # Liste alanı — yineleme yoksa ekle
            existing = self._memories[category]
            if not isinstance(existing, list):
                existing = []
            if not self._is_duplicate(value, existing):
                existing.append(value)
            self._memories[category] = existing

        self._record_metadata(category, value, source, confidence)
        self._save()

    @_locked
    def get_all(self) -> dict:
        return self._memories.copy()

    @_locked
    def get_category(self, category: str) -> list | str | None:
        return self._memories.get(category)

    @_locked
    def get_entries(self) -> list[dict]:
        """Zaman, kaynak ve güven bilgisiyle yönetilebilir hafıza kayıtları."""
        return [entry.copy() for entry in self._metadata]

    @_locked
    def update_entry(self, entry_id: str, category: str, value: str) -> bool:
        """Bir hafıza kaydını kimliği üzerinden güvenli biçimde günceller."""
        entry_id = (entry_id or "").strip()
        value = (value or "").strip()
        if not entry_id or category not in self._memories or not value:
            return False

        target = next(
            (entry for entry in self._metadata if entry.get("id") == entry_id),
            None,
        )
        if target is None:
            return False

        old_category = target.get("category", "")
        old_value = str(target.get("value", ""))
        if not self.remove(old_category, old_value):
            return False

        self.add_to(
            category,
            value,
            source="manual_edit",
            confidence=float(target.get("confidence", 1.0)),
        )
        # add_to yeni bir kimlik üretir; kullanıcı arayüzünde seçimin kararlı
        # kalması için düzenlenen kaydın eski kimliğini geri kullan.
        if self._metadata:
            self._metadata[-1]["id"] = entry_id
            self._save()
        return True

    @_locked
    def remove_by_id(self, entry_id: str) -> bool:
        """Yanlış metin eşleşmesi riskini önleyerek tek bir kaydı siler."""
        target = next(
            (entry for entry in self._metadata if entry.get("id") == entry_id),
            None,
        )
        if target is None:
            return False
        return self.remove(target.get("category", ""), target.get("value", ""))

    @_locked
    def remove(self, category: str, value: str = "") -> bool:
        """Belirli bir hafıza kaydını güvenli ve tam eşleşmeyle kaldırır."""
        if category not in self._memories:
            return False

        current = self._memories[category]
        value_lower = (value or "").strip().lower()
        removed = False

        if isinstance(current, list):
            kept = [
                item for item in current
                if str(item).strip().lower() != value_lower
            ]
            removed = len(kept) != len(current)
            self._memories[category] = kept
        elif not value_lower or str(current or "").strip().lower() == value_lower:
            removed = current is not None
            self._memories[category] = None

        if removed:
            self._metadata = [
                entry for entry in self._metadata
                if not (
                    entry.get("category") == category
                    and (
                        not value_lower
                        or str(entry.get("value", "")).strip().lower()
                        == value_lower
                    )
                )
            ]
            self._save()
        return removed

    @_locked
    def clear(self):
        for key in self._memories:
            self._memories[key] = [] if isinstance(self._memories[key], list) else None
        self._metadata = []
        self._save()

    @_locked
    def formatted(self) -> str:
        """
        LLM prompt'una eklenecek, okunabilir hafıza özeti.
        Boş kategoriler atlanır.
        """
        lines = []

        if self._memories.get("name"):
            lines.append(f"- Kullanıcının adı: {self._memories['name']}")

        if self._memories.get("profession"):
            lines.append(f"- Mesleği / rolü: {self._memories['profession']}")

        if self._memories.get("preferences"):
            prefs = ", ".join(self._memories["preferences"])
            lines.append(f"- Tercihleri: {prefs}")

        if self._memories.get("schedule"):
            sched = ", ".join(self._memories["schedule"])
            lines.append(f"- Çalışma / günlük düzeni: {sched}")

        if self._memories.get("goals"):
            goals = ", ".join(self._memories["goals"])
            lines.append(f"- Hedefleri: {goals}")

        if self._memories.get("misc"):
            misc = ", ".join(self._memories["misc"])
            lines.append(f"- Diğer notlar: {misc}")

        if not lines:
            return ""

        return (
            "Kullanıcı hakkında öğrendiğin bilgiler — bunları konuşmana doğal biçimde yansıt, "
            "robota dönme:\n" + "\n".join(lines)
        )

    # ─────────────────────────────────────────────
    #  Yardımcı metotlar
    # ─────────────────────────────────────────────

    def _detect_category(self, memory: str) -> str:
        """Basit keyword eşleşmesiyle kategori tahmin eder."""
        lower = memory.lower()
        for category, hints in self._CATEGORY_HINTS.items():
            if any(hint in lower for hint in hints):
                return category
        return "misc"

    def _is_duplicate(self, memory: str, existing: list) -> bool:
        """
        Birebir aynı veya çok benzer bir kayıt zaten varsa True döner.
        (Basit substring kontrolü — ileride embedding tabanlı yapılabilir)
        """
        memory_lower = memory.lower()
        for item in existing:
            item_lower = item.lower()
            if memory_lower == item_lower:
                return True
            # Biri diğerini tamamen içeriyorsa yineleme say
            if memory_lower in item_lower or item_lower in memory_lower:
                return True
        return False

    def _record_metadata(
        self,
        category: str,
        value: str,
        source: str,
        confidence: float = 1.0,
    ):
        normalized = value.strip().lower()
        single_value_category = category in ("name", "profession")
        self._metadata = [
            entry for entry in self._metadata
            if not (
                entry.get("category") == category
                and (
                    single_value_category
                    or str(entry.get("value", "")).strip().lower() == normalized
                )
            )
        ]
        self._metadata.append({
            "id": uuid4().hex[:10],
            "category": category,
            "value": value.strip(),
            "source": source,
            "confidence": max(0.0, min(1.0, float(confidence))),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })

    @_locked
    def _save(self):
        os.makedirs(os.path.dirname(self._SAVE_PATH), exist_ok=True)
        try:
            secure_write_json(
                self._SAVE_PATH,
                {
                    "version": self._VERSION,
                    "memories": self._memories,
                    "metadata": self._metadata,
                },
            )
        except Exception as e:
            print(f"[HATA] UserMemory kaydedilemedi: {safe_error(e)}")

    @_locked
    def _load(self):
        if not os.path.exists(self._SAVE_PATH):
            return
        try:
            with open(self._SAVE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Eski format (düz liste) → yeni formata migrate et
            if isinstance(data, list):
                self._memories["misc"] = data
                self._save()
                return

            if isinstance(data, dict) and "memories" in data:
                self._metadata = data.get("metadata", [])
                data = data.get("memories", {})

            # V2'nin ilk sürümündeki kimliksiz kayıtları sessizce yükselt.
            for entry in self._metadata:
                if not entry.get("id"):
                    entry["id"] = uuid4().hex[:10]

            # Eski kategori formatını V2 yapısına migrate et
            for key in self._memories:
                if key in data:
                    self._memories[key] = data[key]
                    values = data[key] if isinstance(data[key], list) else [data[key]]
                    for value in values:
                        if value and not any(
                            entry.get("category") == key
                            and entry.get("value") == value
                            for entry in self._metadata
                        ):
                            self._record_metadata(key, str(value), "legacy")
            self._save()

        except Exception as e:
            print(f"[HATA] UserMemory yüklenemedi: {safe_error(e)}")
