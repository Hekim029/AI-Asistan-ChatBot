import os
import difflib
from pathlib import Path

from services.security import safe_error


BLOCKED_OPEN_EXTENSIONS = {
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe",
    ".js", ".jse", ".wsf", ".wsh", ".scr", ".msi", ".msp", ".hta",
    ".reg", ".lnk", ".url", ".cpl", ".jar",
}
MAX_SCAN_ITEMS = 20_000


# ─────────────────────────────────────────────
#  Sistem klasörleri
# ─────────────────────────────────────────────

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
    "masaüstü":   _get_desktop(),
    "masaustu":   _get_desktop(),
    "indirmeler": _get_downloads(),
    "downloads":  _get_downloads(),
    "belgeler":   Path.home() / "Documents",
    "documents":  Path.home() / "Documents",
    "resimler":   Path.home() / "Pictures",
    "pictures":   Path.home() / "Pictures",
    "müzik":      Path.home() / "Music",
    "muzik":      Path.home() / "Music",
    "videolar":   Path.home() / "Videos",
    "videos":     Path.home() / "Videos",
}


# Target'tan temizlenecek kelimeler (fiil, ek, soru edatı)
_NOISE_WORDS = {
    "klasörüme", "klasörünü", "klasörümü", "klasörü", "klasöre", "klasör",
    "dosyasını", "dosyamı", "dosyayı", "dosyası", "dosya",
    "git", "gel", "aç", "açar", "aç", "göster", "getir", "bul",
    "mısın", "misin", "musun", "müsün", "mi", "mı", "mu", "mü",
    "lütfen", "bana", "benim", "bir", "şu", "o",
}


# ─────────────────────────────────────────────
#  Ana giriş noktası
# ─────────────────────────────────────────────

def handle_file_command(message: str, llm_client=None) -> str | None:
    """
    llm_client verilirse doğal dil parsing kullanır.
    Verilmezse eski keyword tabanlı yönteme düşer.
    """
    if llm_client:
        return _handle_with_llm(message, llm_client)
    return _handle_keyword(message)


# ─────────────────────────────────────────────
#  LLM tabanlı parsing
# ─────────────────────────────────────────────

def _handle_with_llm(message: str, llm_client) -> str | None:
    cmd = llm_client.extract_file_command(message)

    action   = cmd.get("action", "open")
    raw      = cmd.get("target", "")
    location = cmd.get("location", "").strip().lower()

    target    = _clean_target(raw)
    base_path = FOLDERS.get(location, _get_desktop())

    if action == "open":
        return _smart_open(target, base_path)
    elif action == "list":
        return _list_folder(base_path, location or "masaüstü")
    elif action == "search":
        return _search_file(target) if target else "🔍 Ne aramamı istersin?"
    elif action == "delete":
        return _delete_file(target) if target else "⚠️ Hangi dosyayı silmemi istersin?"

    return None


def _clean_target(target: str) -> str:
    """
    LLM'den gelen ham target'ı temizler.

    Örnekler:
      "ChatBot'ı"           -> "ChatBot"
      "chatbot me"          -> "chatbot"
      "ChatBot klasörüme"   -> "ChatBot"
      "ChatBot açar mısın"  -> "ChatBot"

    Mantık:
      1) Apostrof varsa öncesini al (Türkçe özel isim eki: ChatBot'ı)
      2) Kelimelere böl, gürültü kelimelerini at
      3) Kalan 1-2 harflik parçaları at (ek kalıntısı)
    """
    if not target:
        return ""

    # 1) Apostrof temizliği — hem düz hem eğik tırnak
    for apo in ["'", "'", "`", "´"]:
        if apo in target:
            target = target.split(apo)[0]

    # 2) Gürültü kelimelerini at
    words = target.strip().split()
    kept = []
    for w in words:
        stripped = w.strip(".,!?;:").lower()
        if stripped in _NOISE_WORDS:
            continue
        # 3) Tek/çift harflik kalıntı (Türkçe ek parçası) at
        if len(stripped) <= 2 and not stripped.isdigit():
            continue
        kept.append(w)

    return " ".join(kept).strip()


def _smart_open(target: str, base_path: Path) -> str:
    """
    Hedefi 4 kademede arar:
      1) Direkt eşleşme
      2) Büyük/küçük harf farksız eşleşme
      3) Kısmi eşleşme (substring)
      4) FUZZY — yazım hatası toleransı ("CahtBot" -> "ChatBot")
    """
    if not target:
        if base_path.exists():
            os.startfile(str(base_path))
            return f"📁 {base_path.name} klasörü açıldı."
        return "⚠️ Klasör bulunamadı."

    try:
        target = _validate_search_query(target)
    except ValueError as exc:
        return f"⚠️ {exc}"

    # Klasördeki tüm öğeleri bir kez oku
    try:
        items = list(base_path.iterdir())
    except Exception:
        items = []

    names = [i.name for i in items]

    # 1) Direkt eşleşme
    direct = (base_path / target).resolve()
    try:
        direct.relative_to(base_path.resolve())
    except ValueError:
        return "⚠️ Ana klasör dışındaki bir hedef açılamaz."
    if direct.exists():
        if not _is_safe_to_open(direct):
            return "⚠️ Yürütülebilir veya kısayol dosyaları sohbetten açılamaz."
        os.startfile(str(direct))
        return f"📁 '{target}' açıldı."

    # 2) Case-insensitive tam eşleşme
    for item in items:
        if item.name.lower() == target.lower():
            if not _is_safe_to_open(item):
                return "⚠️ Yürütülebilir veya kısayol dosyaları sohbetten açılamaz."
            os.startfile(str(item))
            return f"📁 '{item.name}' açıldı."

    # 3) Kısmi eşleşme (substring)
    partial = [i for i in items if target.lower() in i.name.lower()]
    if len(partial) == 1:
        if not _is_safe_to_open(partial[0]):
            return "⚠️ Yürütülebilir veya kısayol dosyaları sohbetten açılamaz."
        os.startfile(str(partial[0]))
        return f"📁 '{partial[0].name}' açıldı."
    elif len(partial) > 1:
        shown = ", ".join(p.name for p in partial[:5])
        return f"🔍 Birden fazla eşleşme var: {shown}\nHangisini açmamı istersin?"

    # 4) FUZZY eşleşme — yazım hatası toleransı
    match = _fuzzy_match(target, names)
    if match:
        path = base_path / match
        if not _is_safe_to_open(path):
            return "⚠️ Yürütülebilir veya kısayol dosyaları sohbetten açılamaz."
        os.startfile(str(path))
        return f"📁 '{match}' açıldı. ('{target}' yazmışsın, bunu kastettin sanırım)"

    # 5) Son çare: diğer klasörlerde geniş arama
    return _open_file(target)


def _fuzzy_match(target: str, candidates: list[str], cutoff: float = 0.6) -> str | None:
    """
    Yazım hatası toleranslı eşleştirme.

    difflib.get_close_matches(): Python'un standart kütüphanesi.
    İki metnin harf dizilimini karşılaştırıp 0.0–1.0 arası benzerlik puanı verir.

      "CahtBot" vs "ChatBot" -> ~0.86  (yüksek, eşleşir)
      "ChatBot" vs "Belgeler" -> ~0.13 (düşük, eşleşmez)

    cutoff: Minimum benzerlik eşiği. 0.6 = %60 benzerlik.
            Düşürürsen daha toleranslı ama yanlış eşleşme riski artar.
    n=1: Sadece en iyi eşleşmeyi döndür.
    """
    if not target or not candidates:
        return None

    lower_map = {c.lower(): c for c in candidates}
    matches = difflib.get_close_matches(
        target.lower(),
        list(lower_map.keys()),
        n=1,
        cutoff=cutoff
    )
    return lower_map[matches[0]] if matches else None


# ─────────────────────────────────────────────
#  Keyword tabanlı yöntem (fallback)
# ─────────────────────────────────────────────

def _handle_keyword(message: str) -> str | None:
    msg = message.lower().strip()

    if any(word in msg for word in ["aç", "göster", "git"]):
        folder_mentioned = any(name in msg for name in FOLDERS.keys())

        if not folder_mentioned:
            query = msg
            for sw in ["klasörünü", "klasörü", "klasörüme", "dosyayı",
                       "aç", "göster", "git", "lütfen"]:
                query = query.replace(sw, "").strip()
            if query:
                return _smart_open(_clean_target(query), _get_desktop())

        for name, path in FOLDERS.items():
            if name in msg:
                idx = msg.index(name) + len(name)
                rest = msg[idx:].strip()
                for sw in ["klasörünü", "klasörü", "klasörüme", "aç", "göster", "git"]:
                    rest = rest.replace(sw, "").strip()

                # Kalan çok kısaysa Türkçe ek kalıntısıdır, yok say
                if len(rest) <= 2:
                    rest = ""

                if rest:
                    return _smart_open(_clean_target(rest), path)
                else:
                    if path.exists():
                        os.startfile(str(path))
                        return f"📁 {name.capitalize()} klasörü açıldı."
                    return f"⚠️ {name.capitalize()} klasörü bulunamadı."

    if any(word in msg for word in ["listele", "ne var", "içinde ne", "içeriği"]):
        for name, path in FOLDERS.items():
            if name in msg:
                return _list_folder(path, name)

    if any(word in msg for word in ["ara", "bul", "nerede"]):
        query = _extract_filename(msg)
        if query:
            return _search_file(query)

    if any(word in msg for word in ["sil", "kaldır", "delete"]):
        query = _extract_filename(msg)
        if query:
            return _delete_file(query)

    return None


# ─────────────────────────────────────────────
#  Ortak yardımcı fonksiyonlar
# ─────────────────────────────────────────────

def _open_file(query: str) -> str:
    """Tüm ana dizinlerde dosya arar, fuzzy destekli."""
    search_dirs = [_get_desktop(), Path.home() / "Documents", _get_downloads()]

    try:
        query = _validate_search_query(query)
    except ValueError as exc:
        return f"⚠️ {exc}"

    for path in _find_matches(query, search_dirs, limit=1):
        if not _is_safe_to_open(path):
            return "⚠️ Yürütülebilir veya kısayol dosyaları sohbetten açılamaz."
        os.startfile(str(path))
        return f"📄 '{path.name}' açıldı."

    # Sonra fuzzy — sadece üst seviye öğelerde
    for directory in search_dirs:
        if not directory.exists():
            continue
        try:
            names = [p.name for p in directory.iterdir()]
        except Exception:
            continue
        match = _fuzzy_match(query, names)
        if match:
            target = directory / match
            if not _is_safe_to_open(target):
                return "⚠️ Yürütülebilir veya kısayol dosyaları sohbetten açılamaz."
            os.startfile(str(target))
            return f"📄 '{match}' açıldı. ('{query}' yazmışsın, bunu kastettin sanırım)"

    return f"🔍 '{query}' bulunamadı."


def _list_folder(path: Path, name: str) -> str:
    try:
        items = list(path.iterdir())
        if not items:
            return f"📂 {name.capitalize()} klasörü boş."

        folders = sorted([i.name for i in items if i.is_dir()])
        files   = sorted([i.name for i in items if i.is_file()])
        lines   = [f"📂 **{name.capitalize()}** — {len(items)} öğe\n"]

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
        query = _validate_search_query(query)
        search_dirs = [_get_desktop(), Path.home() / "Documents", _get_downloads()]
        results = [str(path) for path in _find_matches(query, search_dirs, limit=10)]

        if not results:
            return f"🔍 '{query}' ile eşleşen dosya bulunamadı."

        lines = [f"🔍 **'{query}'** için {len(results)} sonuç:\n"]
        for r in results:
            lines.append(f"  📄 {r}")
        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Arama hatası: {safe_error(e)}"


def _delete_file(query: str) -> str:
    try:
        query = _validate_search_query(query)

        search_dirs = [_get_desktop(), Path.home() / "Documents", _get_downloads()]
        found = _find_matches(query, search_dirs, limit=50)

        if not found:
            return f"🔍 '{query}' ile eşleşen dosya bulunamadı."

        if len(found) > 1:
            lines = ["⚠️ Birden fazla dosya bulundu, hangisini silmek istiyorsun?"]
            for f in found:
                lines.append(f"  📄 {f}")
            return "\n".join(lines)

        path = found[0]
        from send2trash import send2trash

        send2trash(str(path))
        return f"🗑️ '{path.name}' çöp kutusuna taşındı."

    except PermissionError:
        return "⚠️ Bu dosyayı silmek için izin yok."
    except Exception as e:
        return f"⚠️ Silme hatası: {safe_error(e)}"


def _validate_search_query(query: str) -> str:
    text = " ".join((query or "").strip().split())
    if len(text) < 2:
        raise ValueError("Dosya adını daha açık belirtmelisin.")
    if len(text) > 200:
        raise ValueError("Dosya araması 200 karakter sınırını aşıyor.")
    if any(char in text for char in ("/", "\\", "*", "?", "[", "]")) or ".." in text:
        raise ValueError("Dosya aramasında yol veya joker karakter kullanılamaz.")
    if any(ord(char) < 32 for char in text):
        raise ValueError("Dosya araması kontrol karakteri içeremez.")
    return text


def _find_matches(query: str, directories: list[Path], limit: int) -> list[Path]:
    needle = query.casefold()
    results: list[Path] = []
    scanned = 0
    for directory in directories:
        if not directory.exists() or directory.is_symlink():
            continue
        for path in directory.rglob("*"):
            scanned += 1
            if scanned > MAX_SCAN_ITEMS:
                return results
            if path.is_symlink() or not path.is_file():
                continue
            if needle in path.name.casefold():
                results.append(path)
                if len(results) >= limit:
                    return results
    return results


def _is_safe_to_open(path: Path) -> bool:
    if path.is_symlink():
        return False
    return path.is_dir() or (
        path.is_file()
        and path.suffix.casefold() not in BLOCKED_OPEN_EXTENSIONS
    )


def _extract_filename(message: str) -> str:
    msg = message.lower().strip()
    if '"' in message:
        parts = message.split('"')
        if len(parts) >= 3:
            return parts[1].strip()
    stop_words = ["dosyayı", "dosyasını", "klasörü", "bul", "ara", "sil",
                  "kaldır", "nerede", "aç", "listele", "içinde"]
    for word in stop_words:
        msg = msg.replace(word, "").strip()
    return msg.strip()
