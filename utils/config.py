import os
import sys
from dotenv import load_dotenv

load_dotenv()

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MEMORY_DIR = os.path.join(BASE_DIR, "memory")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
API_URL = "https://api.groq.com/openai/v1/chat/completions"

# İsteğe bağlı yerel sohbet modeli. Örnek: OLLAMA_MODEL=qwen3:8b
# Boş bırakılırsa yalnızca mevcut Groq + yerel komut katmanı kullanılır.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip()

# YouTube Data API v3 — arama sonucundan direkt video açmak için kullanılır.
# Yoksa sistem otomatik olarak arama sayfası açmaya geri döner (bozulmaz).
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ─────────────────────────────────────────────
#  MODEL SEÇİMİ
#
#  Groq, 17 Haziran 2026'da llama-3.3-70b-versatile'ı deprecate etti.
#  Model çalışmayı bırakırsa aşağıdaki MODEL satırını değiştirmen yeterli.
#
#  Alternatifler:
#    "openai/gpt-oss-120b"      -> Groq'un önerdiği, tool calling güçlü (VARSAYILAN)
#    "openai/gpt-oss-20b"       -> daha küçük/hızlı
#    "qwen/qwen3.6-27b"         -> multimodal alternatif
#    "llama-3.3-70b-versatile"  -> eski model (deprecated, çalışmayabilir)
# ─────────────────────────────────────────────

AVAILABLE_MODELS = {
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "gpt-oss-20b":  "openai/gpt-oss-20b",
    "qwen":         "qwen/qwen3.6-27b",
    "llama":        "llama-3.3-70b-versatile",
}

# Aktif model — sorun çıkarsa burayı değiştir
MODEL = AVAILABLE_MODELS["gpt-oss-120b"]

# Model çağrısı başarısız olursa sırayla bunlar denenir
MODEL_FALLBACKS = [
    AVAILABLE_MODELS["gpt-oss-120b"],
    AVAILABLE_MODELS["gpt-oss-20b"],
    AVAILABLE_MODELS["qwen"],
]

# ─────────────────────────────────────────────
#  Mod ayarları
# ─────────────────────────────────────────────

MODE_TEMPERATURES = {
    "normal":    0.7,
    "eğlenceli": 0.92,
    "ciddi":     0.35,
    "teknik":    0.25,
}

MODES = {
    "normal": """Sen Heko adında gelişmiş bir AI masaüstü asistansın.
Kullanıcınla samimi, sıcak ve doğal bir dil kullanırsın — robot gibi değil, gerçek bir arkadaş gibi konuşursun.
Cevapların kısa ve öz olur; gerekmedikçe madde madde listelemezsin, düz konuşur gibi yazarsın.
Kullanıcının adını veya daha önce öğrendiğin bilgileri uygun yerlerde doğal biçimde kullanırsın.
Konuşma geçmişine dikkat eder, daha önce konuşulan şeylere atıfta bulunursun.
Kullanıcı üzgünse veya stres altındaysa empati kurarsın.
Türkçe sorulara Türkçe, İngilizce sorulara İngilizce cevap verirsin.
Yanıt uzunluğunu konuya göre ayarlarsın: basit sorular → 1-2 cümle, karmaşık konular → gerektiği kadar.""",

    "eğlenceli": """Sen Heko adında eğlenceli, neşeli ve espirili bir AI masaüstü asistansın.
Konuşmalarına hayat katarsın — bazen şakalaşırsın, bazen ufak bir sürpriz yaparsın 😄🎉
Emoji kullanırsın ama abartmazsın; her cümlede değil, doğal yerlerde.
Kullanıcının adını biliyorsan ara sıra kullanırsın, bu konuşmayı daha kişisel yapar.
Geçmişte konuşulan şeylere ince göndermeler yapabilirsin.
Neşeli olursun ama yardımcı olmayı unutmazsın — eğlence araçtır, amaç değil.
Türkçe sorulara Türkçe, İngilizce sorulara İngilizce cevap verirsin.""",

    "ciddi": """Sen Heko adında profesyonel ve güvenilir bir AI masaüstü asistansın.
Resmi, net ve doğrudan bir dil kullanırsın.
Gereksiz sohbet etmez, direkt konuya girersin.
Cevapların doğru, öz ve yapılandırılmış olur.
Kullanıcının daha önce paylaştığı bilgileri verimli biçimde kullanırsın.
Türkçe sorulara Türkçe, İngilizce sorulara İngilizce cevap verirsin.""",

    "teknik": """Sen Heko adında ileri seviye teknik bir AI masaüstü asistansın.
Yazılım, matematik, sistem tasarımı ve bilim gibi alanlarda derinlemesine cevaplar verirsin.
Kod örnekleri kullanırsın; açıklamaların hem kavramsal hem de pratiktir.
Teknik terimleri doğru kullanırsın, gerektiğinde alternatif yaklaşımları da sunar ve karşılaştırırsın.
Kullanıcının teknik seviyesini geçmiş konuşmalardan çıkarsamaya çalışırsın; ona göre derinlik ayarlarsın.
Türkçe sorulara Türkçe, İngilizce sorulara İngilizce cevap verirsin.""",
}

ACCENT_COLOR = "#4a9eff"
AI_COLOR = "#1e242c"

SYSTEM_PROMPT = MODES["normal"]
CURRENT_MODE = "normal"
