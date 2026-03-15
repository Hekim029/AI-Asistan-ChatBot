import sys
import os
import winreg

APP_NAME = "HekoAI"

def get_executable_path() -> str:
    vbs_path = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) 
                            else os.path.abspath("."), "HekoAI.vbs")
    return f'wscript "{vbs_path}"'

def enable_startup() -> str:
    """Windows başlangıcına ekle."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, get_executable_path())
        winreg.CloseKey(key)
        return "✅ Heko başlangıca eklendi. Bilgisayar açılınca otomatik başlayacak."
    except Exception as e:
        return f"⚠️ Başlangıca eklenemedi: {str(e)}"


def disable_startup() -> str:
    """Windows başlangıcından kaldır."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        return "✅ Heko başlangıçtan kaldırıldı."
    except FileNotFoundError:
        return "ℹ️ Heko zaten başlangıçta değildi."
    except Exception as e:
        return f"⚠️ Kaldırılamadı: {str(e)}"


def is_startup_enabled() -> bool:
    """Başlangıçta kayıtlı mı kontrol et."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False