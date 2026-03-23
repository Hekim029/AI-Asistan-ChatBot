from datetime import datetime
from memory.context_manager import ContextManager
from memory.user_memory import UserMemory
from services.llm_client import LLMClient
from services.calendar_reader import get_upcoming_events, format_events_response
from core.intent_detector import IntentDetector
import utils.config as config
from services.web_controller import handle_web_command
from services.system_info import get_system_status
from services.app_launcher import launch_app, close_app, media_control, volume_control
from services.pc_controller import handle_file_command
from services.gmail_reader import get_unread_emails, get_today_emails, send_email, search_emails


class Router:

    def __init__(self):
        self.context = ContextManager()
        self.user_memory = UserMemory()
        self.llm = LLMClient()
        self.detector = IntentDetector()

    def get_response(self, message: str) -> str:
        self.context.add_message("user", message)

        # Önce hızlı keyword ile dene
        intent = self.detector.detect(message)

        # Keyword bulamazsa LLM'e sor
        if intent == "llm":
            intent = self.llm.detect_intent(message)

        if intent == "time":
            response = self._get_time()

        elif intent == "greeting":
            response = self.llm.send(
                [{"role": "user", "content": message}],
                self.user_memory.formatted()
            )

        elif intent == "farewell":
            response = self.llm.send(
                [{"role": "user", "content": message}],
                self.user_memory.formatted()
            )

        elif intent == "clear":
            self.context.clear()
            response = "🗑️ Konuşma geçmişi temizlendi."

        elif intent == "remember":
            memory_text = self._extract_memory(message)
            self.user_memory.add(memory_text)
            response = f"✅ Kaydettim: {memory_text}"

        elif intent == "system":
            response = get_system_status()

        elif intent == "app_launch":
            response = launch_app(message)
            if response is None:
                response = self._get_web(message)

        elif intent == "app_close":
            response = close_app(message) or "❌ Hangi uygulamayı kapatmamı istersin?"

        elif intent == "media":
            response = media_control(message) or "🎵 Hangi medya komutunu yapmamı istersin?"

        elif intent == "volume":
            response = volume_control(message) or "🔊 Ses komutunu anlamadım."

        elif intent == "calendar":
            response = self._get_calendar(message)

        elif intent == "web":
            response = self._get_web(message)

        elif intent == "file":
            response = self._get_file(message)

        elif intent == "gmail":
            response = self._get_gmail(message)

        else:
            response = self.llm.send(self.context.get_history(), self.user_memory.formatted())

        self.context.add_message("assistant", response)
        return response

    def _get_time(self) -> str:
        return f"Şu an saat: {datetime.now().strftime('%H:%M')}"

    def _extract_memory(self, message: str) -> str:
        for trigger in ["bunu hatırla", "bunu kaydet", "hatırla:", "kaydet:"]:
            if trigger in message.lower():
                idx = message.lower().index(trigger) + len(trigger)
                return message[idx:].strip()
        return message.strip()

    def _get_web(self, message: str) -> str:
        result = handle_web_command(message)
        if result:
            return result
        return "🌐 Hangi siteyi veya aramayı yapmamı istersin?"

    def _get_file(self, message: str) -> str:
        result = handle_file_command(message)
        if result:
            return result
        return "📁 Hangi dosya veya klasörle ilgili yardım istiyorsun?"

    def _get_gmail(self, message: str) -> str:
        msg = message.lower().strip()

        if any(w in msg for w in ["mail at", "mail gönder", "yaz"]):
            return self._parse_and_send_email(message)

        if any(w in msg for w in ["dan mail", "den mail", "var mı"]):
            query = msg
            for w in ["mail", "var mı", "geldi mi", "gönderdi mi"]:
                query = query.replace(w, "").strip()
            return search_emails(query)

        if any(w in msg for w in ["bugün", "bugünkü"]):
            return get_today_emails()

        if any(w in msg for w in ["okunmamış", "yeni mail", "kaç mail"]):
            return get_unread_emails()

        return get_unread_emails()

    def _parse_and_send_email(self, message: str) -> str:
        import re
        email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', message)
        if not email_match:
            return "⚠️ Geçerli bir email adresi bulunamadı."
        to = email_match.group(0)

        subject = "Heko'dan mesaj"
        konu_match = re.search(r'konu[:\s]+(.+?)(?:içerik|mesaj|$)', message, re.IGNORECASE)
        if konu_match:
            subject = konu_match.group(1).strip()

        body = ""
        icerik_match = re.search(r'(?:içerik|mesaj)[:\s]+(.+)', message, re.IGNORECASE)
        if icerik_match:
            body = icerik_match.group(1).strip()

        if not body:
            return "⚠️ Mail içeriği bulunamadı. 'içerik: ...' şeklinde yaz."

        return send_email(to, subject, body)

    def _get_calendar(self, message: str) -> str:
        try:
            events = get_upcoming_events(days=365)
            if not events:
                return "📅 Takviminde önümüzdeki 365 gün içinde etkinlik bulamadım."

            msg = message.lower()

            if "bugün" in msg:
                filtered = [e for e in events if e["days_left"] == 0]
                if not filtered:
                    return "📅 Bugün için takviminde etkinlik yok."
                lines = ["📅 Bugünkü etkinlikler:"]
                for e in filtered:
                    lines.append(f"  • {e['title']}")
                return "\n".join(lines)

            elif "yarın" in msg:
                filtered = [e for e in events if e["days_left"] == 1]
                if not filtered:
                    return "📅 Yarın için takviminde etkinlik yok."
                lines = ["📅 Yarınki etkinlikler:"]
                for e in filtered:
                    lines.append(f"  • {e['title']}")
                return "\n".join(lines)

            elif "kaç gün" in msg or "ne zaman" in msg:
                for e in events:
                    if any(word in msg for word in e["title"].lower().split()):
                        d = e["days_left"]
                        if d == 0:
                            return f"⏰ '{e['title']}' BUGÜN!"
                        elif d == 1:
                            return f"⏰ '{e['title']}' yarın!"
                        else:
                            return f"⏰ '{e['title']}' etkinliğine {d} gün kaldı."
                e = events[0]
                d = e["days_left"]
                return f"⏰ En yakın etkinliğin '{e['title']}' — {d} gün kaldı."

            else:
                return format_events_response(events)

        except Exception as ex:
            return f"⚠️ Takvime erişirken hata oluştu: {str(ex)}"