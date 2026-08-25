import os
import base64
import datetime
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from services.google_auth import get_credentials
from services.security import (
    clean_single_line,
    safe_error,
    sanitize_untrusted_text,
    validate_user_text,
)


def get_gmail_service():
    return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)


def get_unread_emails(max_results: int = 5) -> str:
    """Okunmamış mailleri getir."""
    try:
        max_results = max(1, min(int(max_results), 20))
        service = get_gmail_service()
        results = service.users().messages().list(
            userId="me",
            labelIds=["INBOX", "UNREAD"],
            maxResults=max_results
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return "📭 Okunmamış mailin yok."

        lines = [f"📬 **{len(messages)} okunmamış mail:**\n"]
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            sender = sanitize_untrusted_text(headers.get("From", "Bilinmiyor"), 300)
            subject = sanitize_untrusted_text(headers.get("Subject", "Konu yok"), 500)

            # Gönderen adını sadeleştir
            if "<" in sender:
                sender = sender.split("<")[0].strip().strip('"')

            lines.append(f"• **{sender}**\n  {subject}")

        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Gmail hatası: {safe_error(e)}"


def get_today_emails(max_results: int = 10) -> str:
    """Bugün gelen mailleri getir."""
    try:
        max_results = max(1, min(int(max_results), 20))
        service = get_gmail_service()
        today = datetime.date.today().strftime("%Y/%m/%d")

        results = service.users().messages().list(
            userId="me",
            q=f"after:{today}",
            maxResults=max_results
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return "📭 Bugün gelen mail yok."

        lines = [f"📬 **Bugün gelen {len(messages)} mail:**\n"]
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject"]
            ).execute()

            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            sender = sanitize_untrusted_text(headers.get("From", "Bilinmiyor"), 300)
            subject = sanitize_untrusted_text(headers.get("Subject", "Konu yok"), 500)

            if "<" in sender:
                sender = sender.split("<")[0].strip().strip('"')

            lines.append(f"• **{sender}**\n  {subject}")

        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Gmail hatası: {safe_error(e)}"


def send_email(to: str, subject: str, body: str) -> str:
    """Mail gönder."""
    try:
        to = clean_single_line(to, name="Alıcı", max_length=320)
        subject = clean_single_line(subject, name="Mail konusu", max_length=998)
        body = validate_user_text(body, name="Mail içeriği", max_length=100_000)
        service = get_gmail_service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(
            userId="me",
            body={"raw": raw}
        ).execute()

        return f"✅ Mail gönderildi → {to}"
    except Exception as e:
        return f"⚠️ Mail gönderilemedi: {safe_error(e)}"


def search_emails(query: str, max_results: int = 5) -> str:
    """Maillerде arama yap."""
    try:
        query = clean_single_line(query, name="Mail arama sorgusu", max_length=500)
        max_results = max(1, min(int(max_results), 20))
        service = get_gmail_service()
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return f"🔍 '{query}' için mail bulunamadı."

        lines = [f"🔍 **'{query}' için {len(messages)} mail:**\n"]
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            sender = sanitize_untrusted_text(headers.get("From", "Bilinmiyor"), 300)
            subject = sanitize_untrusted_text(headers.get("Subject", "Konu yok"), 500)

            if "<" in sender:
                sender = sender.split("<")[0].strip().strip('"')

            lines.append(f"• **{sender}**\n  {subject}")

        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Gmail hatası: {safe_error(e)}"


def _decode_message_part(part: dict) -> str:
    """İlk uygun düz metin gövdesini MIME ağacından çıkar."""
    mime_type = part.get("mimeType", "")
    data = (part.get("body") or {}).get("data")
    if mime_type == "text/plain" and data:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")
    for child in part.get("parts") or []:
        text = _decode_message_part(child)
        if text:
            return text
    return ""


def read_email(query: str) -> str:
    """Arama ifadesiyle eşleşen en yeni mailin başlık ve düz metin içeriğini getir."""
    try:
        query = clean_single_line(query, name="Mail arama sorgusu", max_length=500)
        service = get_gmail_service()
        results = service.users().messages().list(
            userId="me", q=query, maxResults=1
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return f"🔍 '{query}' için okunacak mail bulunamadı."

        detail = service.users().messages().get(
            userId="me", id=messages[0]["id"], format="full"
        ).execute()
        payload = detail.get("payload") or {}
        headers = {
            header.get("name", "").lower(): header.get("value", "")
            for header in payload.get("headers") or []
        }
        body = sanitize_untrusted_text(
            _decode_message_part(payload).strip() or detail.get("snippet", "").strip(),
            4000,
        )
        return (
            f"Gönderen: {sanitize_untrusted_text(headers.get('from', 'Bilinmiyor'), 300)}\n"
            f"Konu: {sanitize_untrusted_text(headers.get('subject', 'Konu yok'), 500)}\n"
            f"Tarih: {sanitize_untrusted_text(headers.get('date', 'Bilinmiyor'), 200)}\n\n"
            f"{body or 'Mailin okunabilir düz metin içeriği yok.'}"
        )
    except Exception as e:
        return f"⚠️ Gmail hatası: {safe_error(e)}"
