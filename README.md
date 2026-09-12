# Premier League 2026-27 Predictor

A FastAPI and React app that fetches Premier League fixtures through
[SportMonks](https://www.sportmonks.com/) and predicts a scoreline for
every upcoming match.

The model learns separate home/away attacking and defensive rates from completed
2026-27 fixtures, applies shrinkage to league averages early in the season, and
uses independent Poisson goal distributions to select the most likely scoreline.
It also returns home-win, draw, and away-win probabilities.

## Set up

```powershell
python3 -m pip install -r requirements.txt
npm run frontend:install
```

Create `.env` with your SportMonks token:

```dotenv
MONKS_KEY=your-sportmonks-api-token
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

The sync stores `data/fixtures-2026-27.json`, allowing predictions to remain
available without another provider request. Open the frontend through the
FastAPI server after building it, or point Vite's `VITE_API_URL` at the API.

La Liga 2026-27 fixtures are also cached in
`data/la-liga-fixtures-2026-27.json` using SportMonks league ID `564` and
season ID `27965`.

## API

- `POST /fixtures/sync` fetches and caches the 2026-27 fixture list.
- `GET /fixtures` returns the cached Premier League fixtures.
- `GET /fixtures?league=la-liga&upcoming_only=true` returns cached upcoming La Liga fixtures.
- `GET /predictions` returns a predicted scoreline for every unplayed fixture.
- `GET /predictions?round=1` filters predictions to a matchweek.
- `GET /healthz` reports the cache state.

## Validate

```powershell
npm run test
npm run lint
```
