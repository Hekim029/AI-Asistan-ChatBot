import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_PATH = "memory/token.json"
CREDENTIALS_PATH = "credentials.json"

def get_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)

def get_upcoming_events(days: int = 365) -> list:
    """Önümüzdeki X gün içindeki etkinlikleri tüm takvimlerden döndür."""
    try:
        service = get_service()
        now = datetime.datetime.utcnow()
        end = now + datetime.timedelta(days=days)

        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])

        result = []
        seen = set()

        for cal in calendars:
            cal_id = cal["id"]
            try:
                events_result = service.events().list(
                    calendarId=cal_id,
                    timeMin=now.isoformat() + "Z",
                    timeMax=end.isoformat() + "Z",
                    maxResults=50,
                    singleEvents=True,
                    orderBy="startTime"
                ).execute()

                for event in events_result.get("items", []):
                    title = event.get("summary", "İsimsiz etkinlik")
                    start_str = event["start"].get("dateTime", event["start"].get("date"))

                    if "T" in start_str:
                        start_dt = datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        start_dt = start_dt.replace(tzinfo=None)
                    else:
                        start_dt = datetime.datetime.strptime(start_str, "%Y-%m-%d")

                    key = (title, str(start_dt.date()))
                    if key in seen:
                        continue
                    seen.add(key)

                    days_left = (start_dt.date() - datetime.date.today()).days
                    result.append({
                        "title": title,
                        "start": start_dt,
                        "days_left": days_left,
                        "description": event.get("description", ""),
                    })
            except:
                continue

        result.sort(key=lambda x: x["days_left"])
        return result

    except Exception as e:
        return []

def format_events_response(events: list) -> str:
    """Etkinlikleri Heko'nun söyleyeceği formata çevir."""
    if not events:
        return "Önümüzdeki 30 gün içinde takviminde etkinlik bulamadım."

    today_events = [e for e in events if e["days_left"] == 0]
    tomorrow_events = [e for e in events if e["days_left"] == 1]
    urgent_events = [e for e in events if 2 <= e["days_left"] <= 7]
    upcoming_events = [e for e in events if e["days_left"] > 7]

    lines = []

    if today_events:
        lines.append("🔴 BUGÜN:")
        for e in today_events:
            lines.append(f"  • {e['title']}")

    if tomorrow_events:
        lines.append("🟠 YARIN:")
        for e in tomorrow_events:
            lines.append(f"  • {e['title']}")

    if urgent_events:
        lines.append("🟡 YAKLAŞIYOR:")
        for e in urgent_events:
            lines.append(f"  • {e['title']} — {e['days_left']} gün kaldı")

    if upcoming_events:
        lines.append("📅 YAKINDA:")
        for e in upcoming_events[:5]:
            lines.append(f"  • {e['title']} — {e['days_left']} gün kaldı")

    return "\n".join(lines)

def check_urgent_events() -> str | None:
    """Bugün veya yarın etkinlik varsa uyarı mesajı döndür, yoksa None."""
    events = get_upcoming_events(days=7)
    urgent = [e for e in events if e["days_left"] <= 1]

    if not urgent:
        soon = [e for e in events if 2 <= e["days_left"] <= 3]
        if soon:
            msgs = [f"'{e['title']}' etkinliğine {e['days_left']} gün kaldı!" for e in soon]
            return "⚠️ " + " | ".join(msgs)
        return None

    msgs = []
    for e in urgent:
        if e["days_left"] == 0:
            msgs.append(f"'{e['title']}' BUGÜN!")
        else:
            msgs.append(f"'{e['title']}' YARIN!")

    return "🔔 " + " | ".join(msgs)