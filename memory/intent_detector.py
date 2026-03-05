class IntentDetector:

    _INTENTS = {
        "time": ["saat", "saat kaç", "what time"],
        "greeting": ["merhaba", "selam", "hey", "hi", "hello"],
        "farewell": ["görüşürüz", "hoşça kal", "bye", "goodbye"],
        "clear": ["temizle", "sıfırla", "clear", "reset"],
        "remember": ["hatırla:", "kaydet:", "bunu hatırla", "bunu kaydet"],
    }

    def detect(self, message: str) -> str:
        message_lower = message.lower().strip()
        for intent, keywords in self._INTENTS.items():
            if any(kw in message_lower for kw in keywords):
                return intent
        return "llm"