import os
from pathlib import Path

def _get_desktop() -> Path:
    paths = [
        Path.home() / "OneDrive" / "Desktop",
        Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Desktop",
        Path.home() / "Desktop",
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
    ]
    for p in paths:
        if p.exists():
            return p
    return Path.home() / "Desktop"

def _get_downloads() -> Path:
    paths = [
        Path.home() / "OneDrive" / "Downloads",
        Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Downloads",
        Path.home() / "Downloads",
        Path(os.environ.get("USERPROFILE", "")) / "Downloads",
    ]
    for p in paths:
        if p.exists():
            return p
    return Path.home() / "Downloads"

FOLDERS = {
    "masaüstü": _get_desktop(),
    "masaustu": _get_desktop(),
    "indirmeler": _get_downloads(),
    "downloads": _get_downloads(),
    "belgeler": Path.home() / "Documents",
    "documents": Path.home() / "Documents",
    "resimler": Path.home() / "Pictures",
    "pictures": Path.home() / "Pictures",
    "müzik": Path.home() / "Music",
    "muzik": Path.home() / "Music",
    "videolar": Path.home() / "Videos",
    "videos": Path.home() / "Videos",
}

def handle_file_command(message: str) -> str | None:
    msg = message.lower().strip()

    if any(word in msg for word in ["aç", "göster"]):
        folder_mentioned = any(name in msg for name in FOLDERS.keys())
        
        if not folder_mentioned:
            query = msg
            for sw in ["klasörünü", "klasörü", "dosyayı", "aç", "göster", "lütfen"]:
                query = query.replace(sw, "").strip()
            if query:
                target = _get_desktop() / query
                if target.exists():
                    os.startfile(str(target))
                    return f"📁 '{query}' açıldı."
                return _open_file(query)
        
        for name, path in FOLDERS.items():
            if name in msg:
                idx = msg.index(name) + len(name)
                rest = msg[idx:].strip()
                for sw in ["klasörünü", "klasörü", "aç", "göster"]:
                    rest = rest.replace(sw, "").strip()
                
                if rest:
                    target = path / rest
                    if target.exists():
                        os.startfile(str(target))
                        return f"📁 '{rest}' açıldı."
                    else:
                        return _open_file(rest)
                else:
                    if path.exists():
                        os.startfile(str(path))
                        return f"📁 {name.capitalize()} klasörü açıldı."
                    else:
                        return f"⚠️ {name.capitalize()} klasörü bulunamadı."

    if "dosyayı aç" in msg or "dosya aç" in msg:
        query = _extract_filename(msg)
        if query:
            return _open_file(query)

    if any(word in msg for word in ["listele", "ne var", "içinde ne", "içeriği"]):
        for name, path in FOLDERS.items():
            if name in msg:
                return _list_folder(path, name)

    if any(word in msg for word in ["ara", "bul", "nerede", "dosyayı bul"]):
        query = _extract_filename(msg)
        if query:
            return _search_file(query)

    if any(word in msg for word in ["sil", "kaldır", "delete"]):
        query = _extract_filename(msg)
        if query:
            return _delete_file(query)

    return None

def _open_file(query: str) -> str:
    search_dirs = [_get_desktop(), Path.home() / "Documents", _get_downloads()]
    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in directory.rglob(f"*{query}*"):
            if path.is_file():
                os.startfile(str(path))
                return f"📄 '{path.name}' açıldı."
    return f"🔍 '{query}' dosyası bulunamadı."

def _list_folder(path: Path, name: str) -> str:
    try:
        items = list(path.iterdir())
        if not items:
            return f"📂 {name.capitalize()} klasörü boş."

        folders = sorted([i.name for i in items if i.is_dir()])
        files = sorted([i.name for i in items if i.is_file()])

        lines = [f"📂 **{name.capitalize()}** — {len(items)} öğe\n"]

        if folders:
            lines.append(f"**Klasörler ({len(folders)}):**")
            for f in folders[:10]:
                lines.append(f"  📁 {f}")
            if len(folders) > 10:
                lines.append(f"  ... ve {len(folders) - 10} klasör daha")

        if files:
            lines.append(f"\n**Dosyalar ({len(files)}):**")
            for f in files[:15]:
                lines.append(f"  📄 {f}")
            if len(files) > 15:
                lines.append(f"  ... ve {len(files) - 15} dosya daha")

        return "\n".join(lines)
    except PermissionError:
        return f"⚠️ {name.capitalize()} klasörüne erişim izni yok."
    except Exception as e:
        return f"⚠️ Hata: {str(e)}"

def _search_file(query: str) -> str:
    try:
        search_dirs = [
            _get_desktop(),
            Path.home() / "Documents",
            _get_downloads(),
        ]

        results = []
        for directory in search_dirs:
            if not directory.exists():
                continue
            for path in directory.rglob(f"*{query}*"):
                results.append(str(path))
                if len(results) >= 10:
                    break

        if not results:
            return f"🔍 '{query}' ile eşleşen dosya bulunamadı."

        lines = [f"🔍 **'{query}'** için {len(results)} sonuç:\n"]
        for r in results:
            lines.append(f"  📄 {r}")

        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Arama hatası: {str(e)}"

def _delete_file(query: str) -> str:
    try:
        search_dirs = [_get_desktop(), Path.home() / "Documents", _get_downloads()]

        found = []
        for directory in search_dirs:
            if not directory.exists():
                continue
            for path in directory.rglob(f"*{query}*"):
                if path.is_file():
                    found.append(path)

        if not found:
            return f"🔍 '{query}' ile eşleşen dosya bulunamadı."

        if len(found) > 1:
            lines = ["⚠️ Birden fazla dosya bulundu, hangisini silmek istiyorsun?"]
            for f in found:
                lines.append(f"  📄 {f}")
            return "\n".join(lines)

        path = found[0]
        path.unlink()
        return f"🗑️ '{path.name}' silindi."

    except PermissionError:
        return "⚠️ Bu dosyayı silmek için izin yok."
    except Exception as e:
        return f"⚠️ Silme hatası: {str(e)}"

def _extract_filename(message: str) -> str:
    msg = message.lower().strip()

    if '"' in message:
        parts = message.split('"')
        if len(parts) >= 3:
            return parts[1].strip()

    stop_words = [
        "dosyayı", "dosyasını", "klasörü", "bul", "ara", "sil",
        "kaldır", "nerede", "aç", "listele", "içinde"
    ]
    for word in stop_words:
        msg = msg.replace(word, "").strip()

    return msg.strip()