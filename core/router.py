from memory.context_manager import ContextManager
from services.llm_client import LLMClient


class Router:

    def __init__(self):
        self.context = ContextManager()
        self.llm = LLMClient()

    def get_response(self, message: str) -> str:
        self.context.add_message("user", message)

        message_lower = message.lower()
        if "saat" in message_lower:
            response = self._get_time()
        else:
            response = self.llm.send(self.context.get_history())

        self.context.add_message("assistant", response)
        return response

    def _get_time(self):
        from datetime import datetime
        return f"Şu an saat: {datetime.now().strftime('%H:%M')}"