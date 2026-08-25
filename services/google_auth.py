"""Google OAuth kimliğini tek noktadan ve Windows DPAPI ile koruyarak yönetir."""

from __future__ import annotations

import ctypes
import json
import os
import threading
from ctypes import wintypes
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

import utils.config as config
from services.security import bounded_json_load, secure_write_bytes, secure_write_text


SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
CREDENTIALS_PATH = Path(config.BASE_DIR) / "credentials.json"
LEGACY_TOKEN_PATH = Path(config.MEMORY_DIR) / "token.json"
TOKEN_PATH = Path(config.MEMORY_DIR) / "token.dat"
_LOCK = threading.RLock()
_DPAPI_DESCRIPTION = "HekoAI Google OAuth"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


if os.name == "nt":
    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob), wintypes.LPCWSTR, ctypes.POINTER(_DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.POINTER(_DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _protect(data: bytes) -> bytes:
    if os.name != "nt":
        return data
    source, source_buffer = _blob(data)
    result = _DataBlob()
    if not _crypt32.CryptProtectData(
        ctypes.byref(source), None, None, None, None,
        _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(result),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        _kernel32.LocalFree(result.pbData)
        del source_buffer


def _unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        return data
    source, source_buffer = _blob(data)
    result = _DataBlob()
    if not _crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None,
        _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(result),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        _kernel32.LocalFree(result.pbData)
        del source_buffer


def _load_token_info() -> dict | None:
    if TOKEN_PATH.exists():
        if TOKEN_PATH.is_symlink() or TOKEN_PATH.stat().st_size > 512_000:
            raise ValueError("OAuth token dosyası güvenli değil veya çok büyük.")
        return json.loads(_unprotect(TOKEN_PATH.read_bytes()).decode("utf-8"))
    if LEGACY_TOKEN_PATH.exists():
        info = bounded_json_load(LEGACY_TOKEN_PATH, max_bytes=512_000)
        _save_token_info(info)
        LEGACY_TOKEN_PATH.unlink()
        return info
    return None


def _save_token_info(info: dict) -> None:
    payload = json.dumps(info, ensure_ascii=False).encode("utf-8")
    try:
        protected = _protect(payload)
    except OSError as exc:
        raise RuntimeError(
            "Windows OAuth token şifrelemesi kullanılamadı; token düz metin "
            "olarak kaydedilmedi. Uygulamayı normal Windows kullanıcı "
            "oturumunda yeniden açın."
        ) from exc
    if os.name == "nt":
        secure_write_bytes(TOKEN_PATH, protected)
    else:
        secure_write_text(TOKEN_PATH, protected.decode("utf-8"))


def get_credentials() -> Credentials:
    with _LOCK:
        info = _load_token_info()
        creds = Credentials.from_authorized_user_info(info, SCOPES) if info else None
        if not creds or not creds.valid or not creds.has_scopes(SCOPES):
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if (
                    not CREDENTIALS_PATH.is_file()
                    or CREDENTIALS_PATH.is_symlink()
                    or CREDENTIALS_PATH.stat().st_size > 1_000_000
                ):
                    raise FileNotFoundError("credentials.json bulunamadı veya güvenli değil.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_PATH), SCOPES
                )
                creds = flow.run_local_server(host="127.0.0.1", port=0)
            _save_token_info(json.loads(creds.to_json()))
        return creds
