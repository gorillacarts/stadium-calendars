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

def _empty_placeholder_event(stadium_name

