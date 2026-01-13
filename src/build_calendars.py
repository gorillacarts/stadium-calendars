from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone

from src.ics import build_ics, Event
from src.sources import Source, fetch_events

OUTPUT_DIR = Path("output")

SOURCES = [
    Source(
        name="Wembley Stadium Events",
        url="https://www.wembleystadium.com/experiences/events",
        location="Wembley Stadium, London",
        stadium_tag="wembley",
    ),
    Source(
        name="Emirates Stadium Events",
        url="https://www.arsenal.com/emirates-stadium/events",
        location="Emirates Stadium, London",
        stadium_tag="emirates",
    ),
    Source(
        name="London Stadium Events",
        url="https://www.london-stadium.com/events/index.html",
        location="London Stadium, London",
        stadium_tag="london-stadium",
    ),
]

CALENDAR_NAMES = {
    "wembley": "Wembley Stadium – All Events (Gorilla)",
    "emirates": "Emirates Stadium – All Events (Gorilla)",
    "london-stadium": "London Stadium – All Events (Gorilla)",
}

OUTFILES = {
    "wembley": "wembley.ics",
    "emirates": "emirates.ics",
    "london-stadium": "london-stadium.ics",
}


def _empty_placeholder_event(stadium_name: str) -> list[Event]:
    # Ensures the .ics file is never empty (helps troubleshooting and prevents 404s).
    now = datetime.now(timezone.utc)
    return [
        Event(
            title=f"{stadium_name}: calendar generated (no events parsed yet)",
            start=now,
            end=None,
            location=stadium_name,
            url="",
        )
    ]


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Proof of life: ensures output is never empty and confirms the script ran.
    (OUTPUT_DIR / "healthcheck.txt").write_text("calendar build ran\n", encoding="utf-8")
    print("[OK] wrote output/healthcheck.txt")

    buckets: dict[str, list[Event]] = {"wembley": [], "emirates": [], "london-stadium": []}

    for src in SOURCES:
        try:
            events = fetch_events(src)
        except Exception as e:
            print(f"[WARN] Failed to fetch {src.name}: {e}")
            events = []
        buckets[src.stadium_tag].extend(events)
        print(f"[INFO] {src.name}: {len(events)} events")

    # Always write files, even if 0 events parsed.
    for tag in buckets:
        events = buckets[tag]
        if not events:
            events = _empty_placeholder_event(CALENDAR_NAMES[tag])

        ics_text = build_ics(CALENDAR_NAMES[tag], events)
        out = OUTPUT_DIR / OUTFILES[tag]
        out.write_text(ics_text, encoding="utf-8")
        print(f"[OK] Wrote {out} ({len(events)} events)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
