"""Açık kullanıcı onayıyla alınan tek ekran karesini Groq Vision ile yorumlar."""

from __future__ import annotations

import base64
import binascii
import json
import re

import requests

from services.security import redact_sensitive_data, safe_error


MAX_DATA_URI_CHARS = 3_800_000
ALLOWED_PREFIXES = ("data:image/jpeg;base64,", "data:image/png;base64,")


def _one_line(value: object, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return redact_sensitive_data(text)[:limit]


def format_screen_analysis(content: object) -> str:
    """Modelin JSON yanıtını kısa metne çevirir; ham OCR/kod dökümünü engeller."""
    raw = str(content or "").strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.I | re.S).strip()
    unfenced = re.sub(r"^```(?:json|text)?\s*|\s*```$", "", raw, flags=re.I | re.S).strip()
    try:
        data = json.loads(unfenced)
    except (json.JSONDecodeError, TypeError, ValueError):
        data = None

    if isinstance(data, dict):
        summary = _one_line(data.get("summary", ""), 500)
        details = data.get("details", [])
        warning = _one_line(data.get("warning", ""), 350)
        if not isinstance(details, list):
            details = []
        clean_details = [
            _one_line(item, 350) for item in details[:4] if _one_line(item, 350)
        ]
        if summary:
            lines = [f"Ekran özeti: {summary}"]
            lines.extend(f"- {item}" for item in clean_details)
            if warning:
                lines.append(f"Uyarı: {warning}")
            return "\n".join(lines)

    # JSON modu beklenmedik biçimde bozulursa Markdown kod bloklarını ve yalnız
    # kalan madde işaretlerini kullanıcıya taşımadan anlaşılır bir yedek üret.
    lines = []
    for line in unfenced.replace("\t", " ").splitlines():
        clean = re.sub(r"^\s*(?:[-*•◦○]+|\d+[.)])\s*", "", line).strip()
        if not clean or not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", clean):
            continue
        lines.append(clean)
    joined = " ".join(lines)
    lowered = joined.casefold()
    if any(token in lowered for token in ("powershell", "ps c:\\", "(venv)", "terminal")):
        return (
            "Ekran özeti: Bir PowerShell veya terminal penceresi ile komut "
            "çıktıları görünüyor. Model ayrıntıları düzenli biçimde özetleyemedi."
        )
    if len(lines) > 8 or (lines and sum(map(len, lines)) / len(lines) < 24):
        return (
            "Ekran görüldü ancak model yalnızca parçalı metinler okuyabildi. "
            "‘Açık uygulamayı özetle’ gibi daha belirli bir soru sorabilirsin."
        )
    clean = _one_line(joined, 1200)
    return clean or "Ekran görüntüsü analiz edildi ancak güvenilir bir özet üretilemedi."


def validate_screen_image_data(image_data: str) -> str:
    value = str(image_data or "")
    prefix = next((item for item in ALLOWED_PREFIXES if value.startswith(item)), "")
    if not prefix:
        raise ValueError("Ekran görüntüsü yalnızca JPEG veya PNG olabilir.")
    if len(value) > MAX_DATA_URI_CHARS:
        raise ValueError("Ekran görüntüsü güvenli gönderim boyutunu aşıyor.")
    encoded = value[len(prefix):]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Ekran görüntüsü verisi geçersiz.") from exc
    if prefix.startswith("data:image/jpeg") and not raw.startswith(b"\xff\xd8"):
        raise ValueError("JPEG ekran görüntüsü imzası geçersiz.")
    if prefix.startswith("data:image/png") and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG ekran görüntüsü imzası geçersiz.")
    return value


def analyze_screen(
    image_data: str,
    question: str,
    *,
    api_key: str,
    api_url: str,
    model: str,
    timeout: float = 45.0,
) -> str:
    """Bellekteki tek kareyi analiz eder; görüntüyü diske veya loga yazmaz."""
    image_uri = validate_screen_image_data(image_data)
    if not (api_key or "").strip():
        return (
            "Ekran görüntüsünü aldım ancak görsel analiz için GROQ_API_KEY "
            "tanımlı değil. Görüntü kaydedilmeden bellekten bırakıldı."
        )
    user_question = " ".join(str(question or "").split())[:1000]
    prompt = (
        "Bu, kullanıcının açık onayıyla alınmış tek bir ekran görüntüsüdür. "
        "Ekranı Türkçe, kısa ve somut biçimde özetle; ham OCR dökümü, kod bloğu, "
        "tablo veya tek başına madde işaretleri üretme. Önce açık uygulamayı ve "
        "genel durumu söyle, sonra en fazla dört önemli ayrıntı ver. Kullanıcı "
        "özellikle bir yazıyı sorarsa yalnızca ilgili kısa bölümü aktar. Görünür "
        "parola, API anahtarı, erişim anahtarı veya özel kişisel veri varsa değeri "
        "ASLA aynen aktarma; yalnızca hassas bilgi göründüğünü ve gizlenmesi "
        "gerektiğini söyle. Emin olmadığın metni uydurma. YALNIZCA şu JSON "
        "biçiminde yanıt ver: {\"summary\":\"tek cümle\",\"details\":[\"ayrıntı\"],"
        "\"warning\":\"varsa gizlilik uyarısı, yoksa boş\"}."
    )
    if user_question:
        prompt += f" Kullanıcının sorusu: {user_question}"

    session = requests.Session()
    session.trust_env = False
    try:
        response = session.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_uri}},
                    ],
                }],
                "temperature": 0.2,
                "max_tokens": 600,
            },
            timeout=max(10.0, min(float(timeout), 60.0)),
            allow_redirects=False,
        )
        if response.status_code == 401:
            return "Görsel analiz anahtarı geçersiz veya yetkisiz görünüyor."
        if response.status_code == 413:
            return "Ekran görüntüsü görsel analiz servisi için fazla büyük."
        if response.status_code == 429:
            return "Görsel analiz kotası şu anda dolu; daha sonra tekrar deneyebilirsin."
        if response.status_code == 400:
            return (
                "Görsel analiz servisi isteği kabul etmedi. Deneysel özellik "
                "seçili Groq modeli veya hesabıyla uyumlu olmayabilir."
            )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        return format_screen_analysis(content)
    except (
        requests.RequestException, ValueError, TypeError, KeyError, IndexError,
    ) as exc:
        return f"Ekran analizi tamamlanamadı: {safe_error(exc)}"
