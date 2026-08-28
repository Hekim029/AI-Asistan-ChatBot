import sys
import os
import winreg
from pathlib import Path

from utils.config import BASE_DIR
from utils.app_info import APP_NAME

def get_executable_path() -> str:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        return f'"{executable}"'
    pythonw = Path(sys.executable).resolve().with_name("pythonw.exe")
    interpreter = pythonw if pythonw.is_file() else Path(sys.executable).resolve()
    main_script = (Path(BASE_DIR) / "main.py").resolve()
    return f'"{interpreter}" "{main_script}"'

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
