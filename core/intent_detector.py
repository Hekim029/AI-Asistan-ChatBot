import re

class IntentDetector:
    _INTENTS = {
        "time": ["saat kaç", "what time", "saat"],
        "greeting": ["merhaba", "selam", "hey", "hi", "hello"],
        "farewell": ["görüşürüz", "hoşça kal", "bye", "goodbye"],
        "clear": ["temizle", "sıfırla", "clear", "reset"],
        "remember": ["bunu hatırla", "bunu kaydet", "hatırla:", "kaydet:"],

        "calendar": [
            "takvim", "etkinlik", "randevu", "sınav", "ders",
            "ne zaman", "kaç gün kaldı", "bugün ne var", "yarın ne var",
            "yaklaşan", "planım", "ajanda", "program",
            "bayram", "bayrama", "bayramı", "tatil", "resmi tatil",
            "ramazan", "kurban", "çocuk bayramı", "cumhuriyet",
            "kaç gün var", "yaklaşıyor",
        ],

        "gmail": [
            "maillerimi göster", "e-posta göster", "gelen kutusu",
            "mail at", "mail gönder", "okunmamış mail", "yeni mail",
            "bugün mail", "kaç mail geldi", "kimden mail",
            "maillerimi kontrol et", "inbox",
            "kaç mesaj", "mesaj var", "mesaj bar", "kaç mail",
            "mail var", "mail sayısı", "mail",
        ],

        "app_close": [
            "spotify kapat", "chrome kapat", "firefox kapat",
            "discord kapat", "steam kapat", "edge kapat",
            "youtube kapat", "sekme kapat", "tarayıcı kapat",
            "kapat", "kapa", "sonlandır",
        ],

        "app_launch": [
            "spotify", "chrome", "firefox", "vs code", "vscode",
            "notepad", "hesap makinesi", "görev yöneticisi",
            "discord", "telegram", "whatsapp", "steam",
            "word", "excel", "powerpoint", "dosya gezgini",
        ],

        "file": [
            "klasörü aç", "klasörü göster", "dosyayı aç", "dosyayı bul", "dosyayı sil",
            "masaüstü", "masaustu", "indirmeler", "belgeler", "klasör",
            "dosya", "listele", "içeriği",
        ],

        "web": [
            "google'da", "googleda", "youtube'da", "youtubeda",
            "internette ara", "siteyi aç", "giriş yap",
            "www.", ".com", ".net", "web sitesi",
            "wikipedia", "vikipedi", "harita", "maps",
            "instagram aç", "twitter aç", "github aç",
            "netflix aç", "trendyol aç", "hepsiburada aç",
            "youtube aç", "google aç",
        ],

        "media": [
            "sonraki şarkı", "önceki şarkı", "müziği durdur",
            "müzik devam", "next track", "previous track",
        ],

        "volume": [
            "ses kıs", "sesi kıs", "sessiz", "mute",
            "sesi artır", "ses yükselt", "ses azalt", "volume",
            "ses seviyesi", "seviyesi olsun",
        ],

        "system": [
            "sistem durumu", "cpu kullanımı", "ram kullanımı",
            "sistem", "ram", "cpu", "işlemci", "bellek", "batarya", "pil", "durum",
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