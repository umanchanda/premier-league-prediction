import { useEffect, useMemo, useState } from "react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

function probability(value) {
  return `${Math.round(value * 100)}%`;
}

function FixtureRow({ prediction }) {
  return (
    <article className="match-item">
      <div>
        <strong>{prediction.home}</strong> <span className="muted">vs</span> <strong>{prediction.away}</strong>
        {prediction.kickoff && <div className="muted small">{new Date(prediction.kickoff).toLocaleString()}</div>}
      </div>
      <div className="prediction-score">
        <strong>{prediction.predicted_score}</strong>
        <div className="muted small">Most likely score ({probability(prediction.scoreline_probability)})</div>
      </div>
      <div className="small">
        <span>H {probability(prediction.home_win_probability)}</span>
        <span> D {probability(prediction.draw_probability)}</span>
        <span> A {probability(prediction.away_win_probability)}</span>
      </div>
    </article>
  );
}

export default function App() {
  const [predictions, setPredictions] = useState([]);
  const [status, setStatus] = useState("Loading cached predictions...");
  const [syncing, setSyncing] = useState(false);
  const [round, setRound] = useState("");

  async function load(selectedRound = round) {
    const query = selectedRound ? `?round=${selectedRound}` : "";
    const response = await fetch(`${API_BASE}/predictions${query}`);
    if (!response.ok) throw new Error("Predictions are unavailable");
    const payload = await response.json();
    setPredictions(payload.predictions);
    setStatus(payload.predictions.length ? "" : "No upcoming fixtures are cached yet.");
  }

  useEffect(() => {
    load().catch((error) => setStatus(error.message));
  }, [round]);

  async function sync() {
    setSyncing(true);
    setStatus("");
    try {
      const response = await fetch(`${API_BASE}/fixtures/sync`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Fixture sync failed");
      await load();
    } catch (error) {
      setStatus(error.message);
    } finally {
      setSyncing(false);
    }
  }

  const heading = useMemo(
    () => round ? `Matchweek ${round} predictions` : "All upcoming fixtures",
    [round],
  );

  return (
    <main className="prediction-desk">
      <header>
        <p className="eyebrow">SportMonks data · Poisson score model</p>
        <h1>Premier League 2026–27 predictions</h1>
        <p className="muted">Predicted scorelines use completed season results to estimate each club&apos;s attack and defence.</p>
      </header>

      <section className="card controls">
        <label htmlFor="round">Matchweek</label>
        <select id="round" value={round} onChange={(event) => setRound(event.target.value)}>
          <option value="">All upcoming fixtures</option>
          {Array.from({ length: 38 }, (_, index) => <option key={index + 1} value={index + 1}>Matchweek {index + 1}</option>)}
        </select>
        <button className="btn primary" onClick={sync} disabled={syncing}>
          {syncing ? "Syncing fixtures..." : "Sync fixtures from SportMonks"}
        </button>
      </section>

      <section className="card fixtures">
        <h2>{heading}</h2>
        {status && <p className="muted">{status}</p>}
        {predictions.map((prediction) => <FixtureRow key={prediction.fixture_id} prediction={prediction} />)}
      </section>
    </main>
  );
}
