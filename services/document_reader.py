"""PDF ve DOCX dosyalarından güvenli, salt okunur metin çıkarımı."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader

from services.file_reader import _is_sensitive, _is_within
from services.security import contains_sensitive_data, sanitize_untrusted_text
from utils.config import BASE_DIR


ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx"}
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_CHARS = 30_000
MAX_PDF_PAGES = 80
MAX_DOCX_ENTRIES = 2_000
MAX_DOCX_UNCOMPRESSED = 100 * 1024 * 1024
MAX_DOCX_ENTRY_BYTES = 50 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250


def read_document(path: str) -> dict:
    target = _validated_document_path(path)
    if target.suffix.casefold() == ".pdf":
        content, units, truncated = _read_pdf(target)
        kind = "PDF"
        unit_name = "sayfa"
    else:
        _validate_docx_archive(target)
        content, units, truncated = _read_docx(target)
        kind = "Word (DOCX)"
        unit_name = "metin bölümü"

    if contains_sensitive_data(content):
        raise ValueError(
            "Belgede parola veya API anahtarı benzeri gizli bilgi algılandı."
        )
    content = sanitize_untrusted_text(content, MAX_OUTPUT_CHARS)
    if not content.strip():
        raise ValueError(
            "Belgede okunabilir metin bulunamadı. Taranmış PDF için OCR desteği gerekir."
        )
    return {
        "path": str(target),
        "name": target.name,
        "kind": kind,
        "size": target.stat().st_size,
        "unit_count": units,
        "unit_name": unit_name,
        "content": content,
        "truncated": truncated,
    }


def _validated_document_path(path: str) -> Path:
    raw = os.path.expandvars(os.path.expanduser((path or "").strip().strip('"')))
    if not raw:
        raise ValueError("PDF veya DOCX dosya yolu gerekli.")
    candidate = Path(raw)
    if candidate.is_symlink():
        raise ValueError("Sembolik bağlantıdan belge okunamaz.")
    target = candidate.resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Belge bulunamadı: {target}")
    allowed_roots = (Path.home().resolve(), Path(BASE_DIR).resolve())
    if not any(_is_within(target, root) for root in allowed_roots):
        raise ValueError("Belge kullanıcı veya proje klasörü dışında okunamaz.")
    if target.is_symlink() or _is_sensitive(target):
        raise ValueError("Bu belge güvenlik nedeniyle sohbetten okunamıyor.")
    if target.suffix.casefold() not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValueError("Yalnızca .pdf ve .docx belgeleri destekleniyor.")
    size = target.stat().st_size
    if size <= 0:
        raise ValueError("Belge boş.")
    if size > MAX_DOCUMENT_BYTES:
        raise ValueError("Belge 20 MB güvenlik sınırını aşıyor.")
    return target


def _read_pdf(path: Path) -> tuple[str, int, bool]:
    with path.open("rb") as handle:
        reader = PdfReader(handle, strict=True)
        if reader.is_encrypted:
            raise ValueError("Parolalı/şifreli PDF belgeleri desteklenmiyor.")
        page_count = len(reader.pages)
        parts: list[str] = []
        length = 0
        truncated = page_count > MAX_PDF_PAGES
        for index, page in enumerate(reader.pages[:MAX_PDF_PAGES], start=1):
            page_text = page.extract_text() or ""
            section = f"[Sayfa {index}]\n{page_text.strip()}"
            parts.append(section)
            length += len(section)
            if length >= MAX_OUTPUT_CHARS:
                truncated = True
                break
    return "\n\n".join(parts)[:MAX_OUTPUT_CHARS], page_count, truncated


def _validate_docx_archive(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise ValueError("DOCX dosyası geçerli bir Office arşivi değil.")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_DOCX_ENTRIES:
            raise ValueError("DOCX çok fazla arşiv girdisi içeriyor.")
        total_size = sum(item.file_size for item in entries)
        total_compressed = sum(item.compress_size for item in entries)
        if total_size > MAX_DOCX_UNCOMPRESSED:
            raise ValueError("DOCX açıldığında 100 MB sınırını aşıyor.")
        if any(item.file_size > MAX_DOCX_ENTRY_BYTES for item in entries):
            raise ValueError("DOCX içinde aşırı büyük bir bileşen var.")
        if total_size / max(total_compressed, 1) > MAX_COMPRESSION_RATIO:
            raise ValueError("DOCX güvenli olmayan sıkıştırma oranına sahip.")
        lowered = {item.filename.casefold() for item in entries}
        if any(
            "vbaproject.bin" in name or "/embeddings/" in f"/{name}"
            for name in lowered
        ):
            raise ValueError("Makro veya gömülü nesne içeren Word belgesi desteklenmiyor.")


def _read_docx(path: Path) -> tuple[str, int, bool]:
    with zipfile.ZipFile(path) as archive:
        try:
            document_xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError("DOCX ana belge içeriğini taşımıyor.") from exc
    lowered = document_xml[:4096].lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("DOCX güvenli olmayan XML tanımı içeriyor.")
    try:
        root = SafeET.fromstring(document_xml)
    except (ParseError, DefusedXmlException) as exc:
        raise ValueError("DOCX belge XML'i bozuk.") from exc

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def node_text(node) -> str:
        return "".join(
            element.text or ""
            for element in node.iter(f"{namespace}t")
        ).strip()

    parts: list[str] = []
    body = root.find(f"{namespace}body")
    for child in list(body) if body is not None else []:
        if child.tag == f"{namespace}p":
            text = node_text(child)
            if text:
                parts.append(text)
        elif child.tag == f"{namespace}tbl":
            for row in child.iter(f"{namespace}tr"):
                cells = [node_text(cell) for cell in row.findall(f"{namespace}tc")]
                if any(cells):
                    parts.append(" | ".join(cells))
    parts = [part for part in parts if part]
    full_text = "\n".join(parts)
    return full_text[:MAX_OUTPUT_CHARS], len(parts), len(full_text) > MAX_OUTPUT_CHARS
