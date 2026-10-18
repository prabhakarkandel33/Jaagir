import { useState } from 'react';

const JOB_SERVICE_URL = import.meta.env.VITE_JOB_SERVICE_URL ?? 'http://localhost:3001';
const CANDIDATE_SERVICE_URL =
  import.meta.env.VITE_CANDIDATE_SERVICE_URL ?? 'http://localhost:3002';

type Health = { service: string; status: string };

export default function App() {
  const [health, setHealth] = useState<Health[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function checkHealth() {
    setError(null);
    try {
      const responses = await Promise.all(
        [JOB_SERVICE_URL, CANDIDATE_SERVICE_URL].map((base) =>
          fetch(`${base}/healthz`).then((r) => r.json() as Promise<Health>),
        ),
      );
      setHealth(responses);
    } catch {
      setHealth([]);
      setError('Could not reach the services. Run `tasks.ps1 dev` first.');
    }
  }

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 640, margin: '4rem auto' }}>
      <h1>Job Portal</h1>
      <p>Recruiters post jobs. Candidates search and apply.</p>
      <button onClick={checkHealth}>Check service health</button>
      {error && <p role="alert">{error}</p>}
      <ul>
        {health.map((item) => (
          <li key={item.service}>
            {item.service}: <strong>{item.status}</strong>
          </li>
        ))}
      </ul>
    </main>
  );
}
