import requests
import utils.config as config

class LLMClient:

    def __init__(self):
        self._headers = {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

    def send(self, messages: list[dict], user_context: str = "") -> str:
        print(f"KULLANILAN PROMPT: {config.SYSTEM_PROMPT[:50]}")
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