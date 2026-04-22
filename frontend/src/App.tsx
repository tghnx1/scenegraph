import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
};

const apiBaseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:3000";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Backend returned ${response.status}`);
        }

        const payload = (await response.json()) as HealthResponse;
        setHealth(payload);
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

    void loadHealth();

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
            <span className="label">API base URL</span>
            <strong>{apiBaseUrl}</strong>
          </article>
        </div>

        {error ? <p className="error">Backend check failed: {error}</p> : null}
      </section>
    </main>
  );
}
