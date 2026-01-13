from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def _dt_to_ics(dt: datetime) -> str:
    # Use UTC to avoid Outlook TZ quirks; Outlook renders in local time.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y%m%dT%H%M%SZ")

@dataclass(frozen=True)
class Event:
    title: str
    start: datetime
    end: datetime | None
    location: str
    url: str

    @property
    def uid(self) -> str:
        base = f"{self.title}|{self.start.isoformat()}|{self.location}|{self.url}"
        h = hashlib.sha1(base.encode("utf-8")).hexdigest()
        return f"{h}@gorilla-stadium-calendars"

def build_ics(calendar_name: str, events: list[Event]) -> str:
    now = datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Gorilla Carts & Kiosks//Stadium Calendars//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(calendar_name)}",
        "X-WR-TIMEZONE:Europe/London",
    ]

    for e in sorted(events, key=lambda x: x.start):
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{e.uid}",
            f"DTSTAMP:{_dt_to_ics(now)}",
            f"DTSTART:{_dt_to_ics(e.start)}",
        ])
        if e.end:
            lines.append(f"DTEND:{_dt_to_ics(e.end)}")
        lines.extend([
            f"SUMMARY:{_ics_escape(e.title)}",
            f"LOCATION:{_ics_escape(e.location)}",
        ])
        if e.url:
            lines.append(f"URL:{_ics_escape(e.url)}")
            lines.append(f"DESCRIPTION:{_ics_escape(e.url)}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
