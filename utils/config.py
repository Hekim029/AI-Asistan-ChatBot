import os
import sys
from dotenv import load_dotenv

from utils.runtime_storage import prepare_runtime_data_dir

IS_FROZEN = bool(getattr(sys, "frozen", False))
if IS_FROZEN:
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)

# Çalışma dizinindeki saldırgan kontrollü bir .env yerine yalnızca uygulamanın
# kendi kökündeki yapılandırmayı yükle.
load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)

MEMORY_DIR = str(prepare_runtime_data_dir(BASE_DIR, frozen=IS_FROZEN))
APP_SETTINGS_PATH = os.path.join(MEMORY_DIR, "app_settings.json")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
API_URL = "https://api.groq.com/openai/v1/chat/completions"

# İsteğe bağlı yerel sohbet modeli. Örnek: OLLAMA_MODEL=qwen3:8b
# Boş bırakılırsa yalnızca mevcut Groq + yerel komut katmanı kullanılır.
OLLAMA_SETTINGS_PATH = os.path.join(MEMORY_DIR, "local_model_settings.json")

# Arayüzden kaydedilen tercih varsa .env değerinin önüne geçer. Dosya yoksa
# mevcut .env davranışı aynen korunur.
from services.local_model import load_local_model_settings  # noqa: E402
from services.app_settings import load_app_settings  # noqa: E402

_LOCAL_MODEL_SETTINGS = load_local_model_settings(
    OLLAMA_SETTINGS_PATH,
    default_model=os.getenv("OLLAMA_MODEL", "").strip(),
    default_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip(),
)
OLLAMA_MODEL = _LOCAL_MODEL_SETTINGS["model"]
OLLAMA_URL = _LOCAL_MODEL_SETTINGS["base_url"]
_APP_SETTINGS = load_app_settings(APP_SETTINGS_PATH)
SCREEN_VISION_ENABLED = _APP_SETTINGS["screen_vision_enabled"]
TTS_AUTO_SPEAK = _APP_SETTINGS["tts_auto_speak"]
TTS_VOICE_ID = _APP_SETTINGS["tts_voice_id"]
TTS_RATE = _APP_SETTINGS["tts_rate"]
TTS_VOLUME = _APP_SETTINGS["tts_volume"]
VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b").strip()
HEKO_PROJECT_ROOT = os.getenv("HEKO_PROJECT_ROOT", BASE_DIR).strip()

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

CURRENT_MODE = _APP_SETTINGS["assistant_mode"]
SYSTEM_PROMPT = _APP_SETTINGS["assistant_prompt"].strip() or MODES[CURRENT_MODE]
ACCENT_COLOR = _APP_SETTINGS["accent_color"]
AI_COLOR = _APP_SETTINGS["ai_color"]
