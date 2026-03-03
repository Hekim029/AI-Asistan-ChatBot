import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MODEL = "llama-3.3-70b-versatile"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """Sen gelişmiş bir AI asistansın. Adın ARIA (Advanced Reasoning & Intelligence Assistant).
Kısa, net ve samimi cevaplar verirsin.
Türkçe sorulara Türkçe, İngilizce sorulara İngilizce cevap verirsin.
Teknik konularda uzmansın ama her seviyeye uygun açıklama yapabilirsin.
Gereksiz uzun cevaplar vermezsin."""