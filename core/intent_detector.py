class IntentDetector:
    _INTENTS = {
        "time": ["saat", "saat kaç", "what time"],
        "greeting": ["merhaba", "selam", "hey", "hi", "hello"],
        "farewell": ["görüşürüz", "hoşça kal", "bye", "goodbye"],
        "clear": ["temizle", "sıfırla", "clear", "reset"],
        "remember": ["hatırla:", "kaydet:", "bunu hatırla", "bunu kaydet"],
        "system": ["sistem", "ram", "cpu", "işlemci", "bellek", "batarya", "pil", "durum"],
        
        # 'app_launch' kelimelerini 'web'den daha önce kontrol etmesi için buraya aldık
        "app_launch": ["aç", "çalıştır", "başlat", "open"],
        
        "calendar": [
            "takvim", "etkinlik", "randevu", "sınav", "ders",
            "ne zaman", "kaç gün kaldı", "bugün ne var", "yarın ne var",
            "yaklaşan", "planım", "ajanda", "program",
            "bayram", "bayrama", "tatil", "resmi tatil",
            "ramazan", "kurban", "çocuk bayramı", "cumhuriyet",
            "kaç gün var", "yaklaşıyor",
        ],
        "web": [
            "google", "youtube", "ara", "search", "arama yap",
            "harita", "maps", "wikipedia", "vikipedi",
            "hava durumu", "internette ara",
            "siteyi aç", "giriş yap", "git", "www.", ".com", ".net", ".org","link", "bağlantı", "web", "site", "sayfa", "soru sor", "bilgi al", "araştır", "bul", "göster",
            "aç", "başlat", "çalıştır", "open"
        ],
    }

    def detect(self, message: str) -> str:
        message_lower = message.lower().strip()
        for intent, keywords in self._INTENTS.items():
            if any(kw in message_lower for kw in keywords):
                return intent
        return "llm"