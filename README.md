# Premier League 2026-27 Predictor

A FastAPI and React app that fetches Premier League fixtures through
[SportMonks](https://www.sportmonks.com/) and predicts a scoreline for
every upcoming match.

The model fits one attacking and one defensive rating per team plus a
league-wide home advantage, using weighted Poisson regression over this season's
results and the previous two seasons (older games count less, with a 180-day
half-life). Promoted teams start from the average rating of the teams they
replaced, and ridge shrinkage pulls teams with little data toward average. It
returns home-win, draw, and away-win probabilities, and the likeliest scoreline
within the likeliest result.

## Set up

```powershell
python3 -m pip install -r requirements.txt
npm run frontend:install
```

Create `.env` with your SportMonks token:

```dotenv
SPORTSMONKS_KEY=your-sportmonks-api-token
```

## Run

```powershell
npm run build
npm run start
```

Then sync current fixtures:

```powershell
npm run sync
```

You can also fetch fixtures directly from the command line. Premier League is
the default; use `--league la-liga` for the La Liga cache:

```powershell
python3 fixtures.py
python3 fixtures.py --league la-liga
```

The sync stores `data/fixtures-2026-27.json`, allowing predictions to remain
available without another provider request. Open the frontend through the
FastAPI server after building it, or point Vite's `VITE_API_URL` at the API.

La Liga 2026-27 fixtures are also cached in
`data/la-liga-fixtures-2026-27.json` using SportMonks league ID `564` and
season ID `27965`.

## Prior seasons

`data/history/` holds 2024-25 and 2025-26 results for both leagues, taken from
the public-domain [openfootball](https://github.com/openfootball/football.json)
dataset with team names mapped to SportMonks names. Rebuild it with:

```powershell
python3 history.py
```

When a new season starts, add the finished season to `HISTORY_SEASONS` in
`history.py` and drop the oldest, then add any new team names to
`TEAM_ALIASES`.

## API

- `POST /fixtures/sync` fetches and caches the 2026-27 fixture list.
- `POST /fixtures/sync?league=la-liga` syncs the La Liga cache; Premier League is the default.
- `GET /fixtures?league=la-liga` returns the selected league's cached fixtures.
- `GET /fixtures?league=la-liga&upcoming_only=true&round=1` filters cached fixtures.
- `GET /predictions` returns predicted scorelines for every unplayed fixture.
- `GET /predictions?league=la-liga&round=1` filters a league's predictions to a matchweek.
- `GET /predictions/{fixture_id}/heatmap?league=la-liga` returns a selected fixture's score probability matrix.
- `GET /healthz` reports the cache state.

## Validate

```powershell
npm run test
npm run lint
python3 backtest.py
```

`backtest.py` replays the latest prior season matchday by matchday, using only
results available before each one, and reports RPS (lower is better), result
accuracy, exact-score rate and points per match. Use it to judge model changes.
