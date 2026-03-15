import os
import subprocess
import re
import keyboard
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

APPS = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "spotify": "spotify",
    "vlc": "vlc",
    "vs code": "code",
    "vscode": "code",
    "kod editörü": "code",
    "terminal": "cmd",
    "komut istemi": "cmd",
    "powershell": "powershell",
    "not defteri": "notepad",
    "notepad": "notepad",
    "hesap makinesi": "calc",
    "görev yöneticisi": "taskmgr",
    "dosya gezgini": "explorer",
    "ayarlar": "ms-settings:",
    "discord": "discord",
    "telegram": "telegram",
    "whatsapp": "whatsapp",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "steam": "steam",
}

PROCESS_NAMES = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "spotify": "Spotify.exe",
    "vlc": "vlc.exe",
    "vs code": "Code.exe",
    "vscode": "Code.exe",
    "discord": "Discord.exe",
    "telegram": "Telegram.exe",
    "steam": "steam.exe",
    "not defteri": "notepad.exe",
    "notepad": "notepad.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
}

def launch_app(message: str) -> str | None:
    msg = message.lower().strip()
    for word in ["aç", "başlat", "çalıştır", "open", "lütfen", "uygulamasını", "uygulamayı"]:
        msg = msg.replace(word, "").strip()
    if msg in APPS:
        return _open(msg, APPS[msg])
    for app_name, executable in APPS.items():
        if app_name in msg:
            return _open(app_name, executable)
    return None

def close_app(message: str) -> str | None:
    msg = message.lower().strip()
    if any(w in msg for w in ["youtube", "netflix", "instagram", "github", "sekme", "tarayıcı"]):
        from services.web_controller import close_browser_tab
        return close_browser_tab(msg)
    for word in ["kapat", "kaldır", "durdur", "sonlandır", "kapa"]:
        msg = msg.replace(word, "").strip()
    for app_name, process in PROCESS_NAMES.items():
        if app_name in msg:
            return _kill(app_name, process)
    return None

def media_control(message: str) -> str | None:
    msg = message.lower().strip()
    if any(w in msg for w in ["sonraki", "ileri", "next"]):
        keyboard.press_and_release("next track")
        return "⏭️ Sonraki şarkıya geçildi."
    if any(w in msg for w in ["önceki", "geri", "previous"]):
        keyboard.press_and_release("previous track")
        return "⏮️ Önceki şarkıya geçildi."
    if any(w in msg for w in ["durdur", "pause", "beklet"]):
        keyboard.press_and_release("play/pause media")
        return "⏸️ Müzik duraklatıldı."
    if any(w in msg for w in ["devam", "play", "çal", "başlat"]):
        keyboard.press_and_release("play/pause media")
        return "▶️ Müzik devam ediyor."
    return None

def volume_control(message: str) -> str | None:
    msg = message.lower().strip()

    if any(w in msg for w in ["sessiz", "mute", "sesi kapat"]):
        keyboard.press_and_release("volume mute")
        return "🔇 Ses kapatıldı."

    if any(w in msg for w in ["sesi artır", "yükselt", "volume up"]):
        for _ in range(5):
            keyboard.press_and_release("volume up")
        return "🔊 Ses yükseltildi."

    if any(w in msg for w in ["ses kıs", "sesi kıs", "azalt", "volume down"]):
        for _ in range(5):
            keyboard.press_and_release("volume down")
        return "🔉 Ses kısıldı."

    m = re.search(r'(\d+)', msg)
    if m:
        level = int(m.group(1))
        level = max(0, min(100, level))
        nircmd_level = int(level * 655.35)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        nircmd = os.path.join(base, "nircmd.exe")
        subprocess.run(f'"{nircmd}" setsysvolume {nircmd_level}', shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"🔊 Ses seviyesi %{level}'e ayarlandı."

    return None

def _open(app_name: str, executable: str) -> str | None:
    try:
        if executable.startswith("ms-"):
            os.startfile(executable)
        else:
            subprocess.Popen(executable, shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        return f"🚀 {app_name.capitalize()} açılıyor..."
    except Exception:
        return None

def _kill(app_name: str, process: str) -> str:
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", process],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return f"❌ {app_name.capitalize()} kapatıldı."
    except Exception as e:
        return f"⚠️ Kapatma hatası: {str(e)}"