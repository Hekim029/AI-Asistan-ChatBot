import requests
from utils.config import GROQ_API_KEY, MODEL, API_URL, SYSTEM_PROMPT


class LLMClient:

    def __init__(self):
        self._headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

    def send(self, messages: list[dict]) -> str:
        payload = {
            "model": MODEL,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        }

        try:
            response = requests.post(API_URL, headers=self._headers, json=payload)
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

    def _inject_system_prompt(self, messages: list[dict]) -> list[dict]:
        if not messages:
            return messages
        first = f"[Talimat: {SYSTEM_PROMPT}]\n\n{messages[0]['content']}"
        return [{"role": "user", "content": first}] + messages[1:]