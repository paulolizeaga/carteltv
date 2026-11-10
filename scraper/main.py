#!/usr/bin/env python3
"""CartelTV: ESPN supplies fixtures; FutbolenlaTV supplies Spanish TV listings."""
from __future__ import annotations
import json, re, unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"matches.json"
MADRID=ZoneInfo("Europe/Madrid")
ESPN="https://site.api.espn.com/apis/site/v2/sports"
FOOTBALL={
 "esp.1":"LaLiga","esp.2":"Segunda División","esp.copa_del_rey":"Copa del Rey",
 "esp.super_cup":"Supercopa de España","uefa.champions":"Champions League",
 "uefa.europa":"Europa League","uefa.europa.conf":"Conference League",
}
S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (compatible; CartelTV/1.0)","Accept":"text/html,application/json,*/*"})
CHANNEL_RE=re.compile(r"(?i)\\b(M\\+\\s*(?:LALIGA|Liga de Campeones|Champions|Vamos|Deportes)|Movistar(?:\\s*Plus\\+?|\\s*Liga[^,|]*)?|DAZN(?:\\s*LaLiga)?|La\\s*1|Teledeporte|RTVE\\s*Play|GOL(?:\\s*Play)?|ETB\\s*[124]|ETB1|ETB2|TVG|TV3|Esport\\s*3|À\\s*Punt|Aragón\\s*Deporte|Canal\\s*Sur|CMM\\s*Play|IB3|TPA|Real\\s*Madrid\\s*TV|Barça\\s*(?:TV|One)|LALIGA\\s*TV\\s*HYPERMOTION|Primera\\s*Federación\\s*TV)\\b")

def norm(s):
 s=unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()
 s=re.sub(r"\b(fc|cf|club|de|the)\b"," ",s)
 return re.sub(r"[^a-z0-9]+"," ",s).strip()

def similarity(a,b):
 a,b=norm(a),norm(b)
 if not a or not b:return 0
 if a in b or b in a:return .96
 return SequenceMatcher(None,a,b).ratio()

def get_json(url):
 r=S.get(url,timeout=25);r.raise_for_status();return r.json()

def espn_event(event,label,sport="football"):
 comps=event.get("competitions") or []; comp=comps[0] if comps else {}
 teams=comp.get("competitors") or []
 home=next((x for x in teams if x.get("homeAway")=="home"),None)
 away=next((x for x in teams if x.get("homeAway")=="away"),None)
 if not home and len(teams)>=2:home,away=teams[:2]
 if not home or not away:return None
 def team(x):
  t=x.get("team") or {};return t.get("displayName") or t.get("name") or "—",t.get("logo") or ""
 hn,hl=team(home);an,al=team(away)
 venue=(comp.get("venue") or {}).get("fullName") or ""
 addr=(comp.get("venue") or {}).get("address") or {}
 if isinstance(addr,dict) and addr.get("city"):venue+=", "+addr["city"]
 start=event.get("date") or comp.get("date")
 status=((event.get("status") or {}).get("type") or {}).get("state","pre")
 broadcasts=[]
 for c in comps:
  for b in c.get("broadcasts") or []:
   broadcasts.extend(str(x) for x in (b.get("names") or []) if x)
 return {"id":"espn-"+str(event.get("id","")),"sport":sport,"competition":label,
  "home":hn,"away":an,"home_logo":hl,"away_logo":al,"start":start,
  "date":start[:10] if start else "","venue":venue,"channel":"",
  "status":status,"featured":label in ("Champions League","Copa del Rey","Supercopa de España")}

def fetch_football(day):
 out=[]
 for league,label in FOOTBALL.items():
  try:
   payload=get_json(f"{ESPN}/soccer/{league}/scoreboard?dates={day}&limit=100")
   for e in payload.get("events",[]):
    m=espn_event(e,label)
    if m:out.append(m)
   print(f"[ESPN] {label}: {len(payload.get('events',[]))}")
  except Exception as e:print(f"[ESPN] {label}: {e}")
 return out

def fetch_leafs(day):
 try:events=get_json(f"{ESPN}/hockey/nhl/scoreboard?dates={day}&limit=100").get("events",[])
 except Exception as e:print("[NHL]",e);return []
 out=[]
 for e in events:
  m=espn_event(e,"NHL","nhl")
  if not m or "toronto maple leafs" not in norm(m["home"]+" "+m["away"]):continue
  # For NHL, keep only Canadian national/regional rights explicitly named by ESPN.
  comps=e.get("competitions") or []
  names=[str(n) for c in comps for b in (c.get("broadcasts") or []) for n in (b.get("names") or [])]
  m["channel"]=" / ".join(dict.fromkeys(n for n in names if re.search(r"TSN|Sportsnet",n,re.I)))
  m["featured"]=True;out.append(m)
 return out

def spanish_tv_index():
 """Read individual fixture cards and their Spanish TV channels."""
 url="https://www.futbolenlatv.es/"
 r=S.get(url,timeout=30);r.raise_for_status()
 soup=BeautifulSoup(r.text,"html.parser")
 index=[]
 competitions={"la liga ea sports","laliga hypermotion","segunda division","copa del rey","champions league","europa league","conference league","supercopa de espana","premier league","bundesliga","futbol hoy","futbol en la tv"}
 for node in soup.find_all(["article","li","tr","div"]):
  text=node.get_text(" ",strip=True)
  if len(text)<15 or len(text)>650:continue
  channels=list(dict.fromkeys(x.strip() for x in CHANNEL_RE.findall(text)))
  if not channels:continue
  # Team names are linked individually on this guide. Exclude channel and competition links.
  names=[]
  for link in node.find_all("a"):
   label=link.get_text(" ",strip=True)
   key=norm(label)
   if not key or CHANNEL_RE.search(label) or key in competitions:continue
   if len(key)>38:continue
   if key not in [norm(x) for x in names]:names.append(label)
  # A card with more than two team links is a parent container, not a single fixture.
  if len(names)==2:
   index.append({"names":names,"channels":channels,"text":text})
 # Remove duplicate cards, retaining the shortest textual representation.
 unique={}
 for row in index:
  key=tuple(sorted(norm(x) for x in row["names"]))
  if key not in unique or len(row["text"])<len(unique[key]["text"]):unique[key]=row
 return list(unique.values())

def enrich_spanish_channels(matches):
 football=[m for m in matches if m["sport"]=="football"]
 if not football:return
 try:index=spanish_tv_index()
 except Exception as e:
  print("[TV guide] No se pudo leer futbolenlatv.es:",e);return
 for m in football:
  best=None;best_score=0
  for row in index:
   # Evaluate all candidate team-name pairs from a guide row.
   names=row["names"]
   hs=max((similarity(m["home"],n) for n in names),default=0)
   aw=max((similarity(m["away"],n) for n in names),default=0)
   score=(hs+aw)/2
   if hs>=.68 and aw>=.68 and score>best_score:
    best,best_score=row,score
  if best:
   m["channel"]=" / ".join(best["channels"])
   print(f"[TV guide] {m['home']} - {m['away']}: {m['channel']} ({best_score:.2f})")

def main():
 now=datetime.now(MADRID);day=now.strftime("%Y%m%d")
 matches=fetch_football(day)+fetch_leafs(day)
 enrich_spanish_channels(matches)
 # Keep the Madrid calendar day, not the UTC date supplied by ESPN.
 filtered=[]
 for m in matches:
  try:
   if m.get("start") and datetime.fromisoformat(m["start"].replace("Z","+00:00")).astimezone(MADRID).date()==now.date():filtered.append(m)
  except ValueError:continue
 filtered.sort(key=lambda x:x.get("start") or "")
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),"timezone":"Europe/Madrid","matches":filtered},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(f"[done] {len(filtered)} eventos guardados")

if __name__=="__main__":main()
