from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import json
import re
import time
import sys
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
    # Optional: used by build_calendars.py for (M)/(F)/(C)/(O) prefixes
    kind: str = ""


HEADERS = {
    "User-Agent": "Gorilla-StadiumCalendars/1.0 (+calendar automation)",
    "Accept-Language": "en-GB,en;q=0.9",
}


def _get(url: str) -> str:
    """
    Fetch a URL but NEVER crash the whole build if a site is slow / blocks us.
    Returns "" on failure so downstream parsers return [].
    """
    for attempt in range(2):  # simple retry once
        try:
            r = requests.get(url, headers=HEADERS, timeout=90)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"[WARN] Failed to fetch {url} (attempt {attempt+1}/2): {e}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
                continue
            return ""


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
_FIXTURES_DT_RE = re.compile(
    r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{1,2}:\d{2}\s+[+-]\d{2}:\d{2}$"
)


def _events_from_fixtures(html: str, default_location: str, page_url: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")

    # Extract text in order, line-by-line
    text_lines = [ln.strip() for ln in soup.get_text("\n").split("\n")]
    text_lines = [ln for ln in text_lines if ln]

    # Best-effort competition hints from image alt text
    img_alts = [img.get("alt", "").strip() for img in soup.find_all("img") if img.get("alt")]

    events: list[Event] = []
    i = 0
    while i < len(text_lines):
        ln = text_lines[i]

        if _FIXTURES_DT_RE.match(ln):
            dt_str = ln

            # Find the next "Team - Team" line
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
                    # Add a default duration so Outlook shows a block
                    end_dt = start_dt + timedelta(hours=2, minutes=30)

                    # Competition tag best-effort (helps later filtering)
                    comp = ""
                    window = " ".join(text_lines[max(0, i-2): min(len(text_lines), i+3)]).lower()
                    if "champions league" in window:
                        comp = "Champions League"
                    elif "league cup" in window:
                        comp = "League Cup"
                    elif "fa cup" in window:
                        comp = "FA Cup"

                    if not comp:
                        for alt in img_alts:
                            alt_l = alt.lower()
                            if alt_l in ("champions league", "league cup", "fa cup"):
                                comp = alt
                                break

                    title = game if not comp else f"{game} ({comp})"

                    events.append(
                        Event(
                            title=title,
                            start=start_dt,
                            end=end_dt,
                            location=default_location,
                            url=page_url,
                        )
                    )

            i = j if j > i else i + 1
        else:
            i += 1

    return events


def _fetch_one(source: Source) -> list[Event]:
    html = _get(source.url)
    if not html:
        return []

    if "fixtur.es" in source.url:
        return _events_from_fixtures(html, source.location, source.url)

    # Default: stadium sites via JSON-LD
    return _events_from_jsonld(html, source.location)


def fetch_events(sources: Source | Iterable[Source]) -> dict[Source, list[Event]] | list[Event]:
    """
    Supports BOTH call styles:
      - fetch_events(source) -> list[Event]
      - fetch_events([source1, source2, ...]) -> dict[Source, list[Event]]
    """
    if isinstance(sources, Source):
        return _fetch_one(sources)

    result: dict[Source, list[Event]] = {}
    for s in sources:
        result[s] = _fetch_one(s)
    return result
