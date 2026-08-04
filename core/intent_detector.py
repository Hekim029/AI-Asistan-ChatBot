import re


class IntentDetector:
    """
    Keyword tabanlı hızlı intent tespiti.

    ÖNEMLİ KAVRAM — İki tip keyword var:

    1) STRICT (katı):  Kelime sınırıyla aranır. "çal" yazarsak "çalan" eşleşmez.
                       Kısa ve başka kelimelerin içinde geçebilecek kelimeler için.
                       Örn: çal, ara, harita, ders, saat

    2) LOOSE (esnek):  Substring olarak aranır. "masaüstü" yazarsak "masaüstümü"
                       de eşleşir. Türkçe ek alabilen özel isimler için.
                       Örn: masaüstü, youtube, spotify, takvim
    """

    # ─────────────────────────────────────────────
    #  Esnek keyword'ler — ek alabilir, substring yeterli
    # ─────────────────────────────────────────────
    _LOOSE = {
        "calendar": [
            "takvim", "etkinlik", "randevu", "sınav",
            "ajanda", "bayram", "tatil", "ramazan", "kurban",
            "cumhuriyet", "yaklaşan",
        ],

        "gmail": [
            "mail", "e-posta", "eposta", "inbox", "gelen kutusu",
        ],

        "app_launch": [
            "spotify", "chrome", "firefox", "vscode", "vs code",
            "notepad", "discord", "telegram", "whatsapp", "steam",
            "excel", "powerpoint", "dosya gezgini", "hesap makinesi",
            "görev yöneticisi",
        ],

        "file": [
            "masaüstü", "masaustu", "indirmeler", "belgeler",
            "klasör", "klasöre", "klasörü",
        ],

        "web": [
            "youtube", "instagram", "twitter", "github", "netflix",
            "trendyol", "hepsiburada", "wikipedia", "vikipedi",
            "www.", ".com", ".net",
        ],

        "system": [
            "cpu", "işlemci", "bellek", "batarya",
        ],
    }

    # ─────────────────────────────────────────────
    #  Katı keyword'ler — tam kelime eşleşmesi gerekir
    # ─────────────────────────────────────────────
    _STRICT = {
        "time": ["saat", "saat kaç"],

        "greeting": ["merhaba", "selam", "hey", "hi", "hello", "günaydın"],

        "farewell": ["görüşürüz", "hoşça kal", "bye", "goodbye", "bay bay"],

        "clear": ["temizle", "sıfırla", "clear", "reset"],

        "remember": ["hatırla", "kaydet", "not al", "unutma"],

        "calendar": ["ders", "program", "planım"],

        "app_close": ["kapat", "kapa", "sonlandır"],

        "file": ["listele", "dosya", "dosyayı", "dosyalar"],

        "web": ["harita", "maps", "site", "siteyi"],

        "media": [
            "sonraki", "önceki", "durdur", "duraklat",
            "next", "previous", "pause",
        ],

        "volume": [
            "sessiz", "mute", "kıs", "yükselt", "azalt", "volume",
        ],

        "system": ["ram", "sistem", "pil", "durum"],
    }

    # ─────────────────────────────────────────────
    #  Bu kelimeler varsa o intent KESİNLİKLE seçilmez
    # ─────────────────────────────────────────────
    _BLOCKERS = {
        "media": ["çalan", "çalıyor", "hangi", "ne çalıyor", "şu an", "şuan"],
        "web":   ["yol haritası", "yol harita"],
    }

    def detect(self, message: str) -> str:
        msg = message.lower().strip()

        # ── Öncelikli özel kurallar ──────────────────

        # "ses 50 yap" gibi sayı içeren ses komutları
        if re.search(r'ses\s+\d+', msg):
            return "volume"

        # YouTube/Spotify geçiyorsa direkt web
        if "youtube" in msg or "spotify" in msg:
            return "web"

        # ── Normal tarama ────────────────────────────

        for intent in self._all_intents():
            if self._is_blocked(intent, msg):
                continue

            if self._matches_loose(intent, msg):
                return intent

            if self._matches_strict(intent, msg):
                return intent

        return "llm"

    # ─────────────────────────────────────────────
    #  Yardımcı metotlar
    # ─────────────────────────────────────────────

    def _all_intents(self) -> list[str]:
        """
        Kontrol sırası. Sıra ÖNEMLİ — üstteki önce kontrol edilir.
        file, app_launch'tan önce gelmeli.
        """
        return [
            "time", "greeting", "farewell", "clear", "remember",
            "calendar", "gmail", "app_close", "file", "app_launch",
            "web", "media", "volume", "system",
        ]

    def _matches_loose(self, intent: str, msg: str) -> bool:
        """Substring araması — ek almış haller de eşleşir."""
        keywords = self._LOOSE.get(intent, [])
        return any(kw in msg for kw in keywords)

    def _matches_strict(self, intent: str, msg: str) -> bool:
        """
        Kelime siniri aramasi.
        \\b = word boundary. r"\\bcal\\b" -> "calan" icindeki "cal"i YAKALAMAZ.
        re.escape() -> keyword'de ozel karakter varsa bozulmasin diye.
        """
        keywords = self._STRICT.get(intent, [])
        for kw in keywords:
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, msg):
                return True
        return False

    def _is_blocked(self, intent: str, msg: str) -> bool:
        """Bu intent icin engelleyici kelime var mi?"""
        blockers = self._BLOCKERS.get(intent, [])
        return any(b in msg for b in blockers)