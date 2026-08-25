"""Heko genelinde kullanılan güvenlik doğrulamaları ve güvenli dosya yazımı."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


MAX_USER_TEXT = 80_000
MAX_SHORT_TEXT = 500

_SECRET_PATTERNS = (
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        re.I | re.S,
    ),
    re.compile(
        r"\b(?:gsk_|sk-|ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{20,}\b"
    ),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|client[_-]?secret|refresh[_-]?token|password|passwd|authorization)"
        r"\b\s*[:=]\s*(['\"]?)([^\s,'\"}]{8,})\2"
    ),
)


def contains_sensitive_data(value: object) -> bool:
    text = str(value or "")
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def redact_sensitive_data(value: object) -> str:
    """Yüksek güvenli anahtar/parola desenlerini log ve kalıcı kayıttan çıkarır."""
    text = str(value or "")
    for env_name in ("GROQ_API_KEY", "YOUTUBE_API_KEY"):
        secret = os.getenv(env_name, "").strip()
        if len(secret) >= 8:
            text = text.replace(secret, f"[{env_name}:GİZLENDİ]")
    text = _SECRET_PATTERNS[0].sub("[ÖZEL_ANAHTAR:GİZLENDİ]", text)
    for pattern in _SECRET_PATTERNS[1:5]:
        text = pattern.sub("[ERİŞİM_ANAHTARI:GİZLENDİ]", text)
    text = _SECRET_PATTERNS[5].sub(lambda m: f"{m.group(1)}=[GİZLENDİ]", text)
    return text


def safe_error(error: BaseException, limit: int = 500) -> str:
    clean = redact_sensitive_data(str(error)).replace("\x00", "")
    return clean[:limit] or error.__class__.__name__


def sanitize_untrusted_text(value: object, max_length: int = 4000) -> str:
    text = str(value or "")
    text = "".join(char for char in text if char in "\n\t" or ord(char) >= 32)
    return redact_sensitive_data(text)[:max_length]


def clean_single_line(value: object, *, name: str, max_length: int = MAX_SHORT_TEXT) -> str:
    raw = str(value or "").strip()
    if any(ord(char) < 32 for char in raw):
        raise ValueError(f"{name} kontrol karakteri içeremez.")
    text = " ".join(raw.split())
    if not text:
        raise ValueError(f"{name} boş olamaz.")
    if len(text) > max_length:
        raise ValueError(f"{name} {max_length} karakter sınırını aşıyor.")
    return text


def validate_user_text(value: object, *, name: str, max_length: int = MAX_USER_TEXT) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} boş olamaz.")
    if len(text) > max_length:
        raise ValueError(f"{name} {max_length} karakter sınırını aşıyor.")
    if "\x00" in text:
        raise ValueError(f"{name} ikili içerik taşıyamaz.")
    return text


def validate_loopback_url(value: str) -> str:
    """Ollama adresini yalnızca bu bilgisayardaki HTTP(S) servisiyle sınırlar."""
    parsed = urlsplit((value or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Yerel model adresi yalnızca http veya https kullanabilir.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Yerel model adresi kimlik bilgisi, sorgu veya parça içeremez.")
    hostname = (parsed.hostname or "").casefold()
    is_loopback = hostname == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = False
    if not is_loopback:
        raise ValueError("Ollama adresi güvenlik nedeniyle yalnızca localhost olabilir.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Yerel model portu geçersiz.") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Yerel model portu geçersiz.")
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None:
        netloc += f":{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), "", ""))


def validate_https_url(value: str, *, allow_hosts: set[str] | None = None) -> str:
    parsed = urlsplit((value or "").strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Yalnızca geçerli HTTPS adresleri açılabilir.")
    if parsed.username or parsed.password:
        raise ValueError("Adres içinde kullanıcı adı veya parola bulunamaz.")
    hostname = parsed.hostname.casefold().rstrip(".")
    if allow_hosts and hostname not in {host.casefold() for host in allow_hosts}:
        raise ValueError("Bu alan adına izin verilmiyor.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local):
        raise ValueError("Yerel veya özel ağ adresleri tarayıcıdan açılamaz.")
    if len(value) > 2048:
        raise ValueError("Adres çok uzun.")
    return value


def secure_write_text(path: str | Path, content: str) -> None:
    """Aynı klasörde 0600 geçici dosya kullanarak atomik ve özel yazım yapar."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError("Sembolik bağlantı üzerine güvenli veri yazılamaz.")
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        try:
            os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        except (AttributeError, OSError):
            pass
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        try:
            os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def secure_write_bytes(path: str | Path, content: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError("Sembolik bağlantı üzerine güvenli veri yazılamaz.")
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        try:
            os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        except (AttributeError, OSError):
            pass
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        try:
            os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def secure_write_json(path: str | Path, data: object) -> None:
    secure_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def bounded_json_load(path: str | Path, *, max_bytes: int = 5 * 1024 * 1024):
    target = Path(path)
    if target.is_symlink():
        raise ValueError("Sembolik bağlantıdan veri yüklenemez.")
    if target.stat().st_size > max_bytes:
        raise ValueError("Yerel veri dosyası boyut sınırını aşıyor.")
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)
