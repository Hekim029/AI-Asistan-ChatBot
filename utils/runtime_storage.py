"""Kaynak çalışma ve paketli uygulama için güvenli veri dizini seçimi."""

from __future__ import annotations

import os
from pathlib import Path

from services.security import secure_write_bytes


_LEGACY_FILES = frozenset({
    "app_settings.json",
    "daily_briefing_config.json",
    "daily_briefing_state.json",
    "daily_motivation.json",
    "history.json",
    "local_model_settings.json",
    "reminders.json",
    "session_names.json",
    "shared_workspace.json",
    "tasks.json",
    "token.dat",
    "token.json",
    "user_memory.json",
})
_LEGACY_DIRECTORIES = frozenset({"sessions", "project_backups"})
_MAX_MIGRATION_FILES = 1_000
_MAX_MIGRATION_FILE_BYTES = 16 * 1024 * 1024
_MAX_MIGRATION_TOTAL_BYTES = 256 * 1024 * 1024


def runtime_data_dir(base_dir: str | Path, *, frozen: bool) -> Path:
    """Paketli uygulamada yazılabilir kullanıcı dizinini, kaynakta memory/ döndürür."""
    base = Path(base_dir).resolve()
    if not frozen:
        return base / "memory"

    configured = os.environ.get("LOCALAPPDATA", "").strip()
    local_root = Path(configured).expanduser() if configured else Path.home() / "AppData" / "Local"
    if not local_root.is_absolute():
        local_root = Path.home() / "AppData" / "Local"
    return local_root.resolve() / "HekoAI" / "data"


def migrate_legacy_data(legacy_dir: str | Path, target_dir: str | Path) -> int:
    """Eski EXE-yanı memory verisini, üzerine yazmadan yeni dizine taşır."""
    legacy = Path(legacy_dir)
    target = Path(target_dir)
    if not legacy.is_dir() or legacy.is_symlink():
        return 0
    if target.exists() and target.is_symlink():
        raise ValueError("Uygulama veri klasörü sembolik bağlantı olamaz.")
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        return 0

    candidates: list[tuple[Path, Path]] = []
    for name in sorted(_LEGACY_FILES):
        source = legacy / name
        if source.is_file() and not source.is_symlink():
            candidates.append((source, target / name))
    for directory_name in sorted(_LEGACY_DIRECTORIES):
        directory = legacy / directory_name
        if not directory.is_dir() or directory.is_symlink():
            continue
        for source in directory.rglob("*"):
            if source.is_file() and not source.is_symlink():
                candidates.append((source, target / source.relative_to(legacy)))

    copied = 0
    total_bytes = 0
    for source, destination in candidates[:_MAX_MIGRATION_FILES]:
        size = source.stat().st_size
        if size > _MAX_MIGRATION_FILE_BYTES:
            continue
        if total_bytes + size > _MAX_MIGRATION_TOTAL_BYTES:
            break
        secure_write_bytes(destination, source.read_bytes())
        total_bytes += size
        copied += 1
    return copied


def prepare_runtime_data_dir(base_dir: str | Path, *, frozen: bool) -> Path:
    """Hedefi hazırlar ve yalnızca paketli sürümde eski kayıtları bir kez geçirir."""
    target = runtime_data_dir(base_dir, frozen=frozen)
    if frozen:
        migrate_legacy_data(Path(base_dir) / "memory", target)
    else:
        target.mkdir(parents=True, exist_ok=True)
    return target
