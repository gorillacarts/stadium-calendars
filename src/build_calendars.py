from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from src.ics import build_ics, Event
from src.sources import Source, fetch_events

OUTPUT_DIR = Path("output")

# One calendar per stadium tag, but we can feed it multiple sources.
SOURCES = [
    # ----------------------------
    # Wembley Stadium (concerts/other)
    # ----------------------------
    Source(
        name="Wembley Stadium Events",
        url="https://www.wembleystadium.com/experiences/events",
        location="Wembley Stadium, London",
        stadium_tag="wembley",
        kind="stadium",  # used for prefixing (C)/(O)
    ),

    # ----------------------------
    # Emirates Stadium: Arsenal home fixtures + Emirates events
    # ----------------------------
    Source(
        name="Arsenal Men (Home) – Emirates",
        url="https://fixtur.es/en/team/arsenal/home",
        location="Emirates Stadium, London",
        stadium_tag="emirates",
        kind="mens",  # (M)
    ),
    Source(
        name="Arsenal Women (Home) – Emirates",
        url="https://fixtur.es/en/team/arsenal-women/home",
        location="Emirates Stadium, London",
        stadium_tag="emirates",
        kind="womens",  # (F)
    ),
    Source(
        name="Emirates Stadium Events",
        url="https://www.arsenal.com/emirates-stadium/events",
        location="Emirates Stadium, London",
        stadium_tag="emirates",
        kind="stadium",  # (C)/(O)
    ),

    # ----------------------------
    # London Stadium: West Ham home fixtures + London Stadium events
    # ----------------------------
    Source(
        name="West Ham Men (Home) – London Stadium",
        url="https://fixtur.es/en/team/west-ham-united/home",
        location="London Stadium, London",
        stadium_tag="london-stadium",
        kind="mens",  # (M)
    ),
    Source(
        name="West Ham Women (Home) – London Stadium",
        url="https://fixtur.es/en/team/west-ham-united-women/home",
        location="London Stadium, London",
        stadium_tag="london-stadium",
        kind="womens",  # (F)
    ),
    Source(
        name="London Stadium Events",
        url="https://www.london-stadium.com/events/index.html",
        location="London Stadium, London",
        stadium_tag="london-stadium",
        kind="stadium",  # (C)/(O)
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

def _prefix_for_source(source: Source, title: str) -> str:
    """
    Option 1: single calendar, prefix titles:
      (M) = Men's fixtures
      (F) = Women's fixtures
      (C) = Concerts (best-effort heuristic)
      (O) = Other (best-effort heuristic)
    """
    if getattr(source, "kind", "") == "mens":
        return f"(M) {title}"
    if getattr(source, "kind", "") == "womens":
        return f"(F) {title}"

    # Stadium events: try to guess concert vs other from the title
    t = (title or "").lower()
    concertish = any(k in t for k in ["tour", "live", "concert", "festival", "gig"])
    sportish = any(k in t for k in ["match", "vs", " v ", "fixture", "cup", "league", "nfl", "boxing", "rugby"])
    if concertish and not sportish:
        return f"(C) {title}"
    return f"(O) {title}"

def build() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch everything from all sources
    all_events_by_source = fetch_events(SOURCES)

    # Group into one calendar per stadium
    events_by_stadium: dict[str, list[Event]] = {k: [] for k in CALENDAR_NAMES.keys()}

    for source, events in all_events_by_source.items():
        tag = source.stadium_tag
        if tag not in events_by_stadium:
            continue

        for e in events:
            # Prefix title
            e.title = _prefix_for_source(source, e.title)

            # Ensure location is set (helps in Outlook)
            if not e.location:
                e.location = source.location

            events_by_stadium[tag].append(e)

    # Remove placeholders automatically once we have real events
    for tag, evs in events_by_stadium.items():
        events_by_stadium[tag] = [
            e for e in evs
            if "calendar generated (no events parsed yet)" not in (e.title or "").lower()
        ]

    # Write ICS files
    for tag, cal_name in CALENDAR_NAMES.items():
        outfile = OUTPUT_DIR / OUTFILES[tag]
        events = sorted(events_by_stadium[tag], key=lambda e: e.start)

        ics_text = build_ics(
            calendar_name=cal_name,
            events=events,
            generated_at=datetime.now(timezone.utc),
        )
        outfile.write_text(ics_text, encoding="utf-8")

if __name__ == "__main__":
    build()
