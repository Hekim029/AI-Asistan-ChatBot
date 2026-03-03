from datetime import datetime
from memory.context_manager import ContextManager
from services.llm_client import LLMClient
from core.intent_detector import IntentDetector

class Router:

    def __init__(self):
        self.context = ContextManager()
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
        else:
            response = self.llm.send(self.context.get_history())

        self.context.add_message("assistant", response)
        return response

    def _get_time(self) -> str:
        return f"Şu an saat: {datetime.now().strftime('%H:%M')}"