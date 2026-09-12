import { useCallback, useEffect, useMemo, useState } from "react";
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

function UpcomingFixtureRow({ fixture }) {
  return (
    <article className="match-item">
      <div>
        <strong>{fixture.home}</strong> <span className="muted">vs</span> <strong>{fixture.away}</strong>
        {fixture.kickoff && <div className="muted small">{new Date(fixture.kickoff).toLocaleString()}</div>}
      </div>
      <div className="fixture-round muted small">
        {fixture.round ? `Matchweek ${fixture.round}` : "Upcoming fixture"}
      </div>
    </article>
  );
}

export default function App() {
  const [predictions, setPredictions] = useState([]);
  const [laLigaFixtures, setLaLigaFixtures] = useState([]);
  const [status, setStatus] = useState("Loading cached predictions...");
  const [syncing, setSyncing] = useState(false);
  const [round, setRound] = useState("");

  const applyFixtureData = useCallback((predictionPayload, laLigaPayload) => {
    setPredictions(predictionPayload.predictions);
    setLaLigaFixtures(laLigaPayload.fixtures);
    setStatus(
      predictionPayload.predictions.length || laLigaPayload.fixtures.length
        ? ""
        : "No upcoming fixtures are cached yet.",
    );
  }, []);

  const load = useCallback(async (selectedRound = round) => {
    const query = selectedRound ? `?round=${selectedRound}` : "";
    const [predictionsResponse, laLigaResponse] = await Promise.all([
      fetch(`${API_BASE}/predictions${query}`),
      fetch(`${API_BASE}/fixtures?league=la-liga&upcoming_only=true`),
    ]);
    if (!predictionsResponse.ok) throw new Error("Predictions are unavailable");
    if (!laLigaResponse.ok) throw new Error("La Liga fixtures are unavailable");
    const [predictionPayload, laLigaPayload] = await Promise.all([
      predictionsResponse.json(),
      laLigaResponse.json(),
    ]);
    return { predictionPayload, laLigaPayload };
  }, [round]);

  useEffect(() => {
    let cancelled = false;
    load()
      .then(({ predictionPayload, laLigaPayload }) => {
        if (!cancelled) applyFixtureData(predictionPayload, laLigaPayload);
      })
      .catch((error) => {
        if (!cancelled) setStatus(error.message);
      });
    return () => {
      cancelled = true;
    };
  }, [applyFixtureData, load]);

  async function sync() {
    setSyncing(true);
    setStatus("");
    try {
      const response = await fetch(`${API_BASE}/fixtures/sync`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Fixture sync failed");
      const { predictionPayload, laLigaPayload } = await load();
      applyFixtureData(predictionPayload, laLigaPayload);
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
        <h1>2026–27 football fixtures</h1>
        <p className="muted">Premier League predictions use completed season results to estimate each club&apos;s attack and defence, and La Liga upcoming fixtures are listed below.</p>
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

      <section className="card fixtures">
        <h2>{round ? `La Liga matchweek ${round} fixtures` : "La Liga upcoming fixtures"}</h2>
        {!laLigaFixtures.length && !status && <p className="muted">No upcoming La Liga fixtures are cached yet.</p>}
        {laLigaFixtures.map((fixture) => <UpcomingFixtureRow key={fixture.id} fixture={fixture} />)}
      </section>
    </main>
  );
}
