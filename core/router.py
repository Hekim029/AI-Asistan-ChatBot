from datetime import datetime
from memory.context_manager import ContextManager
from memory.user_memory import UserMemory
from services.llm_client import LLMClient
from core.intent_detector import IntentDetector


class Router:

    def __init__(self):
        self.context = ContextManager()
        self.user_memory = UserMemory()
        self.llm = LLMClient()
        self.detector = IntentDetector()

    def get_response(self, message: str) -> str:
        self.context.add_message("user", message)
        intent = self.detector.detect(message)

        if intent == "time":
            response = self._get_time()
        elif intent == "greeting":
            response = "Merhaba! Sana nasıl yardımcı olabilirim?"
        elif intent == "farewell":
            response = "Görüşürüz! İyi günler."
        elif intent == "clear":
            self.context.clear()
            response = "🗑️ Konuşma geçmişi temizlendi."
        elif intent == "remember":
            memory_text = self._extract_memory(message)
            self.user_memory.add(memory_text)
            response = f"✅ Kaydettim: {memory_text}"
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