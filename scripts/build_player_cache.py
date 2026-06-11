#!/usr/bin/env python3
"""
Build player_cache.json for the Arsenal Rebuild frontend.

Fetches and stores:
  - Arsenal squad rosters for seasons 2009-2015
  - All LEAGUE_CLUBS squad rosters for seasons 2009-2015
  - Market value histories for all collected players + rumoured targets

Usage:
    python scripts/build_player_cache.py [--api-url http://localhost:8001]

Run against the local transfermarkt-api server. Commit the resulting
frontend/player_cache.json so the frontend works without a live API.
Supports resuming — already-fetched entries are skipped.
"""

import json
import time
import argparse
from datetime import datetime
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────

ARSENAL_ID = "11"
SEASONS    = list(range(2009, 2016))
OUT_FILE   = Path(__file__).parent.parent / "frontend" / "player_cache.json"
DELAY      = 1.2   # seconds between requests
SAVE_EVERY = 20    # checkpoint every N ops

LEAGUE_CLUBS = {
    # Premier League
    "281":"Man City",    "31":"Liverpool",    "985":"Man Utd",
    "631":"Chelsea",    "148":"Tottenham",    "29":"Everton",
    "405":"Aston Villa","379":"West Ham",     "762":"Newcastle",
    "1237":"Leicester", "289":"Sunderland",   "931":"Fulham",
    # La Liga
    "418":"Real Madrid","131":"Barcelona",    "13":"Atlético",
    "368":"Sevilla",    "1049":"Valencia",    "1050":"Villarreal",
    "621":"Athletic",   "2197":"Real Sociedad",
    # Bundesliga
    "27":"Bayern",      "16":"Dortmund",      "15":"Leverkusen",
    "33":"Schalke",     "18":"M'gladbach",    "86":"Werder",
    "41":"Hamburg",     "26":"Stuttgart",
    # Serie A
    "506":"Juventus",   "46":"Inter",         "5":"AC Milan",
    "6195":"Napoli",    "12":"Roma",          "398":"Lazio",
    "430":"Fiorentina",
    # Ligue 1
    "583":"PSG",        "1041":"Lyon",        "244":"Marseille",
    "162":"Monaco",     "1082":"Lille",       "417":"Nice",
    "3911":"Bordeaux",
}

# All plausible Arsenal targets 2009-2015, across positions
TARGET_NAMES = [
    # ── Goalkeepers ──────────────────────────────────────────────────────
    "Heurelho Gomes", "Shay Given", "Manuel Neuer", "Joe Hart",
    "Pepe Reina", "Julio Cesar", "David de Gea", "Bernd Leno",
    "Kasper Schmeichel", "Thibaut Courtois", "Mark Schwarzer",
    "Michel Vorm", "Brad Guzan", "Stephane Ruffier", "Victor Valdes",
    "Wojciech Szczesny", "Lukasz Fabianski", "David Ospina",

    # ── Defenders ────────────────────────────────────────────────────────
    "Joleon Lescott", "Gary Cahill", "Branislav Ivanovic",
    "Jan Vertonghen", "Mats Hummels", "Thiago Silva", "Marquinhos",
    "Kostas Manolas", "Shkodran Mustafi", "David Luiz",
    "Raphael Varane", "Diego Godin", "Toby Alderweireld",
    "Nicolas Otamendi", "Neven Subotic", "Sokratis Papastathopoulos",
    "Dejan Lovren", "Mamadou Sakho", "Martin Skrtel", "Daniel Agger",
    "Leighton Baines", "Luke Shaw", "Nathaniel Clyne", "Jonny Evans",
    "Christopher Samba", "Sylvain Distin", "Ryan Shawcross",
    "Phil Jagielka", "Ashley Williams", "Bacary Sagna",
    "Patrice Evra", "Gael Clichy", "Aleksandar Kolarov",
    "Thomas Vermaelen", "Per Mertesacker", "Laurent Koscielny",
    "Mathieu Debuchy", "Calum Chambers",

    # ── Midfielders ──────────────────────────────────────────────────────
    "Gareth Barry", "Luka Modric", "Franck Ribery", "Yoann Gourcuff",
    "Yann M'Vila", "Wesley Sneijder", "Juan Mata", "Ivan Perisic",
    "Cesc Fabregas", "Mesut Ozil", "Marouane Fellaini", "Willian",
    "Morgan Schneiderlin", "Kevin De Bruyne", "Thiago Alcantara",
    "Ilkay Gundogan", "Granit Xhaka", "N'Golo Kante", "David Silva",
    "Isco", "Marco Verratti", "Julian Draxler", "Clint Dempsey",
    "Toni Kroos", "Miralem Pjanic", "Paul Pogba", "Arturo Vidal",
    "Axel Witsel", "Gylfi Sigurdsson", "Christian Eriksen",
    "Philippe Coutinho", "Henrikh Mkhitaryan", "Eden Hazard",
    "Oscar", "Dimitri Payet", "James Milner", "Jordan Henderson",
    "Santi Cazorla", "Mikel Arteta", "Jack Wilshere", "Aaron Ramsey",
    "Tomas Rosicky", "Abou Diaby", "Samir Nasri",
    "Andrey Arshavin", "Alex Song",

    # ── Attackers ────────────────────────────────────────────────────────
    "Karim Benzema", "David Villa", "Samuel Eto'o", "Dimitar Berbatov",
    "Robinho", "Fernando Torres", "Edin Dzeko", "Falcao",
    "Diego Forlan", "Gonzalo Higuain", "Luis Suarez", "Wayne Rooney",
    "Didier Drogba", "Mario Balotelli", "Robert Lewandowski",
    "Edinson Cavani", "Diego Costa", "Harry Kane", "Jamie Vardy",
    "Riyad Mahrez", "Alexandre Lacazette", "Demba Ba",
    "Loic Remy", "Christian Benteke", "Romelu Lukaku",
    "Raheem Sterling", "Sadio Mane", "Marcus Rashford",
    "Antoine Griezmann", "Alvaro Morata", "Memphis Depay",
    "Jackson Martinez", "Robin van Persie", "Theo Walcott",
    "Olivier Giroud", "Lukas Podolski", "Gervinho",
    "Alexis Sanchez", "Danny Welbeck",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_json(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    WARN: {e}")
        return None


def save(cache):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(
            {"version": "1.0", "generated": datetime.now().isoformat(), **cache},
            ensure_ascii=False, separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def load_existing():
    if OUT_FILE.exists():
        try:
            d = json.loads(OUT_FILE.read_text(encoding="utf-8"))
            sq = len(d.get("squads", {}))
            hi = len(d.get("history", {}))
            print(f"Resuming from existing cache ({sq} squads, {hi} histories)")
            return d
        except Exception:
            pass
    return {"squads": {}, "history": {}}

# ── Phases ────────────────────────────────────────────────────────────────────

def fetch_squad(api_url, club_id, yr, squads, all_ids):
    key = f"{club_id}-{yr}"
    if key in squads:
        for p in squads[key]:
            all_ids.add(str(p["id"]))
        return True  # already cached
    d = get_json(f"{api_url}/clubs/{club_id}/players", params={"season_id": yr})
    if d:
        players = [
            {"id": p["id"], "name": p.get("name", ""), "position": p.get("position", ""),
             "age": p.get("age"), "market_value": p.get("market_value")}
            for p in d.get("players", []) if p.get("id") and p.get("name")
        ]
        squads[key] = players
        for p in players:
            all_ids.add(str(p["id"]))
        return True
    squads[key] = []
    return False


def main(api_url):
    cache   = load_existing()
    squads  = cache.setdefault("squads",  {})
    history = cache.setdefault("history", {})
    all_ids = set(history.keys())
    ops     = 0

    def tick():
        nonlocal ops
        time.sleep(DELAY)
        ops += 1
        if ops % SAVE_EVERY == 0:
            save(cache)
            print("    [checkpoint saved]")

    # ── Phase 1: Arsenal squads ────────────────────────────────────────────
    print("\n=== Phase 1: Arsenal squads (2009-2015) ===")
    for yr in SEASONS:
        key = f"{ARSENAL_ID}-{yr}"
        if key in squads:
            print(f"  {yr}: cached ({len(squads[key])} players)")
            for p in squads[key]: all_ids.add(str(p["id"]))
            continue
        print(f"  Fetching Arsenal {yr}/{yr-1999}…")
        fetch_squad(api_url, ARSENAL_ID, yr, squads, all_ids)
        print(f"    {len(squads.get(key,[]))} players")
        tick()
    save(cache)

    # ── Phase 2: All browse-club squads ───────────────────────────────────
    print(f"\n=== Phase 2: Browse club squads ({len(LEAGUE_CLUBS)} clubs × {len(SEASONS)} seasons) ===")
    total = len(LEAGUE_CLUBS) * len(SEASONS)
    done  = 0
    for club_id, club_name in LEAGUE_CLUBS.items():
        for yr in SEASONS:
            key = f"{club_id}-{yr}"
            done += 1
            if key in squads:
                for p in squads[key]: all_ids.add(str(p["id"]))
                continue
            print(f"  [{done}/{total}] {club_name} {yr}…")
            fetch_squad(api_url, club_id, yr, squads, all_ids)
            print(f"    {len(squads.get(key,[]))} players")
            tick()
    save(cache)
    print(f"Squads done. {len(all_ids)} unique player IDs collected.")

    # ── Phase 3: Search rumoured targets ──────────────────────────────────
    print(f"\n=== Phase 3: Searching {len(TARGET_NAMES)} rumoured targets ===")
    for name in TARGET_NAMES:
        encoded = requests.utils.quote(name, safe="")
        d = get_json(f"{api_url}/players/search/{encoded}")
        if d:
            results = d.get("results", [])
            if results:
                pid = str(results[0]["id"])
                all_ids.add(pid)
                print(f"  {name} → {results[0].get('name')} (id:{pid})")
            else:
                print(f"  {name} → no results")
        else:
            print(f"  {name} → request failed")
        tick()
    save(cache)

    # ── Phase 4: Market value histories ───────────────────────────────────
    to_fetch = sorted(all_ids - set(history.keys()))
    print(f"\n=== Phase 4: Market value histories ({len(to_fetch)} new, {len(history)} cached) ===")
    for i, pid in enumerate(to_fetch):
        print(f"  [{i+1}/{len(to_fetch)}] player {pid}…")
        d = get_json(f"{api_url}/players/{pid}/market_value")
        if d:
            history[pid] = [
                {"date": e.get("date"), "value": e.get("marketValue"), "club": e.get("clubName")}
                for e in d.get("marketValueHistory", []) if e.get("date")
            ]
            print(f"    {len(history[pid])} entries")
        else:
            history[pid] = []
        tick()

    save(cache)
    print(f"\n✓ Done!  →  {OUT_FILE}")
    print(f"  Squads    : {len(squads)}")
    print(f"  Histories : {len(history)}")
    print(f"  Players   : {len(all_ids)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Arsenal Rebuild player cache")
    parser.add_argument("--api-url", default="http://localhost:8001")
    args = parser.parse_args()
    main(args.api_url)
