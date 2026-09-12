"""FastAPI service for SportMonks Premier League fixture predictions."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from fixtures import SportMonksFixtureSource, load_cache, save_cache
from model import PremierLeagueModel

load_dotenv()
_fixtures = load_cache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Premier League 2026-27 Predictions", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


def _predictions() -> list[dict]:
    return PremierLeagueModel(_fixtures).predict_upcoming(_fixtures)


@app.get("/healthz")
def healthz():
    return {"service": app.title, "season": "2026-27", "cached_fixtures": len(_fixtures)}


@app.post("/fixtures/sync")
def sync_fixtures():
    global _fixtures
    try:
        _fixtures = SportMonksFixtureSource().fetch()
        save_cache(_fixtures)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SportMonks fixture sync failed: {exc}") from exc
    return {"season": "2026-27", "fixtures": len(_fixtures)}


@app.get("/fixtures")
def fixtures():
    return {"season": "2026-27", "fixtures": _fixtures}


@app.get("/predictions")
def predictions(round: int | None = Query(default=None, ge=1, le=38)):
    items = _predictions()
    if round is not None:
        items = [item for item in items if next(
            (fixture.round == round for fixture in _fixtures if fixture.id == item["fixture_id"]), False
        )]
    return {"season": "2026-27", "predictions": items}


if os.path.isdir("frontend/dist"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
