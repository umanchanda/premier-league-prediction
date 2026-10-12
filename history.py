"""Build prior-season result caches from the public-domain openfootball dataset.

The model uses the last two seasons as a starting point, so early-season
predictions are not based on a handful of 2026-27 games. Team names are mapped
to the SportMonks names used by the current-season caches.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fixtures import LEAGUES, Fixture, save_cache

HISTORY_DIR = Path(__file__).parent / "data" / "history"
HISTORY_SEASONS = ("2024-25", "2025-26")
OPENFOOTBALL_URL = "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{code}.json"
OPENFOOTBALL_CODES = {"premier-league": "en.1", "la-liga": "es.1"}

# openfootball name -> SportMonks name. Unlisted teams keep their openfootball name.
TEAM_ALIASES = {
    "Arsenal FC": "Arsenal",
    "Aston Villa FC": "Aston Villa",
    "Brentford FC": "Brentford",
    "Brighton & Hove Albion FC": "Brighton & Hove Albion",
    "Burnley FC": "Burnley",
    "Chelsea FC": "Chelsea",
    "Crystal Palace FC": "Crystal Palace",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Ipswich Town FC": "Ipswich Town",
    "Leeds United FC": "Leeds United",
    "Leicester City FC": "Leicester City",
    "Liverpool FC": "Liverpool",
    "Manchester City FC": "Manchester City",
    "Manchester United FC": "Manchester United",
    "Newcastle United FC": "Newcastle United",
    "Nottingham Forest FC": "Nottingham Forest",
    "Southampton FC": "Southampton",
    "Sunderland AFC": "Sunderland",
    "Tottenham Hotspur FC": "Tottenham Hotspur",
    "West Ham United FC": "West Ham United",
    "Wolverhampton Wanderers FC": "Wolverhampton Wanderers",
    "CA Osasuna": "Osasuna",
    "CD Leganés": "Leganés",
    "Club Atlético de Madrid": "Atlético de Madrid",
    "Elche CF": "Elche",
    "Getafe CF": "Getafe",
    "Girona FC": "Girona",
    "Levante UD": "Levante",
    "RC Celta de Vigo": "Celta de Vigo",
    "RCD Espanyol de Barcelona": "Espanyol",
    "RCD Mallorca": "Mallorca",
    "Rayo Vallecano de Madrid": "Rayo Vallecano",
    "Real Betis Balompié": "Real Betis",
    "Real Madrid CF": "Real Madrid",
    "Real Sociedad de Fútbol": "Real Sociedad",
    "Real Valladolid CF": "Real Valladolid",
    "Sevilla FC": "Sevilla",
    "UD Las Palmas": "Las Palmas",
    "Valencia CF": "Valencia",
    "Villarreal CF": "Villarreal",
}


def history_path(league: str, season: str) -> Path:
    return HISTORY_DIR / f"{league}-{season}.json"


def normalize_openfootball(payload: dict, season: str) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for index, match in enumerate(payload.get("matches", [])):
        score = match.get("score")
        full_time = score.get("ft") if isinstance(score, dict) else score
        if not full_time or len(full_time) != 2:
            continue
        round_name = str(match.get("round", "")).split()[-1:]
        fixtures.append(Fixture(
            id=f"openfootball-{season}-{index}",
            home=TEAM_ALIASES.get(match["team1"], match["team1"]),
            away=TEAM_ALIASES.get(match["team2"], match["team2"]),
            kickoff=f"{match['date']} {match.get('time', '12:00')}:00",
            round=int(round_name[0]) if round_name and round_name[0].isdigit() else None,
            home_score=int(full_time[0]),
            away_score=int(full_time[1]),
        ))
    return sorted(fixtures, key=lambda fixture: fixture.kickoff or "")


def load_history(league: str) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for path in sorted(HISTORY_DIR.glob(f"{league}-*.json")):
        fixtures.extend(Fixture(**item) for item in json.loads(path.read_text(encoding="utf-8")))
    return fixtures


def main() -> None:
    parser = argparse.ArgumentParser(description="Download prior-season results for the model.")
    parser.add_argument("--league", choices=LEAGUES, action="append")
    args = parser.parse_args()

    import requests

    for league in args.league or list(LEAGUES):
        for season in HISTORY_SEASONS:
            url = OPENFOOTBALL_URL.format(season=season, code=OPENFOOTBALL_CODES[league])
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            fixtures = normalize_openfootball(response.json(), season)
            save_cache(fixtures, history_path(league, season))
            print(f"Saved {len(fixtures)} {league} {season} results to {history_path(league, season)}")


if __name__ == "__main__":
    main()
