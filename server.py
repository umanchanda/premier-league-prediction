"""FastAPI service for SportMonks Premier League fixture predictions."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from fixtures import LEAGUES, SportMonksFixtureSource, filter_fixtures, load_cache, save_cache
from model import PremierLeagueModel

load_dotenv()
_fixture_caches = {
    name: load_cache(config.cache_path)
    for name, config in LEAGUES.items()
}
_fixtures = _fixture_caches["premier-league"]
_la_liga_fixtures = _fixture_caches["la-liga"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Premier League 2026-27 Predictions", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


def _league_fixtures(league: str):
    if league not in LEAGUES:
        raise HTTPException(status_code=400, detail=f"Unsupported league: {league}")
    return _la_liga_fixtures if league == "la-liga" else _fixtures


def _predictions(fixtures: list) -> list[dict]:
    return PremierLeagueModel(fixtures).predict_upcoming(fixtures)


def _competition_name(league: str) -> str:
    return "La Liga" if league == "la-liga" else "Premier League"


@app.get("/healthz")
def healthz():
    return {
        "service": app.title,
        "seasons": {
            league: {"cached_fixtures": len(fixtures)}
            for league, fixtures in _fixture_caches.items()
        },
    }


@app.post("/fixtures/sync")
def sync_fixtures(league: str = Query(default="premier-league")):
    global _fixtures, _la_liga_fixtures
    config = LEAGUES.get(league)
    if config is None:
        raise HTTPException(status_code=400, detail=f"Unsupported league: {league}")
    try:
        fixtures = SportMonksFixtureSource(
            season_id=config.season_id,
            league_id=config.league_id,
        ).fetch()
        save_cache(fixtures, config.cache_path)
        _fixture_caches[league] = fixtures
        if league == "la-liga":
            _la_liga_fixtures = fixtures
        else:
            _fixtures = fixtures
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SportMonks fixture sync failed: {exc}") from exc
    return {"league": league, "season": "2026-27", "fixtures": len(fixtures)}


@app.get("/fixtures")
def fixtures(
    league: str = Query(default="premier-league"),
    upcoming_only: bool = Query(default=False),
    round: int | None = Query(default=None, ge=1),
):
    items = filter_fixtures(_league_fixtures(league), upcoming_only=upcoming_only, round=round)
    return {
        "league": league,
        "competition": _competition_name(league),
        "season": "2026-27",
        "fixtures": items,
    }


@app.get("/predictions")
def predictions(
    round: int | None = Query(default=None, ge=1, le=38),
    league: str = Query(default="premier-league"),
):
    fixtures = _league_fixtures(league)
    items = _predictions(fixtures)
    completed_items = PremierLeagueModel(fixtures).predict_completed(fixtures)
    if round is not None:
        items = [item for item in items if next(
            (fixture.round == round for fixture in fixtures if fixture.id == item["fixture_id"]), False
        )]
        completed_items = [item for item in completed_items if next(
            (fixture.round == round for fixture in fixtures if fixture.id == item["fixture_id"]), False
        )]
    return {
        "league": league,
        "season": "2026-27",
        "predictions": items,
        "completed_predictions": completed_items,
    }


@app.get("/predictions/{fixture_id}/heatmap")
def prediction_heatmap(
    fixture_id: str,
    league: str = Query(default="premier-league"),
):
    fixtures = _league_fixtures(league)
    fixture = next((item for item in fixtures if item.id == fixture_id), None)
    if fixture is None:
        raise HTTPException(status_code=404, detail="Fixture not found")

    if fixture.played:
        completed = sorted(
            (item for item in fixtures if item.played),
            key=lambda item: item.kickoff or "",
        )
        history = []
        for item in completed:
            if item.id == fixture.id:
                break
            history.append(item)
        model = PremierLeagueModel(history)
    else:
        model = PremierLeagueModel(fixtures)

    prediction = model.predict(fixture)
    return {
        "fixture_id": fixture.id,
        "league": league,
        "home": fixture.home,
        "away": fixture.away,
        "predicted_score": prediction.predicted_score,
        "home_score": fixture.home_score,
        "away_score": fixture.away_score,
        "matrix": model.score_matrix(fixture),
    }


if os.path.isdir("frontend/dist"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
