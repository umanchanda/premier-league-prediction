import { useEffect, useMemo, useState } from "react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_URL ?? "";
const LEAGUE_LABELS = {
  "premier-league": "Premier League",
  "la-liga": "La Liga",
};

function probability(value) {
  return `${Math.round(value * 100)}%`;
}

function bothTeamsToScore(scoreline) {
  const [homeGoals, awayGoals] = scoreline.split("-").map(Number);
  return homeGoals > 0 && awayGoals > 0 ? "Y" : "N";
}

function FixtureRow({ prediction, onSelect }) {
  const played = typeof prediction.home_score === "number"
    && typeof prediction.away_score === "number";

  return (
    <button className="match-item" type="button" onClick={() => onSelect(prediction)}>
      <div className="fixture-name" role="cell">
        <strong>{prediction.home}</strong> <span className="muted">vs</span> <strong>{prediction.away}</strong>
        {prediction.kickoff && <div className="muted small">{new Date(prediction.kickoff).toLocaleString()}</div>}
      </div>
      <div role="cell"><strong>{prediction.predicted_score}</strong></div>
      <div role="cell"><strong>{played ? `${prediction.home_score}-${prediction.away_score}` : "-"}</strong></div>
      <div className="moneyline" role="cell">
        <span>H {probability(prediction.home_win_probability)}</span>
        <span>D {probability(prediction.draw_probability)}</span>
        <span>A {probability(prediction.away_win_probability)}</span>
      </div>
      <div role="cell"><strong>{bothTeamsToScore(prediction.predicted_score)}</strong></div>
    </button>
  );
}

function ScoreHeatmap({ fixture, heatmap, loading, error, onClose }) {
  if (loading) return <section className="card heatmap-panel"><p className="muted">Loading score probabilities...</p></section>;
  if (error) return <section className="card heatmap-panel"><p className="muted">{error}</p></section>;
  if (!heatmap) return null;

  const cells = heatmap.matrix.flat();
  const maxProbability = Math.max(...cells.map((cell) => cell.probability));
  const actualScore = typeof fixture.home_score === "number" && typeof fixture.away_score === "number"
    ? `${fixture.home_score}-${fixture.away_score}`
    : null;

  return (
    <section className="card heatmap-panel">
      <div className="heatmap-heading">
        <div>
          <h2>{fixture.home} vs {fixture.away}</h2>
          <p className="muted small">Darker cells indicate more likely scorelines.</p>
        </div>
        <button className="btn ghost" type="button" onClick={onClose}>Close</button>
      </div>
      <div className="heatmap-grid" aria-label="Possible score probabilities">
        <div className="heatmap-corner">H \ A</div>
        {heatmap.matrix[0].map((cell) => <div className="heatmap-axis" key={`away-${cell.away_goals}`}>{cell.away_goals}</div>)}
        {heatmap.matrix.map((row) => (
          <div className="heatmap-row" key={`home-${row[0].home_goals}`}>
            <div className="heatmap-axis">{row[0].home_goals}</div>
            {row.map((cell) => {
              const scoreline = `${cell.home_goals}-${cell.away_goals}`;
              const isPredicted = scoreline === heatmap.predicted_score;
              const isActual = scoreline === actualScore;
              return (
                <div
                  className={`heatmap-cell${isPredicted ? " predicted" : ""}${isActual ? " actual" : ""}`}
                  key={scoreline}
                  style={{ backgroundColor: `rgba(11, 92, 255, ${Math.max(0.08, cell.probability / maxProbability)})` }}
                  title={`${scoreline}: ${probability(cell.probability)}`}
                >
                  {probability(cell.probability)}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div className="heatmap-legend muted small">
        <span>Predicted: {heatmap.predicted_score}</span>
        {actualScore && <span>Actual: {actualScore}</span>}
      </div>
    </section>
  );
}

async function fetchItems(selectedLeague, selectedRound) {
  const params = new URLSearchParams({ league: selectedLeague });
  if (selectedRound) params.set("round", selectedRound);
  const predictionsResponse = await fetch(`${API_BASE}/predictions?${params}`);
  if (!predictionsResponse.ok) throw new Error("Fixtures are unavailable");
  const predictionPayload = await predictionsResponse.json();
  const completed = selectedRound ? predictionPayload.completed_predictions : [];
  return [...completed, ...predictionPayload.predictions];
}

export default function App() {
  const [predictions, setPredictions] = useState([]);
  const [status, setStatus] = useState("Loading cached predictions...");
  const [syncing, setSyncing] = useState(false);
  const [league, setLeague] = useState("premier-league");
  const [round, setRound] = useState("");
  const [selectedFixture, setSelectedFixture] = useState(null);
  const [heatmap, setHeatmap] = useState(null);
  const [heatmapLoading, setHeatmapLoading] = useState(false);
  const [heatmapError, setHeatmapError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchItems(league, round).then((items) => {
      if (!cancelled) {
        setPredictions(items);
        setStatus(items.length ? "" : "No fixtures are cached for this matchweek yet.");
      }
    }).catch((error) => {
      if (!cancelled) setStatus(error.message);
    });
    return () => { cancelled = true; };
  }, [league, round]);

  async function sync() {
    setSyncing(true);
    setStatus("");
    try {
      const response = await fetch(`${API_BASE}/fixtures/sync?league=${league}`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Fixture sync failed");
      const items = await fetchItems(league, round);
      setPredictions(items);
      setStatus(items.length ? "" : "No fixtures are cached for this matchweek yet.");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setSyncing(false);
    }
  }

  async function selectFixture(fixture) {
    setSelectedFixture(fixture);
    setHeatmap(null);
    setHeatmapError("");
    setHeatmapLoading(true);
    try {
      const response = await fetch(`${API_BASE}/predictions/${fixture.fixture_id}/heatmap?league=${league}`);
      if (!response.ok) throw new Error("Score probabilities are unavailable");
      setHeatmap(await response.json());
    } catch (error) {
      setHeatmapError(error.message);
    } finally {
      setHeatmapLoading(false);
    }
  }

  function changeLeague(nextLeague) {
    setLeague(nextLeague);
    setRound("");
    setSelectedFixture(null);
    setHeatmap(null);
  }

  const heading = useMemo(
    () => round ? `Matchweek ${round}` : "All upcoming fixtures",
    [round],
  );

  return (
    <main className="prediction-desk">
      <header>
        <p className="eyebrow">SportMonks data · Poisson score model</p>
        <h1>{LEAGUE_LABELS[league]} 2026–27 predictions</h1>
        <p className="muted">Predicted scorelines use completed season results to estimate each club&apos;s attack and defence.</p>
      </header>

      <section className="card controls">
        <div className="league-toggle" aria-label="League">
          {Object.entries(LEAGUE_LABELS).map(([value, label]) => (
            <button
              className={league === value ? "active" : ""}
              key={value}
              type="button"
              onClick={() => changeLeague(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <label htmlFor="round">Matchweek</label>
        <select id="round" value={round} onChange={(event) => setRound(event.target.value)}>
          <option value="">All upcoming fixtures</option>
          {Array.from({ length: 38 }, (_, index) => <option key={index + 1} value={index + 1}>Round {index + 1}</option>)}
        </select>
        <button className="btn primary" onClick={sync} disabled={syncing}>
          {syncing ? "Syncing fixtures..." : "Sync fixtures from SportMonks"}
        </button>
      </section>

      <section className="card fixtures">
        <h2>{heading}</h2>
        <div className="match-header" role="row">
          <strong>Fixture Name (A v B)</strong>
          <strong>Predicted Scoreline</strong>
          <strong>Actual Scoreline</strong>
          <strong>Moneyline (H % D % A %)</strong>
          <strong>BTTS</strong>
        </div>
        {status && <p className="muted">{status}</p>}
        {predictions.map((prediction) => <FixtureRow key={prediction.fixture_id} prediction={prediction} onSelect={selectFixture} />)}
      </section>
      {selectedFixture && <ScoreHeatmap
        fixture={selectedFixture}
        heatmap={heatmap}
        loading={heatmapLoading}
        error={heatmapError}
        onClose={() => setSelectedFixture(null)}
      />}
    </main>
  );
}
