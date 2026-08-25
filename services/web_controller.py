import time
import webbrowser
import urllib.parse
import os
import pygetwindow as gw
import pyautogui

def handle_web_command(message: str) -> str:
    msg = message.lower().strip()

    if "spotify" in msg:
        query = _extract_query(message, ["spotify'da", "spotifyda", "spotify da", "spotify'de", "spotify"])
        if query:
            os.startfile(f"spotify:search:{urllib.parse.quote(query)}")
            return f"🎵 Spotify'da '{query}' araması açıldı."
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
        "trendyol": "https://www.trendyol.com",
        "hepsiburada": "https://www.hepsiburada.com",
        "google": "https://www.google.com",  # ← ekle
    }

    for name, url in sites.items():
        if name in msg and any(word in msg for word in ["aç", "git", "giriş"]):
            if name == "youtube":
                continue
            webbrowser.open(url)
            return f"🌐 {name.capitalize()} açıldı."

    if "youtube" in msg:
        open_triggers = ["aç", "git", "başlat", "open", "açsana", "açarmısın", "açar mısın"]
        search_triggers = ["ara", "bul", "search", "izle", "'da", "da ", "de ", "te "]

        has_open = any(t in msg for t in open_triggers)
        has_search = any(t in msg for t in search_triggers)

        query = _extract_query(msg, ["youtube'da", "youtubeda", "youtube da",
                                    "youtube'de", "youtube de", "youtube"])
        
        bad_queries = ["aç", "ac", "yi", "yu", "u", "ü", "açsana", ""]
        if query and query not in bad_queries:
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            webbrowser.open(url)
            return f"🎬 YouTube'da '{query}' aranıyor..."

        # Sorgu yoksa direkt aç
        if has_open and not has_search:
            webbrowser.open("https://www.youtube.com")
            return "🎬 YouTube açıldı."

        webbrowser.open("https://www.youtube.com")
        return "🎬 YouTube açıldı."
    
    if any(word in msg for word in ["harita", "maps", "nerede"]):
        query = _extract_query(msg, ["haritada", "maps'te", "nerede", "konumu"])
        if query:
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
            webbrowser.open(url)
            return f"🗺️ Haritada '{query}' aranıyor..."

    search_triggers = ["google'da", "googleda", "internette ara", "google aç", "google da"]
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
            
            for prefix in ["'de ", "'da ", "'yi ", "'yu ", "'u ", "'ü ",
                           "de ", "da ", "yi ", "yu ", "te ", "ta "]:
                if query.startswith(prefix):
                    query = query[len(prefix):].strip()
                    break

            for suffix in [" şarkısını başlat", " şarkıyı başlat", " şarkısını çal",
                           " şarkıyı çal", " başlat", " çal", " aç", " şarkısı"]:
                if query.endswith(suffix):
                    query = query[:-len(suffix)].strip()
            return query
    return ""

def close_browser_tab(query: str) -> str:
    target = None
    if "youtube" in query:
        target = "youtube"
    elif "netflix" in query:
        target = "netflix"
    elif "instagram" in query:
        target = "instagram"
    elif "github" in query:
        target = "github"

    all_windows = gw.getAllWindows()

    for win in all_windows:
        title = win.title.lower()
        if target and target in title:
            try:
                win.restore()
                time.sleep(0.3)
                win.activate()
                time.sleep(0.6)
                x = win.left + win.width // 2
                y = win.top + win.height // 2
                pyautogui.click(x, y)
                time.sleep(0.3)
                pyautogui.hotkey("ctrl", "w")
                return f"❌ {target.capitalize()} sekmesi kapatıldı."
            except Exception as e:
                return f"⚠️ Hata: {str(e)}"

    return f"⚠️ '{target}' sekmesi bulunamadı."
