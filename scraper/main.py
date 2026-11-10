#!/usr/bin/env python3
"""Build the CartelTV daily schedule from ESPN scoreboards and TVFutbol listings."""
from __future__ import annotations
import json, re, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "matches.json"
MADRID = ZoneInfo("Europe/Madrid")
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
FOOTBALL = {
    "esp.1": "LaLiga",
    "esp.2": "Segunda División",
    "esp.copa_del_rey": "Copa del Rey",
    "esp.super_cup": "Supercopa de España",
    "uefa.champions": "Champions League",
    "uefa.europa": "Europa League",
    "uefa.europa.conf": "Conference League",
}
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "CartelTV/1.0 (+https://github.com/paulolizeaga/carteltv)", "Accept": "application/json,text/html,*/*"})

def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

def get_json(url: str):
    response = SESSION.get(url, timeout=25)
    response.raise_for_status()
    return response.json()

def extract_broadcasts(event: dict) -> list[str]:
    found = []
    for competition in event.get("competitions", []):
        for broadcast in competition.get("broadcasts", []) or []:
            names = broadcast.get("names") or []
            if isinstance(names, list):
                found.extend(str(x) for x in names if x)
            elif names:
                found.append(str(names))
    return list(dict.fromkeys(found))

def espn_event(event: dict, competition_name: str) -> dict | None:
    competitions = event.get("competitions") or []
    comp = competitions[0] if competitions else {}
    competitors = comp.get("competitors") or []
    home = next((x for x in competitors if x.get("homeAway") == "home"), None)
    away = next((x for x in competitors if x.get("homeAway") == "away"), None)
    if not home and len(competitors) >= 2:
        home, away = competitors[0], competitors[1]
    if not home or not away:
        return None
    def team(item):
        t = item.get("team") or {}
        return t.get("displayName") or t.get("name") or "Por confirmar", t.get("logo") or ""
    hn, hl = team(home); an, al = team(away)
    venue = (comp.get("venue") or {}).get("fullName") or ""
    city = (comp.get("venue") or {}).get("address") or {}
    if isinstance(city, dict):
        venue += (", " + city.get("city", "")) if city.get("city") else ""
    start = event.get("date") or comp.get("date")
    status = ((event.get("status") or {}).get("type") or {}).get("state", "pre")
    broadcasts = extract_broadcasts(event)
    return {
        "id": "espn-" + str(event.get("id", "")),
        "sport": "football", "competition": competition_name,
        "home": hn, "away": an, "home_logo": hl, "away_logo": al,
        "start": start, "date": start[:10] if start else "",
        "venue": venue, "channel": " / ".join(broadcasts) if broadcasts else "",
        "status": status, "featured": competition_name in ("Champions League", "Copa del Rey", "Supercopa de España"),
    }

def fetch_football(today: str) -> list[dict]:
    result = []
    for league, label in FOOTBALL.items():
        url = f"{ESPN}/soccer/{league}/scoreboard?dates={today}&limit=100"
        try:
            payload = get_json(url)
            for event in payload.get("events", []):
                item = espn_event(event, label)
                if item:
                    result.append(item)
            print(f"[football] {label}: {len(payload.get('events', []))} eventos")
        except Exception as exc:
            print(f"[football] ERROR {label}: {exc}")
    return result

def fetch_maple_leafs(today: str) -> list[dict]:
    url = f"{ESPN}/hockey/nhl/scoreboard?dates={today}&limit=100"
    try:
        payload = get_json(url)
    except Exception as exc:
        print(f"[NHL] ERROR scoreboard: {exc}")
        return []
    result = []
    for event in payload.get("events", []):
        item = espn_event(event, "NHL")
        if not item:
            continue
        names = norm(item["home"]) + " " + norm(item["away"])
        if "toronto maple leafs" not in names:
            continue
        # NHL broadcasts can identify TSN/Sportsnet; retain the network name when ESPN provides it.
        item["sport"] = "nhl"
        item["featured"] = True
        item["channel"] = next((x for x in extract_broadcasts(event) if re.search(r"\b(TSN|Sportsnet)\b", x, re.I)), "")
        if not item["channel"]:
            item["channel"] = ""
        result.append(item)
    print(f"[NHL] Toronto Maple Leafs: {len(result)}")
    return result

def tvfutbol_channel_hints(matches: list[dict]) -> None:
    """Best-effort enrichment only; never invent a channel if a listing cannot be matched."""
    try:
        response = SESSION.get("https://tvfutbol.es/", timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        # The site is a dynamic editorial listing. Search a short text window around both
        # team names; only accept known Spanish broadcasters in that same window.
        channel_pattern = re.compile(r"(Movistar(?:\s+Plus\+?)?|DAZN(?:\s+LaLiga)?|La\s*1|RTVE\s*Play|GOL\s*Play|M\+\s*Liga|M\+\s*Champions)", re.I)
        for match in matches:
            if match["sport"] != "football" or match["channel"]:
                continue
            h, a = norm(match["home"]), norm(match["away"])
            ih, ia = text.lower().find(h), text.lower().find(a)
            if ih < 0 or ia < 0 or abs(ih - ia) > 1800:
                continue
            left, right = sorted((ih, ia))
            window = text[max(0, left-250):min(len(text), right+450)]
            channels = channel_pattern.findall(window)
            if channels:
                match["channel"] = " / ".join(dict.fromkeys(x.strip() for x in channels))
    except Exception as exc:
        print(f"[TVFutbol] aviso: no se pudo enriquecer la programación: {exc}")

def main():
    now = datetime.now(MADRID)
    day = now.strftime("%Y%m%d")
    matches = fetch_football(day) + fetch_maple_leafs(day)
    tvfutbol_channel_hints(matches)
    # Only events for the current Madrid calendar date are displayed.
    matches = [m for m in matches if m.get("start") and datetime.fromisoformat(m["start"].replace("Z","+00:00")).astimezone(MADRID).date() == now.date()]
    matches.sort(key=lambda x: x.get("start") or "")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "timezone": "Europe/Madrid", "matches": matches}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[done] {len(matches)} eventos guardados en {OUT}")

if __name__ == "__main__":
    main()