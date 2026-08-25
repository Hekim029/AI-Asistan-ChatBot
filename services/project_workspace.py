"""Güvenli proje okuma, listeleme ve onaylı dosya güncelleme servisi."""

from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from services.file_reader import ALLOWED_EXTENSIONS, SENSITIVE_NAMES
from utils.config import BASE_DIR, MEMORY_DIR
from services.security import contains_sensitive_data


IGNORED_PARTS = {
    ".git", ".idea", ".vscode", "__pycache__", "venv", ".venv",
    "node_modules", "build", "dist", ".pytest_cache", ".mypy_cache",
}
RUNTIME_MEMORY_PARTS = {"sessions", "project_backups"}
_WRITE_LOCK = threading.RLock()
MAX_PROJECT_FILES = 500
MAX_WRITE_CHARS = 80_000


class ProjectWorkspace:
    def __init__(self, root: str | None = None, backup_root: str | None = None):
        configured = root or os.getenv("HEKO_PROJECT_ROOT") or BASE_DIR
        self.root = Path(configured).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"Proje klasörü bulunamadı: {self.root}")
        if self.root.parent == self.root or self.root == Path.home().resolve():
            raise ValueError("Proje kökü disk veya kullanıcı ana klasörü kadar geniş olamaz.")
        self.backup_root = Path(backup_root or (Path(MEMORY_DIR) / "project_backups"))

    def list_files(self, query: str = "", limit: int = 120) -> dict:
        needle = query.strip().casefold()
        cap = min(max(1, int(limit)), MAX_PROJECT_FILES)
        results: list[str] = []
        for path in sorted(self.root.rglob("*")):
            if len(results) >= cap:
                break
            if (
                not path.is_file()
                or self._is_ignored(path)
                or path.suffix.casefold() not in ALLOWED_EXTENSIONS
            ):
                continue
            relative = path.relative_to(self.root).as_posix()
            if needle and needle not in relative.casefold():
                continue
            results.append(relative)
        return {"root": str(self.root), "files": results, "truncated": len(results) >= cap}

    def read_file(self, relative_path: str) -> dict:
        target = self._resolve(relative_path)
        self._validate_text_target(target, must_exist=True)
        content = self._read(target)
        if contains_sensitive_data(content):
            raise ValueError("Dosyada parola veya API anahtarı benzeri gizli bilgi algılandı.")
        return {
            "path": target.relative_to(self.root).as_posix(),
            "content": content,
            "sha256": self._digest(content),
            "size": target.stat().st_size,
        }

    def preview_change(self, relative_path: str, new_content: str,
                       expected_sha256: str = "") -> dict:
        target = self._resolve(relative_path)
        self._validate_text_target(target, must_exist=False)
        self._validate_content(new_content)
        old_content = self._read(target) if target.exists() else ""
        current_hash = self._digest(old_content)
        if target.exists() and not expected_sha256:
            raise ValueError("Mevcut dosya önce okunmalı ve expected_sha256 verilmelidir.")
        if expected_sha256 and expected_sha256 != current_hash:
            raise ValueError("Dosya okunduktan sonra değişmiş; yeni içeriği tekrar hazırla.")
        relative = target.relative_to(self.root).as_posix()
        diff = "".join(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{relative}", tofile=f"b/{relative}",
        ))
        return {
            "path": relative,
            "old_sha256": current_hash,
            "new_sha256": self._digest(new_content),
            "diff": diff or "(İçerik değişikliği yok.)",
            "changed": old_content != new_content,
            "is_new": not target.exists(),
        }

    def apply_change(self, relative_path: str, new_content: str,
                     expected_sha256: str = "") -> dict:
        with _WRITE_LOCK:
            preview = self.preview_change(relative_path, new_content, expected_sha256)
            if not preview["changed"]:
                return {**preview, "backup": ""}
            target = self._resolve(relative_path)
            backup = ""
            if target.exists():
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                backup_target = (self.backup_root / stamp
                                 / target.relative_to(self.root))
                backup_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_target)
                backup = str(backup_target)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                    handle.write(new_content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, target)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            return {**preview, "backup": backup}

    def trash_file(self, relative_path: str) -> dict:
        """Bir proje dosyasını yalnızca doğrulanan kökten Çöp Kutusu'na taşır."""
        with _WRITE_LOCK:
            preview = self.preview_delete(relative_path)
            target = self._resolve(preview["path"])
            from send2trash import send2trash
            send2trash(str(target))
            return preview

    def preview_delete(self, relative_path: str) -> dict:
        target = self._resolve(relative_path)
        self._validate_text_target(target, must_exist=True)
        return {
            "path": target.relative_to(self.root).as_posix(),
            "size": target.stat().st_size,
        }

    def _resolve(self, relative_path: str) -> Path:
        raw = (relative_path or "").strip().replace("\\", "/")
        if not raw:
            raise ValueError("Proje içindeki göreli dosya yolu gerekli.")
        candidate = Path(raw)
        if candidate.is_absolute():
            raise ValueError("Tam yol yerine proje içindeki göreli yolu kullan.")
        unresolved = self.root / candidate
        if unresolved.is_symlink():
            raise ValueError("Sembolik bağlantıdaki proje dosyasına erişilemez.")
        target = unresolved.resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Proje klasörü dışına çıkılamaz.") from exc
        if self._is_ignored(target):
            raise ValueError("Bu proje klasörü güvenlik veya performans nedeniyle kapalı.")
        return target

    def _is_ignored(self, path: Path) -> bool:
        try:
            parts = path.relative_to(self.root).parts
        except ValueError:
            return True
        folded = tuple(part.casefold() for part in parts)
        if any(part in IGNORED_PARTS for part in folded):
            return True
        if folded and folded[0] == "memory":
            if any(part in RUNTIME_MEMORY_PARTS for part in folded[1:]):
                return True
            if path.suffix.casefold() != ".py":
                return True
        return False

    @staticmethod
    def _validate_content(content: str):
        if not isinstance(content, str):
            raise ValueError("Yeni dosya içeriği metin olmalı.")
        if len(content) > MAX_WRITE_CHARS:
            raise ValueError("Tek değişiklik 80.000 karakter sınırını aşıyor.")
        if "\x00" in content:
            raise ValueError("İkili içerik proje dosyasına yazılamaz.")
        if contains_sensitive_data(content):
            raise ValueError("Kod içeriğinde parola veya API anahtarı benzeri gizli bilgi algılandı.")

    @staticmethod
    def _read(path: Path) -> str:
        data = path.read_bytes()
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("Dosya 2 MB sınırını aşıyor.")
        if b"\x00" in data[:4096]:
            raise ValueError("İkili dosyalar desteklenmiyor.")
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("cp1254", errors="replace")

    @staticmethod
    def _digest(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_text_target(path: Path, must_exist: bool):
        if must_exist and not path.is_file():
            raise FileNotFoundError(f"Proje dosyası bulunamadı: {path.name}")
        if path.exists() and not path.is_file():
            raise ValueError("Hedef bir dosya olmalı.")
        if path.name.casefold() in SENSITIVE_NAMES or path.name.casefold().startswith(".env."):
            raise ValueError("Hassas dosyalar sohbetten okunamaz veya değiştirilemez.")
        if path.suffix.casefold() not in ALLOWED_EXTENSIONS:
            raise ValueError("Bu dosya uzantısı proje çalışma alanında desteklenmiyor.")
