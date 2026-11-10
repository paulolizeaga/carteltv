#!/usr/bin/env python3
"""CartelTV: ESPN fixtures enriched with the Spanish XMLTV guide."""
from __future__ import annotations

import gzip
import json
import re
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "matches.json"
MADRID = ZoneInfo("Europe/Madrid")
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
XMLTV_URL = "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml"

FOOTBALL = {
    "esp.1": "LaLiga",
    "esp.2": "Segunda División",
    "esp.copa_del_rey": "Copa del Rey",
    "esp.super_cup": "Supercopa de España",
    "uefa.champions": "Champions League",
    "uefa.europa": "Europa League",
    "uefa.europa.conf": "Conference League",
}

# Only Spanish broadcasters relevant to live football. Lower rank = preferred.
CHANNEL_PRIORITY = [
    "movistar laliga", "m laliga", "dazn laliga", "laliga tv",
    "movistar liga de campeones", "m liga de campeones", "dazn 1",
    "movistar plus", "movistar+", "la 1", "teledeporte", "rtve play",
    "gol play", "gol", "etb1", "etb2", "tv3", "esport3", "tv galicia",
    "tvg", "canal sur", "à punt", "a punt", "ib3",
]
S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; CartelTV/1.0)",
    "Accept": "application/xml,text/xml,application/json,*/*",
})


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    value = re.sub(r"\b(fc|cf|club|de|the)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def similarity(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.98
    # Token overlap helps when the EPG adds prefixes such as "Deportivo" or "Real".
    aa, bb = set(a.split()), set(b.split())
    overlap = len(aa & bb) / max(1, min(len(aa), len(bb)))
    return max(SequenceMatcher(None, a, b).ratio(), overlap * 0.92)


def get_json(url: str):
    response = S.get(url, timeout=25)
    response.raise_for_status()
    return response.json()


def get_scoreboard_events(path, date_filter):
    """Fetch a scoreboard range, falling back to one request per day if needed."""
    url = f"{ESPN}/{path}/scoreboard?dates={date_filter}&limit=1000"
    try:
        return get_json(url).get("events", [])
    except Exception:
        if "-" not in date_filter:
            raise
        first, last = (datetime.strptime(part, "%Y%m%d").date() for part in date_filter.split("-", 1))
        events = []
        day = first
        while day <= last:
            daily_url = f"{ESPN}/{path}/scoreboard?dates={day:%Y%m%d}&limit=100"
            try:
                events.extend(get_json(daily_url).get("events", []))
            except Exception as exc:
                print(f"[ESPN] {path} {day}: {exc}")
            day += timedelta(days=1)
        return events


def espn_event(event, label, sport="football"):
    competitions = event.get("competitions") or []
    comp = competitions[0] if competitions else {}
    teams = comp.get("competitors") or []
    home = next((x for x in teams if x.get("homeAway") == "home"), None)
    away = next((x for x in teams if x.get("homeAway") == "away"), None)
    if not home and len(teams) >= 2:
        home, away = teams[:2]
    if not home or not away:
        return None

    def team(item):
        data = item.get("team") or {}
        return data.get("displayName") or data.get("name") or "—", data.get("logo") or ""

    home_name, home_logo = team(home)
    away_name, away_logo = team(away)
    venue = (comp.get("venue") or {}).get("fullName") or ""
    address = (comp.get("venue") or {}).get("address") or {}
    if isinstance(address, dict) and address.get("city"):
        venue += ", " + address["city"]
    start = event.get("date") or comp.get("date")
    status = ((event.get("status") or {}).get("type") or {}).get("state", "pre")
    return {
        "id": "espn-" + str(event.get("id", "")),
        "sport": sport, "competition": label,
        "home": home_name, "away": away_name,
        "home_logo": home_logo, "away_logo": away_logo,
        "start": start, "date": start[:10] if start else "",
        "venue": venue, "channel": "", "status": status,
        "featured": label in ("Champions League", "Copa del Rey", "Supercopa de España"),
    }


def fetch_football(day):
    output = []
    for league, label in FOOTBALL.items():
        try:
            events = get_scoreboard_events(f"soccer/{league}", day)
            for event in events:
                match = espn_event(event, label)
                if match:
                    output.append(match)
            print(f"[ESPN] {label}: {len(events)}")
        except Exception as exc:
            print(f"[ESPN] {label}: {exc}")
    return output


def fetch_leafs(day):
    try:
        events = get_scoreboard_events("hockey/nhl", day)
    except Exception as exc:
        print("[NHL]", exc)
        return []
    output = []
    for event in events:
        match = espn_event(event, "NHL", "nhl")
        if not match or "toronto maple leafs" not in norm(match["home"] + " " + match["away"]):
            continue
        competitions = event.get("competitions") or []
        names = [
            str(name)
            for comp in competitions
            for broadcast in (comp.get("broadcasts") or [])
            for name in (broadcast.get("names") or [])
        ]
        match["channel"] = " / ".join(dict.fromkeys(
            name for name in names if re.search(r"TSN|Sportsnet", name, re.I)
        ))
        match["featured"] = True
        output.append(match)
    return output


def xmltv_datetime(value):
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y%m%d%H%M%S %z", "%Y%m%d%H%M %z", "%Y%m%d%H%M%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except ValueError:
            pass
    return None


def channel_rank(channel_name):
    key = norm(channel_name)
    for rank, preferred in enumerate(CHANNEL_PRIORITY):
        if norm(preferred) in key or key in norm(preferred):
            return rank
    return None


def read_epg_programmes():
    """Stream the XMLTV feed to disk, then yield only Spanish sports-channel programmes."""
    with tempfile.NamedTemporaryFile(prefix="carteltv-epg-", suffix=".xml") as temp:
        response = S.get(XMLTV_URL, timeout=90, stream=True)
        response.raise_for_status()
        response.raw.decode_content = True
        total = 0
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                temp.write(chunk)
                total += len(chunk)
        temp.flush()
        print(f"[EPG] Descargados {total / 1024 / 1024:.1f} MB")

        channels = {}
        # First pass: channel IDs -> human-readable display names.
        for _, element in ET.iterparse(temp.name, events=("end",)):
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "channel":
                channel_id = element.attrib.get("id", "")
                names = [
                    (child.text or "").strip()
                    for child in element
                    if child.tag.rsplit("}", 1)[-1] == "display-name" and (child.text or "").strip()
                ]
                if channel_id and names:
                    channels[channel_id] = names[0]
                element.clear()
            elif tag == "programme":
                element.clear()

        # Second pass: only programme rows for our Spanish channel shortlist.
        for _, element in ET.iterparse(temp.name, events=("end",)):
            if element.tag.rsplit("}", 1)[-1] != "programme":
                continue
            channel_id = element.attrib.get("channel", "")
            channel_name = channels.get(channel_id, "")
            rank = channel_rank(channel_name)
            if rank is not None:
                values = {}
                for child in element:
                    tag = child.tag.rsplit("}", 1)[-1]
                    if tag in ("title", "sub-title", "desc"):
                        values[tag] = " ".join((child.text or "").split())
                start = xmltv_datetime(element.attrib.get("start"))
                stop = xmltv_datetime(element.attrib.get("stop"))
                title = " | ".join(values.get(key, "") for key in ("title", "sub-title", "desc") if values.get(key))
                if start and title:
                    yield {
                        "channel": channel_name,
                        "rank": rank,
                        "start": start,
                        "stop": stop,
                        "text": title,
                    }
            element.clear()


def enrich_channels_from_epg(matches):
    football = [match for match in matches if match["sport"] == "football"]
    if not football:
        return
    try:
        programmes = list(read_epg_programmes())
    except Exception as exc:
        print(f"[EPG] No se pudo leer guiatv.xml: {exc}")
        return

    assigned = 0
    for match in football:
        try:
            kickoff = datetime.fromisoformat(match["start"].replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        candidates = []
        for programme in programmes:
            # Sports broadcasts commonly start before kick-off; allow a 90-minute lead-in.
            if programme["start"] > kickoff + timedelta(minutes=30):
                continue
            if programme["stop"] and programme["stop"] < kickoff - timedelta(minutes=15):
                continue
            text = programme["text"]
            home_score = similarity(match["home"], text)
            away_score = similarity(match["away"], text)
            if home_score >= 0.78 and away_score >= 0.78:
                candidates.append((programme["rank"], home_score + away_score, programme))
        if candidates:
            # Main Spanish broadcaster first; if tied, choose the strongest team-name match.
            candidates.sort(key=lambda item: (item[0], -item[1]))
            match["channel"] = candidates[0][2]["channel"]
            assigned += 1
            print(f"[EPG] {match['home']} - {match['away']}: {match['channel']}")
    print(f"[EPG] Canal principal asignado a {assigned}/{len(football)} partidos")


def main():
    now = datetime.now(MADRID)
    first_day = now.date() - timedelta(days=7)
    last_day = now.date() + timedelta(days=14)
    day_range = f"{first_day:%Y%m%d}-{last_day:%Y%m%d}"
    matches = fetch_football(day_range) + fetch_leafs(day_range)
    enrich_channels_from_epg(matches)

    filtered = []
    for match in matches:
        try:
            if match.get("start"):
                local_date = datetime.fromisoformat(match["start"].replace("Z", "+00:00")).astimezone(MADRID).date()
                if first_day <= local_date <= last_day:
                    match["date"] = local_date.isoformat()
                    filtered.append(match)
        except ValueError:
            continue
    filtered.sort(key=lambda item: item.get("start") or "")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "Europe/Madrid",
        "matches": filtered,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[done] {len(filtered)} eventos guardados")


if __name__ == "__main__":
    main()
