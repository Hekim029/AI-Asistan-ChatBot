import webbrowser
import urllib.parse
import os

def handle_web_command(message: str) -> str:
    msg = message.lower().strip()

    if "spotify" in msg:
        query = _extract_query(message, ["spotify'da", "spotifyda", "spotify da", "spotify'de", "spotify"])
        if query:
            os.startfile(f"spotify:search:{urllib.parse.quote(query)}")
            return f"🎵 Spotify'da '{query}' aranıyor..."
        else:
            os.startfile("spotify:")
            return "🎵 Spotify açıldı."
    
    sites = {
        "fırat": "https://firat.edu.tr",
        "firat": "https://firat.edu.tr",
        "instagram": "https://instagram.com",
        "twitter": "https://twitter.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
        "netflix": "https://netflix.com",
        "youtube": "https://www.youtube.com",
        "trendol": "https://www.trendyol.com",
        "trendyol": "https://www.trendyol.com",
        "hepsiburada": "https://www.hepsiburada.com",
    }

    for name, url in sites.items():
        if name in msg and any(word in msg for word in ["aç", "git", "giriş"]):
            if name == "youtube" and any(trigger in msg for trigger in ["da", "de", "ara"]):
                break 
            webbrowser.open(url)
            return f"🌐 {name.capitalize()} açıldı."

    for name, url in sites.items():
        if name in msg and any(word in msg for word in ["aç", "git", "giriş"]):
            if name == "youtube":
                continue
            webbrowser.open(url)
            return f"🌐 {name.capitalize()} açıldı."

    if any(word in msg for word in ["harita", "maps", "nerede"]):
        query = _extract_query(msg, ["haritada", "maps'te", "nerede", "konumu"])
        if query:
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
            webbrowser.open(url)
            return f"🗺️ Haritada '{query}' aranıyor..."

    search_triggers = ["google'da", "googleda", "ara", "search", "nedir", "kimdir"]
    if any(trigger in msg for trigger in search_triggers):
        query = _extract_query(msg, search_triggers)
        if query:
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)
            return f"🔍 Google'da '{query}' aranıyor..."

    return None

def _extract_query(message: str, triggers: list) -> str:
    msg = message.lower().strip()
    msg = msg.replace('"', '').replace("'", "")
    
    triggers_sorted = sorted(triggers, key=len, reverse=True)
    for trigger in triggers_sorted:
        if trigger in msg:
            idx = msg.index(trigger) + len(trigger)
            query = msg[idx:].strip()
            
            suffixes = [
                " şarkısını başlat", " şarkıyı başlat", " şarkısını çal", 
                " şarkıyı çal", " başlat", " çal", " aç", " şarkısı"
            ]
            for suffix in suffixes:
                if query.endswith(suffix):
                    query = query[:-len(suffix)].strip()
            return query
    return ""