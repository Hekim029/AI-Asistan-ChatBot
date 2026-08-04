import json
import os
from datetime import datetime
from utils.config import MEMORY_DIR

SUMMARY_SYSTEM_PROMPT = """Sen bir konuşma özetleyicisisin.
Verilen konuşma geçmişini kısa ve bilgi kaybetmeden özetle.
Özet 3-5 cümle olsun. Türkçe yaz.
Kullanıcının sorduğu önemli şeyleri ve verilen cevapların özünü koru.
SADECE özeti yaz, başka hiçbir şey ekleme."""

class ContextManager:

    def __init__(
        self,
        max_messages: int = 20,
        summary_threshold: int = 16,
        llm_client=None,
        save_path: str | None = None,
    ):
        """
        :param max_messages:      Hafızada tutulacak maksimum mesaj sayısı
        :param summary_threshold: Bu sayıya ulaşınca özetleme tetiklenir
        """
        self._history: list[dict] = []
        self._summary: str = ""
        self._max_messages = max_messages
        self._summary_threshold = summary_threshold
        self._llm_client = llm_client
        self._save_path = save_path or os.path.join(MEMORY_DIR, "history.json")
        self._load()

    def add_message(self, role: str, content: str):
        """Geçmişe yeni mesaj ekler, eşik aşılırsa özetleme tetiklenir."""
        if not content or not content.strip():
            return

        self._history.append({
            "role":      role,
            "content":   content.strip(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        if len(self._history) >= self._summary_threshold:
            self._compress(self._llm_client)

        if len(self._history) > self._max_messages:
            self._history = self._history[-self._max_messages:]

        self._save()

    def get_history(self, limit: int = None) -> list[dict]:
        """
        LLM'e gönderilecek geçmişi döndürür.
        Timestamp'i çıkarır — LLM API sadece role/content kabul eder.
        Özet varsa en başa sistem mesajı olarak ekler.
        """
        history = self._history[-limit:] if limit else self._history

        clean = [{"role": m["role"], "content": m["content"]} for m in history]

        if self._summary:
            clean.insert(0, {
                "role":    "system",
                "content": f"Önceki konuşmaların özeti:\n{self._summary}"
            })

        return clean

    def get_raw_history(self, limit: int = None) -> list[dict]:
        """Timestamp dahil ham geçmişi döndürür (UI / geçmiş penceresi için)."""
        if limit:
            return self._history[-limit:].copy()
        return self._history.copy()

    def get_summary(self) -> str:
        return self._summary

    def clear(self):
        """Tüm geçmişi ve özeti temizler."""
        self._history.clear()
        self._summary = ""
        if os.path.exists(self._save_path):
            try:
                os.remove(self._save_path)
            except Exception:
                pass
        self._save()

    def summarize_with_llm(self, llm_client) -> bool:
        """
        Mevcut geçmişi LLM ile özetler.
        Router tarafından çağrılabilir.
        Başarılıysa True döner.
        """
        return self._compress(llm_client)

    def _compress(self, llm_client=None):
        """
        İlk yarıyı özetler, ikinci yarıyı aktif geçmiş olarak tutar.
        LLM client yoksa basit metin özeti üretir.
        """
        if len(self._history) < 4:
            return

        mid = len(self._history) // 2
        to_summarize = self._history[:mid]
        self._history = self._history[mid:]

        if llm_client:
            self._summary = self._llm_summarize(to_summarize, llm_client)
        else:
            self._summary = self._simple_summarize(to_summarize)

        self._save()

    def _llm_summarize(self, messages: list[dict], llm_client) -> str:
        """LLM ile özetleme yapar."""
        try:
            conversation = "\n".join(
                f"{m['role'].upper()} ({m.get('timestamp', '')}): {m['content']}"
                for m in messages
            )
            import requests
            import utils.config as config

            payload = {
                "model": config.MODEL,
                "messages": [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user",   "content": conversation}
                ],
                "max_tokens": 300,
                "temperature": 0.3
            }

            headers = {
                "Authorization": f"Bearer {config.GROQ_API_KEY}",
                "Content-Type":  "application/json"
            }

            response = requests.post(config.API_URL, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()

        except Exception as e:
            print(f"⚠️ LLM özetleme başarısız, basit özete geçiliyor: {e}")
            return self._simple_summarize(messages)

    def _simple_summarize(self, messages: list[dict]) -> str:
        """LLM yoksa basit metin özeti üretir."""
        lines = []
        for m in messages:
            role = "Kullanıcı" if m["role"] == "user" else "Heko"
            ts   = m.get("timestamp", "")
            lines.append(f"[{ts}] {role}: {m['content'][:100]}{'...' if len(m['content']) > 100 else ''}")
        existing = f"{self._summary}\n" if self._summary else ""
        return existing + "\n".join(lines)

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._save_path), exist_ok=True)
            data = {
                "history": self._history,
                "summary": self._summary
            }
            with open(self._save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Geçmiş kaydedilirken hata: {e}")

    def _load(self):
        if not os.path.exists(self._save_path):
            self._history = []
            self._summary = ""
            return

        try:
            with open(self._save_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                self._history = [
                    {**m, "timestamp": m.get("timestamp", "")}
                    for m in data
                ]
                self._summary = ""
                self._save()
                return

            self._history = data.get("history", [])
            self._summary = data.get("summary", "")

        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠️ Geçmiş yüklenirken hata: {e}")
            self._history = []
            self._summary = ""
