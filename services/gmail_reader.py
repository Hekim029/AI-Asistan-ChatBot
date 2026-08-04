import os
import base64
import datetime
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import utils.config as config

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
TOKEN_PATH = os.path.join(config.MEMORY_DIR, "token.json")
CREDENTIALS_PATH = os.path.join(config.BASE_DIR, "credentials.json")


def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid or not creds.has_scopes(SCOPES):
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def get_unread_emails(max_results: int = 5) -> str:
    """Okunmamış mailleri getir."""
    try:
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
            sender = headers.get("From", "Bilinmiyor")
            subject = headers.get("Subject", "Konu yok")

            # Gönderen adını sadeleştir
            if "<" in sender:
                sender = sender.split("<")[0].strip().strip('"')

            lines.append(f"• **{sender}**\n  {subject}")

        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Gmail hatası: {str(e)}"


def get_today_emails(max_results: int = 10) -> str:
    """Bugün gelen mailleri getir."""
    try:
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
            sender = headers.get("From", "Bilinmiyor")
            subject = headers.get("Subject", "Konu yok")

            if "<" in sender:
                sender = sender.split("<")[0].strip().strip('"')

            lines.append(f"• **{sender}**\n  {subject}")

        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Gmail hatası: {str(e)}"


def send_email(to: str, subject: str, body: str) -> str:
    """Mail gönder."""
    try:
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
        return f"⚠️ Mail gönderilemedi: {str(e)}"


def search_emails(query: str, max_results: int = 5) -> str:
    """Maillerде arama yap."""
    try:
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
            sender = headers.get("From", "Bilinmiyor")
            subject = headers.get("Subject", "Konu yok")

            if "<" in sender:
                sender = sender.split("<")[0].strip().strip('"')

            lines.append(f"• **{sender}**\n  {subject}")

        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Gmail hatası: {str(e)}"


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
        body = _decode_message_part(payload).strip() or detail.get("snippet", "").strip()
        if len(body) > 4000:
            body = body[:3997] + "..."
        return (
            f"Gönderen: {headers.get('from', 'Bilinmiyor')}\n"
            f"Konu: {headers.get('subject', 'Konu yok')}\n"
            f"Tarih: {headers.get('date', 'Bilinmiyor')}\n\n"
            f"{body or 'Mailin okunabilir düz metin içeriği yok.'}"
        )
    except Exception as e:
        return f"⚠️ Gmail hatası: {str(e)}"
