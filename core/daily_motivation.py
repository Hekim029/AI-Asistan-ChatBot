import json
import os
import random
from datetime import date
from utils.config import MEMORY_DIR

MOTIVATIONS = [
    "🚀 Bugün harika şeyler başaracaksın!",
    "💡 Her büyük proje, tek bir satır kodla başlar.",
    "⚡ Dün ne kadar ilerlediğine değil, bugün nereye gideceğine bak.",
    "🎯 Odaklan, her şey mümkün.",
    "🌟 Bugün öğrendiğin şey, yarının süper gücü.",
    "🔥 Hata yapmaktan korkma, kod yazmaktan korkma.",
    "💪 Zorlu problemler, en iyi programcıları yaratır.",
    "🧠 Her bug bir öğrenme fırsatıdır.",
    "✨ Küçük adımlar, büyük değişimler yaratır.",
    "🌍 Bugün yazdığın kod, dünyayı değiştirebilir.",
    "⭐ Mükemmel kod yok, sadece daha iyi kod var.",
    "🎮 Hayat bir oyun, sen de ana karaktersin.",
    "🌈 Karanlık debug gecelerinden sonra refactor sabahı gelir.",
    "🏆 Bugün dünden daha iyi bir geliştirici olacaksın.",
    "💻 Klavyen senin sihir değneğin, kullan!",
]

_SAVE_PATH = os.path.join(MEMORY_DIR, "daily_motivation.json")

def get_today_motivation() -> str | None:
    today = str(date.today())

    if os.path.exists(_SAVE_PATH):
        try:
            with open(_SAVE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == today:
                return None  # bugün zaten gösterildi
        except Exception:
            pass

    motivation = random.choice(MOTIVATIONS)

    with open(_SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump({"date": today, "motivation": motivation}, f, ensure_ascii=False)

    return motivation