import { useCallback, useEffect, useState } from 'react';

import { Badge, Button, ErrorNote, Field } from '../components/ui';
import { SignalPath, combine, fromCheck, fromReady, tone } from '../components/Signal';
import { adminLogin, api } from '../lib/api';
import type { Readyz } from '../lib/types';
import { Ops } from './Ops';

export type AdminTokens = { job: string; candidate: string };

export function Admin({
  tokens,
  onTokens,
}: {
  tokens: AdminTokens | null;
  onTokens: (tokens: AdminTokens | null) => void;
}) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [loginError, setLoginError] = useState<unknown>(null);

  const [jobReady, setJobReady] = useState<Readyz | null>(null);
  const [candidateReady, setCandidateReady] = useState<Readyz | null>(null);
  const [probing, setProbing] = useState(false);
  const [probeError, setProbeError] = useState<unknown>(null);

  const probe = useCallback(async () => {
    setProbing(true);
    setProbeError(null);
    try {
      const [job, candidate] = await Promise.all([api.job.ready(), api.candidate.ready()]);
      setJobReady(job);
      setCandidateReady(candidate);
    } catch (cause) {
      setProbeError(cause);
    } finally {
      setProbing(false);
    }
  }, []);

  useEffect(() => {
    if (tokens) void probe();
  }, [tokens, probe]);

  async function signIn(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setLoginError(null);
    try {
      const [job, candidate] = await Promise.all([
        adminLogin('job', username, password),
        adminLogin('candidate', username, password),
      ]);
      onTokens({ job: job.token, candidate: candidate.token });
      setPassword('');
    } catch (cause) {
      setLoginError(cause);
    } finally {
      setBusy(false);
    }
  }

  if (!tokens) {
    return (
      <div className="app">
        <aside className="rail">
          <div className="brand">
            <span className="brand__mark" aria-hidden="true">
              ज
            </span>
            <div className="brand__text">
              <h1 className="brand__name" lang="hi">
                जागीर
              </h1>
              <p className="brand__latin">Ops console</p>
            </div>
          </div>
          <p className="brand__note">
            Internal view of the pipeline: outbox, replica sync, DLQ, snapshots.
          </p>
          <div className="rail__foot">
            <p className="rail__urls mono">staff access only</p>
            <a className="link link--small" href="/">
              Back to the public site
            </a>
          </div>
        </aside>

        <main className="board">
          <header className="board__head">
            <div>
              <h2 className="board__title">Sign in</h2>
              <p className="board__say">
                Use the admin credentials from each service <code>.env</code> file.
              </p>
            </div>
            <p className="board__meta mono">ADMIN_USERNAME / ADMIN_PASSWORD</p>
          </header>

          <div className="stack">
            <section className="panel panel--both">
              <header className="panel__head">
                <div className="panel__intro">
                  <div className="panel__titleRow">
                    <h2 className="panel__title">Admin credentials</h2>
                  </div>
                  <p className="panel__subtitle">
                    One sign-in covers both services; each returns its own internal token.
                  </p>
                </div>
              </header>
              <div className="panel__body">
                <form className="grid" onSubmit={signIn}>
                  <Field label="Username" wide>
                    <input
                      className="input"
                      autoComplete="username"
                      required
                      value={username}
                      onChange={(event) => setUsername(event.target.value)}
                    />
                  </Field>
                  <Field label="Password" wide>
                    <input
                      className="input"
                      type="password"
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                  </Field>
                  <div className="grid__submit">
                    <Button type="submit" busy={busy}>
                      Sign in
                    </Button>
                  </div>
                </form>
                <ErrorNote error={loginError} />
              </div>
            </section>
          </div>
        </main>
      </div>
    );
  }

  const jobState = fromReady(jobReady);
  const candidateState = fromReady(candidateReady);
  const kafkaState = combine([jobReady?.checks.kafka, candidateReady?.checks.kafka]);

  return (
    <div className="app">
      <aside className="rail">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true">
            ज
          </span>
          <div className="brand__text">
            <h1 className="brand__name" lang="hi">
              जागीर
            </h1>
            <p className="brand__latin">Ops console</p>
          </div>
        </div>

        <section className="rail__block" aria-label="Pipeline status">
          <SignalPath
            nodes={[
              { id: 'job', label: 'Job API', state: jobState },
              { id: 'kafka', label: 'Kafka', state: kafkaState },
              { id: 'candidate', label: 'Candidate', state: candidateState },
            ]}
          />
          <dl className="checks">
            <div>
              <dt>Job</dt>
              <dd>
                <Badge tone={tone(fromCheck(jobReady?.checks.database))}>
                  db {jobReady?.checks.database ?? 'unknown'}
                </Badge>
                <Badge tone={tone(fromCheck(jobReady?.checks.kafka))}>
                  kafka {jobReady?.checks.kafka ?? 'unknown'}
                </Badge>
              </dd>
            </div>
            <div>
              <dt>Candidate</dt>
              <dd>
                <Badge tone={tone(fromCheck(candidateReady?.checks.database))}>
                  db {candidateReady?.checks.database ?? 'unknown'}
                </Badge>
                <Badge
                  tone={tone(
                    fromCheck(candidateReady?.checks.consumer ?? candidateReady?.checks.kafka),
                  )}
                >
                  consumer {candidateReady?.checks.consumer ?? 'unknown'}
                </Badge>
              </dd>
            </div>
          </dl>
        </section>

        <div className="rail__foot">
          <p className="rail__who">
            Signed in as admin
            <br />
            Internal token held in this browser only.
          </p>
          <div className="row row--wrap">
            <a className="link link--small" href="/">
              Public site
            </a>
          </div>
          <button type="button" className="link link--small" onClick={() => onTokens(null)}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="board">
        <header className="board__head">
          <div>
            <h2 className="board__title">Operations</h2>
            <p className="board__say">Outbox, replica sync, DLQ replay, snapshot, wire log.</p>
          </div>
          <div className="row">
            <Button variant="ghost" onClick={() => void probe()} busy={probing}>
              Probe health
            </Button>
          </div>
        </header>

        <div className="stack">
          <ErrorNote error={probeError} />
          <Ops jobToken={tokens.job} candidateToken={tokens.candidate} />
        </div>
      </main>
    </div>
  );
}
