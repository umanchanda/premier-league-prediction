"""Premier League fixture ingestion through SportMonks."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEASON = "2026/2027"
CACHE_PATH = Path(__file__).parent / "data" / "fixtures-2026-27.json"
LA_LIGA_CACHE_PATH = Path(__file__).parent / "data" / "la-liga-fixtures-2026-27.json"

SPORTMONKS_URL = "https://api.sportmonks.com/v3/football/fixtures"


@dataclass(frozen=True)
class Fixture:
    id: str
    home: str
    away: str
    kickoff: str | None
    round: int | None
    home_score: int | None = None
    away_score: int | None = None

    @property
    def played(self) -> bool:
        return self.home_score is not None and self.away_score is not None


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    return None


def _score(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def normalize_sportmonks_fixtures(payload: dict[str, Any]) -> list[Fixture]:
    """Convert a SportMonks fixture response into the app's fixture model."""
    fixtures: list[Fixture] = []
    for item in payload.get("data", []):
        if not isinstance(item, dict):
            continue
        participants = item.get("participants", [])
        home = next((team.get("name") for team in participants
                     if isinstance(team, dict) and team.get("meta", {}).get("location") == "home"), None)
        away = next((team.get("name") for team in participants
                     if isinstance(team, dict) and team.get("meta", {}).get("location") == "away"), None)
        if not isinstance(home, str) or not isinstance(away, str):
            continue

        scores = item.get("scores", [])
        current_scores: dict[str, int | None] = {}
        participant_locations = {
            team.get("id"): team.get("meta", {}).get("location")
            for team in participants if isinstance(team, dict)
        }
        for score in scores:
            if not isinstance(score, dict) or score.get("description") not in (None, "CURRENT"):
                continue
            location = participant_locations.get(score.get("participant_id"))
            if location:
                score_data = score.get("score")
                goals = score_data.get("goals") if isinstance(score_data, dict) else score.get("goals")
                current_scores[location] = _score(goals)

        round_data = item.get("round")
        fixtures.append(Fixture(
            id=str(item.get("id")),
            home=home,
            away=away,
            kickoff=_to_iso(item.get("starting_at")),
            round=_score(round_data.get("name")) if isinstance(round_data, dict) else None,
            home_score=current_scores.get("home"),
            away_score=current_scores.get("away"),
        ))
    return sorted(fixtures, key=lambda fixture: fixture.kickoff or "")


class SportMonksFixtureSource:
    def __init__(
        self,
        api_key: str | None = None,
        season_id: int = 28083,
        league_id: int = 8,
    ) -> None:
        self.api_key = api_key or os.getenv("MONKS_KEY") or os.getenv("SPORTMONKS_KEY")
        self.season_id = season_id
        self.league_id = league_id

    def fetch(self) -> list[Fixture]:
        if not self.api_key:
            raise RuntimeError("Set MONKS_KEY to a SportMonks API token before syncing fixtures.")
        try:
            import requests
        except ModuleNotFoundError as exc:
            raise RuntimeError("Requests is not installed. Run: python -m pip install -r requirements.txt") from exc

        fixtures: list[Fixture] = []
        page = 1
        while True:
            response = requests.get(
                SPORTMONKS_URL,
                params={
                    "api_token": self.api_key,
                    "filters": f"fixtureSeasons:{self.season_id};fixtureLeagues:{self.league_id}",
                    "include": "participants;scores;round",
                    "page": page,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            fixtures.extend(normalize_sportmonks_fixtures(payload))
            pagination = payload.get("pagination", {})
            if not pagination.get("has_more", pagination.get("has_more_page", False)):
                break
            page += 1

        return sorted(fixtures, key=lambda fixture: fixture.kickoff or "")


def save_cache(fixtures: list[Fixture], path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(fixture) for fixture in fixtures], indent=2), encoding="utf-8")


def load_cache(path: Path = CACHE_PATH) -> list[Fixture]:
    if not path.exists():
        return []
    return [Fixture(**item) for item in json.loads(path.read_text(encoding="utf-8"))]
