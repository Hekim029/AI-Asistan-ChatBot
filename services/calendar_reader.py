import datetime
from googleapiclient.discovery import build
from services.google_auth import get_credentials
from services.security import clean_single_line, sanitize_untrusted_text, validate_user_text

def get_service():
    return build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)


def _validated_datetime(value: str, *, field_name: str) -> tuple[str, datetime.datetime]:
    text = clean_single_line(value, name=field_name, max_length=100)
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field_name} ISO-8601 biçiminde geçerli bir tarih-saat olmalı."
        ) from exc
    return text, parsed


def create_calendar_event(
    title: str,
    start_at: str,
    end_at: str,
    description: str = "",
) -> str:
    title = clean_single_line(title, name="Etkinlik başlığı", max_length=500)
    description = validate_user_text(
        description or "Açıklama yok", name="Etkinlik açıklaması", max_length=10_000
    ) if description else ""
    start_at, start_dt = _validated_datetime(start_at, field_name="Başlangıç")
    end_at, end_dt = _validated_datetime(end_at, field_name="Bitiş")
    try:
        valid_order = end_dt > start_dt
    except TypeError as exc:
        raise ValueError(
            "Başlangıç ve bitiş saatleri aynı saat dilimi biçimini kullanmalı."
        ) from exc
    if not valid_order:
        raise ValueError("Etkinlik bitişi başlangıçtan sonra olmalı.")
    service = get_service()
    event = service.events().insert(
        calendarId="primary",
        body={
            "summary": title,
            "description": description,
            "start": {"dateTime": start_at, "timeZone": "Europe/Istanbul"},
            "end": {"dateTime": end_at, "timeZone": "Europe/Istanbul"},
        },
    ).execute()
    summary = sanitize_untrusted_text(event.get("summary", title), 500)
    return f"Takvim etkinliği oluşturuldu: {summary}"


def _find_primary_event(query: str) -> dict | None:
    query = clean_single_line(query, name="Etkinlik araması", max_length=500)
    service = get_service()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    events = service.events().list(
        calendarId="primary",
        q=query,
        timeMin=now,
        singleEvents=True,
        orderBy="startTime",
        maxResults=10,
    ).execute().get("items", [])
    return events[0] if events else None


def update_calendar_event(
    query: str,
    title: str = "",
    start_at: str = "",
    end_at: str = "",
    description: str = "",
) -> str:
    event = _find_primary_event(query)
    if not event:
        return f"'{query}' ile eşleşen yaklaşan etkinlik bulunamadı."
    if title:
        event["summary"] = clean_single_line(title, name="Etkinlik başlığı", max_length=500)
    if description:
        event["description"] = validate_user_text(
            description, name="Etkinlik açıklaması", max_length=10_000
        )
    if start_at:
        start_at, _ = _validated_datetime(start_at, field_name="Başlangıç")
        event["start"] = {"dateTime": start_at, "timeZone": "Europe/Istanbul"}
    if end_at:
        end_at, _ = _validated_datetime(end_at, field_name="Bitiş")
        event["end"] = {"dateTime": end_at, "timeZone": "Europe/Istanbul"}
    get_service().events().update(
        calendarId="primary",
        eventId=event["id"],
        body=event,
    ).execute()
    summary = sanitize_untrusted_text(event.get("summary", query), 500)
    return f"Takvim etkinliği güncellendi: {summary}"


def delete_calendar_event(query: str) -> str:
    event = _find_primary_event(query)
    if not event:
        return f"'{query}' ile eşleşen yaklaşan etkinlik bulunamadı."
    get_service().events().delete(
        calendarId="primary",
        eventId=event["id"],
    ).execute()
    summary = sanitize_untrusted_text(event.get("summary", query), 500)
    return f"Takvim etkinliği silindi: {summary}"

def get_upcoming_events(days: int = 365) -> list:
    """Önümüzdeki X gün içindeki etkinlikleri tüm takvimlerden döndür."""
    try:
        days = max(1, min(int(days), 365))
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
                    title = sanitize_untrusted_text(event.get("summary", "İsimsiz etkinlik"), 500)
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
                        "description": sanitize_untrusted_text(event.get("description", ""), 4000),
                    })
            except (KeyError, TypeError, ValueError, OSError):
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
