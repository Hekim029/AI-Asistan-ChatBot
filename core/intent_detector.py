from email.mime import message
import re

class IntentDetector:
    _INTENTS = {
        "time": ["saat", "saat kaç", "what time"],
        "greeting": ["merhaba", "selam", "hey", "hi", "hello"],
        "farewell": ["görüşürüz", "hoşça kal", "bye", "goodbye"],
        "clear": ["temizle", "sıfırla", "clear", "reset"],
        "remember": ["hatırla:", "kaydet:", "bunu hatırla", "bunu kaydet"],
        "system": ["sistem", "ram", "cpu", "işlemci", "bellek", "batarya", "pil", "durum"],
        
        "app_launch": [
            "spotify", "chrome", "firefox", "vs code", "vscode",
            "notepad", "hesap makinesi", "görev yöneticisi",
            "discord", "telegram", "whatsapp", "steam",
            "word", "excel", "powerpoint", "dosya gezgini",
        ],
        
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
            "siteyi aç", "giriş yap", "git", "www.", ".com", ".net",
            "web", "site", "sayfa", "araştır",
        ],
        "file": [
            "masaüstü", "masaustu", "indirmeler", "belgeler", "klasör",
            "dosya", "listele", "içeriği", "dosyayı bul", "dosyayı sil",
            "klasörü aç", "klasörü göster", "dosyayı aç",
        ],
        "app_close": [
            "kapat", "kapa", "sonlandır", "durdur",
            "spotify kapat", "chrome kapat", "firefox kapat",
        ],
        "media": [
            "sonraki şarkı", "önceki şarkı", "müziği durdur",
            "müzik devam", "next", "previous", "play", "pause",
        ],
        "volume": [
            "ses kıs", "sesi kıs", "sessiz", "mute",
            "ses aç", "sesi artır", "volume",
            "ses seviyesi", "seviyesi olsun", "ses yükselt","ses azalt",
            "ses 1", "ses 2", "ses 3", "ses 4", "ses 5",
            "ses 6", "ses 7", "ses 8", "ses 9", "ses 0",
            "yap ses", "ses yap",
        ],
    }

    def detect(self, message: str) -> str:
        message_lower = message.lower().strip()
        
        if re.search(r'ses\s+\d+', message_lower):
            return "volume"
        
        for intent, keywords in self._INTENTS.items():
            if any(kw in message_lower for kw in keywords):
                return intent
        return "llm"