"""Küçük metin ve kod dosyaları için güvenli, salt okunur içerik okuyucu."""

from __future__ import annotations

import os
from pathlib import Path


ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".html", ".css", ".sql",
    ".csv", ".log", ".java", ".cs", ".cpp", ".c", ".h", ".rs", ".go",
}
SENSITIVE_NAMES = {
    ".env", "credentials.json", "token.json", "id_rsa", "id_ed25519",
}
MAX_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_CHARS = 24_000


def read_text_file(path: str) -> dict:
    raw = os.path.expandvars(os.path.expanduser((path or "").strip().strip('"')))
    if not raw:
        raise ValueError("Dosya yolu gerekli.")
    target = Path(raw).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Dosya bulunamadı: {target}")
    if target.name.casefold() in SENSITIVE_NAMES or target.suffix.casefold() not in ALLOWED_EXTENSIONS:
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
    truncated = len(text) > MAX_OUTPUT_CHARS
    return {
        "path": str(target),
        "name": target.name,
        "size": size,
        "content": text[:MAX_OUTPUT_CHARS],
        "truncated": truncated,
    }
