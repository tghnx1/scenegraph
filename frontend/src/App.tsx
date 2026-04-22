import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  database: string;
};

const apiBaseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:3000";

type Venue = {
  id: number;
  name: string;
  district: string;
  scene_focus: string;
};

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadBootstrapData() {
      try {
        const [healthResponse, venuesResponse] = await Promise.all([
          fetch(`${apiBaseUrl}/health`, {
            signal: controller.signal,
          }),
          fetch(`${apiBaseUrl}/api/venues`, {
            signal: controller.signal,
          }),
        ]);

        if (!healthResponse.ok) {
          throw new Error(`Backend health returned ${healthResponse.status}`);
        }

        if (!venuesResponse.ok) {
          throw new Error(`Venues endpoint returned ${venuesResponse.status}`);
        }

        const healthPayload = (await healthResponse.json()) as HealthResponse;
        const venuesPayload = (await venuesResponse.json()) as { venues: Venue[] };

        setHealth(healthPayload);
        setVenues(venuesPayload.venues);
      } catch (fetchError) {
        if (controller.signal.aborted) {
          return;
        }

        const message =
          fetchError instanceof Error
            ? fetchError.message
            : "Unknown error while reaching backend.";
        setError(message);
      }
    }

    void loadBootstrapData();

    return () => controller.abort();
  }, []);

  return (
    <main className="page">
      <section className="card">
        <p className="eyebrow">Step 1 • Walking Skeleton</p>
        <h1>Berlin Scene Graph</h1>
        <p className="lead">
          Minimal Docker bootstrap for the first end-to-end slice: Vite frontend,
          FastAPI backend, and Postgres wired through one shared startup flow.
        </p>

        <div className="status-grid">
          <article className="status-item">
            <span className="label">Frontend</span>
            <strong>Running</strong>
          </article>
          <article className="status-item">
            <span className="label">Backend health</span>
            <strong>{health?.status ?? "Checking..."}</strong>
          </article>
          <article className="status-item">
            <span className="label">Database</span>
            <strong>{health?.database ?? "Connecting..."}</strong>
          </article>
        </div>

        <section className="venues-panel">
          <div className="venues-header">
            <div>
              <span className="label">Read-only API route</span>
              <h2>Seed venues from Postgres</h2>
            </div>
            <strong className="venues-count">{venues.length} rows</strong>
          </div>

          <div className="venue-list">
            {venues.map((venue) => (
              <article className="venue-card" key={venue.id}>
                <h3>{venue.name}</h3>
                <p>{venue.district}</p>
                <span>{venue.scene_focus}</span>
              </article>
            ))}
          </div>
        </section>

        {error ? <p className="error">Backend check failed: {error}</p> : null}
      </section>
    </main>
  );
}
