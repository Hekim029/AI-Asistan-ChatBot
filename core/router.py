"""
Router — Heko'nun ana giriş noktası.

ESKİ HALİ (~200 satır):
  Intent tespit et -> 15 tane if/elif -> her biri farklı servise git ->
  her servis kendi parametrelerini metinden çıkarsın.

YENİ HALİ (~60 satır):
  Mesajı LLM'e ver -> LLM hangi aracı çağıracağına karar versin ->
  ToolExecutor çalıştırsın -> LLM sonucu cümleye çevirsin.

Artık burada intent mantığı YOK. Router sadece:
  1) Mesajı geçmişe kaydeder
  2) LLM'e devreder
  3) Cevabı geçmişe kaydeder
"""

from memory.context_manager import ContextManager
from memory.user_memory import UserMemory
from services.llm_client import LLMClient, OperationCancelled
from services.reminder_manager import ReminderManager
from services.task_manager import TaskManager
from core.tools import ToolExecutor
from core.local_intents import clarification_for, detect_local_tool, pending_slot_for
from core.shared_state import SharedAssistantState
from utils.config import MEMORY_DIR
import os
from services.security import contains_sensitive_data, safe_error, validate_user_text


class Router:

    def __init__(self, shared_state=None, session_id="main"):
        shared_state = shared_state or SharedAssistantState()
        self.session_id = session_id
        self.shared_state = shared_state
        self.llm         = LLMClient()
        session_dir = os.path.join(MEMORY_DIR, "sessions")
        self.context = ContextManager(
            llm_client=self.llm,
            save_path=os.path.join(session_dir, f"{session_id}.json"),
        )
        self.user_memory = shared_state.user_memory
        self.reminders = shared_state.reminders
        self.tasks = shared_state.tasks
        self.workspace = shared_state.workspace

        # ToolExecutor'a hafıza nesnelerini veriyoruz ki
        # remember_about_user ve clear_history araçları çalışabilsin
        self.executor = ToolExecutor(
            user_memory=self.user_memory,
            context_manager=self.context,
            reminder_manager=self.reminders,
            task_manager=self.tasks,
            shared_workspace=self.workspace,
            session_id=self.session_id,
        )

        # Son çağrılan araçlar — UI veya debug için
        self.last_tools_used: list[str] = []
        self._pending_local_slot = None

    def get_response(self, message: str, on_status=None, is_cancelled=None) -> str:
        """
        Kullanıcı mesajını işler ve cevabı döndürür.

        :param on_status: (opsiyonel) her önemli aşamada çağrılan callback.
                          UI'da "Düşünüyor...", "Klasör açılıyor..." gibi
                          anlık durumlar göstermek için kullanılır.
                          Worker (ayrı thread) bunu bir Qt sinyaline
                          çevirip ana thread'e güvenli şekilde iletir.
        """
        if is_cancelled and is_cancelled():
            raise OperationCancelled("İşlem başlamadan iptal edildi.")
        try:
            message = validate_user_text(message, name="Mesaj", max_length=80_000)
        except ValueError as exc:
            return str(exc)
        if contains_sensitive_data(message):
            return (
                "Bu mesaj parola, API anahtarı veya özel anahtar gibi hassas bir "
                "bilgi içeriyor. Güvenliğin için bunu sohbete kaydetmedim ve modele "
                "göndermedim. Anahtarı ilgili .env dosyasına kendin eklemelisin."
            )

        self.context.add_message("user", message)

        self.last_tools_used = []
        normalized = " ".join(message.lower().strip().split())

        if getattr(self, "_pending_local_slot", None):
            if normalized in {"iptal", "vazgeçtim", "boşver", "boş ver"}:
                self._pending_local_slot = None
                response = "Tamam, bu isteği iptal ettim."
                self.context.add_message("assistant", response)
                return response
            slot = self._pending_local_slot
            self._pending_local_slot = None
            if slot == "note":
                local_call = ("add_note", {"text": message.strip(), "tags": []})
            elif slot == "task":
                local_call = ("add_task", {"title": message.strip(), "due_at": ""})
            elif slot == "weather":
                local_call = ("get_weather", {"city": message.strip(), "period": "today"})
            else:
                local_call = ("read_text_file", {"path": message.strip()})
            tool_name, args = local_call
            if on_status:
                on_status(self._friendly_status(tool_name))
            if is_cancelled and is_cancelled():
                raise OperationCancelled("İşlem iptal edildi.")
            self._on_tool_used(tool_name, args)
            response = self.executor.execute(tool_name, args)
            if is_cancelled and is_cancelled():
                raise OperationCancelled("İşlem iptal edildi.")
            self.context.add_message("assistant", response)
            self.workspace.publish(self.session_id, "tool", message, response)
            return response

        if self.executor.has_pending_action():
            if normalized in {
                "onaylıyorum", "onayla", "evet", "evet yap",
                "tamam yap", "işlemi yap",
            }:
                if on_status:
                    on_status("Onaylanan işlem uygulanıyor...")
                if is_cancelled and is_cancelled():
                    raise OperationCancelled("İşlem iptal edildi.")
                response = self.executor.execute(
                    "confirm_pending_action", {}
                )
                if is_cancelled and is_cancelled():
                    raise OperationCancelled("İşlem iptal edildi.")
                self.context.add_message("assistant", response)
                return response
            if normalized in {
                "iptal", "iptal et", "hayır", "vazgeçtim",
                "yapma", "işlemi iptal et",
            }:
                response = self.executor.execute(
                    "cancel_pending_action", {}
                )
                self.context.add_message("assistant", response)
                return response

        local_call = detect_local_tool(message)
        if local_call:
            tool_name, args = local_call
            if on_status:
                on_status(self._friendly_status(tool_name))
            if is_cancelled and is_cancelled():
                raise OperationCancelled("İşlem iptal edildi.")
            self._on_tool_used(tool_name, args)
            response = self.executor.execute(tool_name, args)
            if is_cancelled and is_cancelled():
                raise OperationCancelled("İşlem iptal edildi.")
            self.context.add_message("assistant", response)
            self.workspace.publish(self.session_id, "tool", message, response)
            return response

        clarification = clarification_for(message)
        if clarification:
            self._pending_local_slot = pending_slot_for(message)
            self.context.add_message("assistant", clarification)
            return clarification

        if on_status:
            on_status("Düşünüyor...")

        def handle_tool(tool_name: str, args: dict):
            self._on_tool_used(tool_name, args)
            if on_status:
                on_status(self._friendly_status(tool_name))

        try:
            shared_context = self.workspace.formatted_context(self.session_id, limit=6)
            response = self.llm.chat(
                messages=self.context.get_history(limit=8),
                user_context="\n\n".join(
                    part for part in (self.user_memory.formatted(), shared_context) if part
                ),
                executor=self.executor,
                on_tool_used=handle_tool,
                is_cancelled=is_cancelled,
            )
        except OperationCancelled:
            raise
        except Exception as e:
            from services.error_logger import log_exception
            log_exception("router", e)
            response = f"Bir sorun oluştu: {safe_error(e)}"

        if is_cancelled and is_cancelled():
            raise OperationCancelled("İşlem iptal edildi.")
        self.context.add_message("assistant", response)
        self.workspace.publish(self.session_id, "conversation", message, response)
        return response

    # ─────────────────────────────────────────
    #  Araç kullanım takibi
    # ─────────────────────────────────────────

    # Her aracın kullanıcıya gösterilecek dostça Türkçe karşılığı.
    # Burada olmayan bir araç için genel bir mesaj kullanılır — yeni
    # araç eklendiğinde buraya satır eklemek ZORUNLU değildir, sistem
    # esnek kalır.
    _STATUS_MAP = {
        "get_time":            "Saate bakılıyor...",
        "create_reminder":     "Hatırlatıcı kuruluyor...",
        "list_reminders":      "Hatırlatıcılar kontrol ediliyor...",
        "cancel_reminder":     "Hatırlatıcı iptal ediliyor...",
        "get_weather":         "Hava durumu kontrol ediliyor...",
        "add_task":            "Görev ekleniyor...",
        "list_tasks":          "Görevler kontrol ediliyor...",
        "complete_task":       "Görev tamamlanıyor...",
        "add_note":            "Not kaydediliyor...",
        "list_notes":          "Notlar kontrol ediliyor...",
        "get_daily_briefing":  "Günlük özet hazırlanıyor...",
        "open_folder":         "Klasör açılıyor...",
        "list_folder":         "Klasör içeriği listeleniyor...",
        "search_file":         "Dosya aranıyor...",
        "delete_file":         "Dosya siliniyor...",
        "launch_app":          "Uygulama açılıyor...",
        "close_app":           "Uygulama kapatılıyor...",
        "control_volume":      "Ses ayarlanıyor...",
        "control_media":       "Medya kontrol ediliyor...",
        "open_website":        "Site açılıyor...",
        "search_web":          "İnternette aranıyor...",
        "get_calendar":        "Takvime bakılıyor...",
        "create_calendar_event": "Takvim etkinliği hazırlanıyor...",
        "update_calendar_event": "Takvim etkinliği güncelleniyor...",
        "delete_calendar_event": "Takvim etkinliği siliniyor...",
        "get_emails":          "Mailler kontrol ediliyor...",
        "read_email":          "Mail içeriği okunuyor...",
        "list_project_files":  "Proje dosyaları listeleniyor...",
        "read_project_file":   "Proje dosyası okunuyor...",
        "update_project_file": "Kod değişikliği önizlemesi hazırlanıyor...",
        "delete_project_file": "Proje dosyası için güvenli silme onayı hazırlanıyor...",
        "read_document":       "Belgeden güvenli biçimde metin çıkarılıyor...",
        "analyze_screen":      "Onaylanan ekran görüntüsü inceleniyor...",
        "send_email":          "Mail gönderiliyor...",
        "get_system_status":   "Sistem durumu kontrol ediliyor...",
        "remember_about_user": "Not alınıyor...",
        "list_user_memory":    "Hafızaya bakılıyor...",
        "forget_user_memory":  "Hafıza kaydı siliniyor...",
        "clear_history":       "Geçmiş temizleniyor...",
        "confirm_pending_action": "Onaylanan işlem uygulanıyor...",
        "cancel_pending_action":  "Bekleyen işlem iptal ediliyor...",
    }

    def _friendly_status(self, tool_name: str) -> str:
        return self._STATUS_MAP.get(tool_name, "İşlem yapılıyor...")

    def _on_tool_used(self, tool_name: str, args: dict):
        """
        LLM bir araç çağırdığında tetiklenir.
        Loglar ve last_tools_used listesine ekler (debug/UI amaçlı).
        """
        self.last_tools_used.append(tool_name)
        arg_names = ", ".join(sorted(str(key) for key in args))
        print(f"[ARAC] {tool_name} (alanlar: {arg_names or 'yok'})")

    # ─────────────────────────────────────────
    #  Dışarıdan erişim (UI için)
    # ─────────────────────────────────────────

    def clear_history(self):
        """UI'daki temizle butonu için."""
        self.context.clear()

    def get_history(self, limit: int = None):
        """Geçmiş penceresi için — timestamp dahil."""
        return self.context.get_raw_history(limit)
