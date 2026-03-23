import requests
import utils.config as config

INTENT_SYSTEM_PROMPT = """Sen bir intent sınıflandırıcısın. Kullanıcının mesajını analiz edip aşağıdaki intent'lerden birini döndür.

SADECE intent adını döndür, başka hiçbir şey yazma.

Intent listesi:
- time → saat sorma
- greeting → selamlama
- farewell → vedalaşma  
- clear → konuşmayı temizle
- remember → bir şeyi hatırla/kaydet
- system → bilgisayar durumu (ram, cpu, pil)
- app_launch → uygulama aç (spotify, chrome, discord vb)
- app_close → uygulama/sekme kapat
- media → müzik kontrol (sonraki, önceki, durdur, devam)
- volume → ses kontrolü (kıs, artır, belirli seviye)
- calendar → takvim, etkinlik, randevu
- web → web sitesi aç, google'da ara, youtube
- file → dosya/klasör işlemleri
- gmail → mail oku, mail gönder
- llm → genel sohbet, soru, diğer her şey

Örnekler:
"spotify aç" → app_launch
"müziği biraz kısar mısın" → volume
"şarkıyı değiştir" → media
"yarın ne var takvimde" → calendar
"masaüstünü göster" → file
"sence en iyi programlama dili hangisi" → llm
"chrome'u kapat" → app_close
"hava nasıl olacak" → web
"beni hatırla: yazılımcıyım" → remember"""


class LLMClient:

    def __init__(self):
        self._headers = {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

    def detect_intent(self, message: str) -> str:
        """LLM ile intent tespit et."""
        valid_intents = {
            "time", "greeting", "farewell", "clear", "remember",
            "system", "app_launch", "app_close", "media", "volume",
            "calendar", "web", "file", "gmail", "llm"
        }

        payload = {
            "model": config.MODEL,
            "messages": [
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            "max_tokens": 10,
            "temperature": 0
        }

        try:
            response = requests.post(config.API_URL, headers=self._headers, json=payload)
            response.raise_for_status()
            intent = response.json()["choices"][0]["message"]["content"].strip().lower()
            if intent in valid_intents:
                return intent
            return "llm"
        except Exception:
            return "llm"

    def send(self, messages: list[dict], user_context: str = "") -> str:
        system = config.SYSTEM_PROMPT
        if user_context:
            system += f"\n\n{user_context}"

        payload = {
            "model": config.MODEL,
            "messages": [{"role": "system", "content": system}] + messages
        }

        try:
            response = requests.post(config.API_URL, headers=self._headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                return "⚠️ Çok fazla istek gönderildi, birkaç saniye bekleyip tekrar dene."
            return f"⚠️ API hatası: {e}"
        except requests.exceptions.ConnectionError:
            return "⚠️ İnternet bağlantısı yok."
        except Exception as e:
            return f"⚠️ Beklenmedik hata: {e}"