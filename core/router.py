from datetime import datetime
from email import message
from memory.context_manager import ContextManager
from memory.user_memory import UserMemory
from services.llm_client import LLMClient
from services.calendar_reader import get_upcoming_events, format_events_response
from core.intent_detector import IntentDetector
import utils.config as config
from services.web_controller import handle_web_command
from services.system_info import get_system_status
from services.app_launcher import launch_app
from services.pc_controller import handle_file_command
from services.app_launcher import launch_app, close_app, media_control, volume_control

class Router:

    def __init__(self):
        self.context = ContextManager()
        self.user_memory = UserMemory()
        self.llm = LLMClient()
        self.detector = IntentDetector()

    def get_response(self, message: str) -> str:
        self.context.add_message("user", message)
        intent = self.detector.detect(message)

        message_lower = message.lower().strip()

        if intent == "time":
            response = self._get_time()
        elif intent == "greeting":
            response = "Merhaba! Sana nasıl yardımcı olabilirim?"
        elif intent == "system":
            response = get_system_status()
        elif intent == "app_launch":
            target = message_lower
            for word in ["aç", "başlat", "çalıştır", "open", "lütfen", "uygulamasını"]:
                target = target.replace(word, "")
            target = target.strip()
            response = launch_app(target)
            if response is None:
                response = self._get_web(message)
        elif intent == "web":
            response = self._get_web(message)
        elif intent == "file":
            response = self._get_file(message)
        elif intent == "farewell":
            response = "Görüşürüz! İyi günler."
        elif intent == "clear":
            self.context.clear()
            response = "🗑️ Konuşma geçmişi temizlendi."
        elif intent == "remember":
            memory_text = self._extract_memory(message)
            self.user_memory.add(memory_text)
            response = f"✅ Kaydettim: {memory_text}"
        elif intent == "calendar":
            response = self._get_calendar(message)
        elif intent == "web":
            response = self._get_web(message)
        elif intent == "app_close":
            response = close_app(message) or "❌ Hangi uygulamayı kapatmamı istersin?"
        elif intent == "media":
            response = media_control(message) or "🎵 Hangi medya komutunu yapmamı istersin?"
        elif intent == "volume":
            response = volume_control(message) or "🔊 Ses komutunu anlamadım."
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
            return f"⚠️ Takvime erişirken hata oluştu: {str(ex)}\nİlk çalıştırmada tarayıcıda Google girişi yapman gerekebilir."