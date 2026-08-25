"""Küçük metin ve kod dosyaları için güvenli, salt okunur içerik okuyucu."""

from __future__ import annotations

import os
from pathlib import Path

from utils.config import BASE_DIR
from services.security import contains_sensitive_data


ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".html", ".css", ".sql",
    ".csv", ".log", ".java", ".cs", ".cpp", ".c", ".h", ".rs", ".go",
}
SENSITIVE_NAMES = {
    ".env", "credentials.json", "token.json", "token.dat", "id_rsa", "id_ed25519",
    ".npmrc", ".pypirc", ".netrc", "secrets.json",
}
SENSITIVE_PARTS = {".ssh", ".gnupg", ".aws", ".azure"}
MAX_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_CHARS = 24_000


def read_text_file(path: str) -> dict:
    raw = os.path.expandvars(os.path.expanduser((path or "").strip().strip('"')))
    if not raw:
        raise ValueError("Dosya yolu gerekli.")
    candidate = Path(raw)
    if candidate.is_symlink():
        raise ValueError("Sembolik bağlantıdan dosya okunamaz.")
    target = candidate.resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Dosya bulunamadı: {target}")
    allowed_roots = (Path.home().resolve(), Path(BASE_DIR).resolve())
    if not any(_is_within(target, root) for root in allowed_roots):
        raise ValueError("Dosya kullanıcı veya proje klasörü dışında okunamaz.")
    if target.is_symlink() or _is_sensitive(target):
        raise ValueError("Bu dosya güvenlik nedeniyle sohbetten okunamıyor.")
    if target.suffix.casefold() not in ALLOWED_EXTENSIONS:
        raise ValueError("Bu dosya türü güvenlik nedeniyle sohbetten okunamıyor.")
    size = target.stat().st_size
    if size > MAX_BYTES:
        raise ValueError("Dosya 2 MB sınırını aşıyor; önce daha küçük bir bölüm seç.")
    data = target.read_bytes()
    if b"\x00" in data[:4096]:
        raise ValueError("Dosya ikili içerik taşıyor; metin olarak okunamaz.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("cp1254", errors="replace")
    if contains_sensitive_data(text):
        raise ValueError("Dosyada parola veya API anahtarı benzeri gizli bilgi algılandı.")
    truncated = len(text) > MAX_OUTPUT_CHARS
    return {
        "path": str(target),
        "name": target.name,
        "size": size,
        "content": text[:MAX_OUTPUT_CHARS],
        "truncated": truncated,
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_sensitive(path: Path) -> bool:
    name = path.name.casefold()
    if name in SENSITIVE_NAMES or name.startswith(".env."):
        return True
    return any(part.casefold() in SENSITIVE_PARTS for part in path.parts)
