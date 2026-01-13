from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import json

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

HEADERS = {
    "User-Agent": "Gorilla-StadiumCalendars/1.0 (+calendar automation)",
    "Accept-Language": "en-GB,en;q=0.9",
}

def _get(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

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

def fetch_events(source: Source) -> list[Event]:
    html = _get(source.url)
    # Prefer JSON-LD. If a site doesn’t expose JSON-LD events, this may return [].
    return _events_from_jsonld(html, source.location)
