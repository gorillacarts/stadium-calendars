from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import re
from datetime import timedelta

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

from src.ics import Event

@dataclass(frozen=True)
class Source:
    name: str
    url: str
    location: str
    stadium_tag: str
    # Optional: lets build_calendars prefix titles later (M/F/C/O).
    # Safe default means your existing code won't break if you don't use it yet.
    kind: str = ""

HEADERS = {
    "User-Agent": "Gorilla-StadiumCalendars/1.0 (+calendar automation)",
    "Accept-Language": "en-GB,en;q=0.9",
}

def _get(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.text

# -----------------------------
# JSON-LD event extraction
# -----------------------------
def _events_from_jsonld(html: str, default_location: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    events: list[Event] = []

    for s in scripts:
        raw = s.get_text(strip=True)
        if not raw:
            continue
        try:
            data: Any = json.loads(raw)
        except Exception:
            continue

        # JSON-LD can be dict/list and can include @graph
        candidates: list[Any] = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            if isinstance(data.get("@graph"), list):
                candidates = data["@graph"]
            else:
                candidates = [data]

        for obj in candidates:
            if not isinstance(obj, dict):
                continue

            t = obj.get("@type")
            if isinstance(t, list):
                is_event = "Event" in t
            else:
                is_event = (t == "Event")

            if not is_event:
                continue

            name = str(obj.get("name") or "Event").strip()
            start = obj.get("startDate")
            end = obj.get("endDate")
            url = str(obj.get("url") or "").strip()

            # location may be nested
            loc = default_location
            loc_obj = obj.get("location")
            if isinstance(loc_obj, dict):
                loc = str(loc_obj.get("name") or loc).strip()

            try:
                start_dt = dtparser.parse(start) if start else None
            except Exception:
                start_dt = None
            if not start_dt:
                continue

            end_dt = None
            if end:
                try:
                    end_dt = dtparser.parse(end)
                except Exception:
                    end_dt = None

            events.append(
                Event(
                    title=name,
                    start=start_dt,
                    end=end_dt,
                    location=loc,
                    url=url,
                )
            )

    return events

# -----------------------------
# Fixtur.es fixture extraction
# -----------------------------
_FIXTURES_DT_RE = re.compile(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{1,2}:\d{2}\s+[+-]\d{2}:\d{2}$")

def _events_from_fixtures(html: str, default_location: str, page_url: str) -> list[Event]:
    """
    Parses fixtur.es team pages (and /home pages). It’s a simple table-like layout.
    We extract:
      - datetime (e.g. "7 Sep 2025 12:00 +01:00")
      - game line (e.g. "Chelsea - Fulham")
      - competition (best-effort from image alt text such as "League Cup", "Champions League")
    """
    soup = BeautifulSoup(html, "html.parser")

    # Fixtur.es pages render as a repeating block; easiest robust method:
    # iterate through text lines and also capture nearby image alt text.
    text_lines = [ln.strip() for ln in soup.get_text("\n").split("\n")]
    text_lines = [ln for ln in text_lines if ln]

    # Collect competition hints from image alts in document order
    # (they appear right next to some dates in the page).
    img_alts = [img.get("alt", "").strip() for img in soup.find_all("img") if img.get("alt")]
    # We'll use this as a weak hint; the line-based parser below is the main driver.

    events: list[Event] = []
    i = 0
    while i < len(text_lines):
        ln = text_lines[i]

        # Find a datetime line like "11 Jan 2026 12:00 +00:00"
        if _FIXTURES_DT_RE.match(ln):
            dt_str = ln
            # Next non-empty line that contains " - " is usually the game
            game = ""
            j = i + 1
            while j < len(text_lines):
                if " - " in text_lines[j]:
                    game = text_lines[j]
                    break
                j += 1

            if game:
                try:
                    start_dt = dtparser.parse(dt_str)
                except Exception:
                    start_dt = None

                if start_dt:
                    # Best-effort competition detection:
                    # If the page line itself includes a known competition keyword, use it.
                    comp = ""
                    # Sometimes alt text ends up as plain words in the text; check nearby window.
                    window = " ".join(text_lines[max(0, i-2): min(len(text_lines), i+3)]).lower()
                    if "champions league" in window:
                        comp = "Champions League"
                    elif "league cup" in window:
                        comp = "League Cup"
                    elif "fa cup" in window:
                        comp = "FA Cup"

                    # If still empty, fall back to any img alt that looks like a competition
                    if not comp:
                        for alt in img_alts:
                            if alt.lower() in ("league cup", "champions league", "fa cup"):
                                comp = alt
                                break

                    title = game
                    if comp:
                        title = f"{game} ({comp})"

                    events.append(
                        Event(
                            title=title,
                            start=start_dt,
                            end=start_dt + timedelta(hours=2, minutes=30),
                            location=default_location,
                            url=page_url,
                        )
                    )
            i = j if j > i else i + 1
        else:
            i += 1

    return events

def fetch_events(source: Source) -> list[Event]:
    html = _get(source.url)

    # Fixtur.es fixtures
    if "fixtur.es" in source.url:
        return _events_from_fixtures(html, source.location, source.url)

    # Default: stadium sites via JSON-LD
    return _events_from_jsonld(html, source.location)
