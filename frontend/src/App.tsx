import { useEffect, useState } from 'react';

import { Badge } from './components/ui';
import { BASES, api } from './lib/api';
import type { Readyz } from './lib/types';
import { Candidate, type CandidateSession } from './views/Candidate';
import { Discover } from './views/Discover';
import { Ops } from './views/Ops';
import { Recruiter, type RecruiterSession } from './views/Recruiter';

type Tab = 'discover' | 'recruiter' | 'candidate' | 'ops';
type Signal = 'ok' | 'degraded' | 'down' | 'unknown';

const TABS: { id: Tab; label: string; hint: string; say: string }[] = [
  {
    id: 'discover',
    label: 'Discover',
    hint: 'Search, read, apply',
    say: 'Search either copy, read the job, apply.',
  },
  {
    id: 'recruiter',
    label: 'Recruiter',
    hint: 'Jobs and applicants',
    say: 'Write jobs, publish them, read applicants.',
  },
  {
    id: 'candidate',
    label: 'Candidate',
    hint: 'Profile and history',
    say: 'Keep the profile current and track applications.',
  },
  {
    id: 'ops',
    label: 'Ops',
    hint: 'Outbox, sync, DLQ',
    say: 'Outbox, snapshot, reconciliation, and the DLQ.',
  },
];

function tabFromHash(): Tab {
  const value = window.location.hash.replace('#', '');
  return TABS.some((item) => item.id === value) ? (value as Tab) : 'discover';
}

function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function store(key: string, value: unknown): void {
  try {
    if (value === null || value === undefined || value === '') {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, JSON.stringify(value));
    }
  } catch {
    // A full or blocked storage must not break the page.
  }
}

function fromReady(ready: Readyz | null): Signal {
  if (!ready) return 'unknown';
  return ready.status === 'ok' ? 'ok' : 'degraded';
}

function fromCheck(value: string | undefined): Signal {
  if (value === 'ok' || value === 'up') return 'ok';
  if (value === 'degraded' || value === 'stale') return 'degraded';
  if (value === 'down') return 'down';
  return 'unknown';
}

function combine(values: (string | undefined)[]): Signal {
  const states = values.map(fromCheck);
  if (states.some((state) => state === 'down')) return 'down';
  if (states.some((state) => state === 'degraded')) return 'degraded';
  if (states.length > 0 && states.every((state) => state === 'ok')) return 'ok';
  return 'unknown';
}

function tone(state: Signal): 'ok' | 'warn' | 'danger' | 'muted' {
  if (state === 'ok') return 'ok';
  if (state === 'degraded') return 'warn';
  if (state === 'down') return 'danger';
  return 'muted';
}

function SignalPath({ nodes }: { nodes: { id: string; label: string; state: Signal }[] }) {
  const spoken = nodes.map((node) => `${node.label} ${node.state}`).join(', ');
  return (
    <div className="signal" role="img" aria-label={`Pipeline: ${spoken}`}>
      <span className="signal__track" aria-hidden="true" />
      {nodes.map((node) => (
        <div key={node.id} className={`signal__node is-${node.state}`}>
          <span className="signal__dot" aria-hidden="true">
            <span key={node.state} className="signal__halo" />
          </span>
          <span className="signal__label">{node.label}</span>
          <span className="signal__state">{node.state}</span>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [recruiterSession, setRecruiterSession] = useState<RecruiterSession | null>(() =>
    readStored<RecruiterSession | null>('jp.recruiter', null),
  );
  const [candidateSession, setCandidateSession] = useState<CandidateSession | null>(() =>
    readStored<CandidateSession | null>('jp.candidate', null),
  );
  const [internalToken, setInternalToken] = useState<string>(() =>
    readStored<string>('jp.internal', ''),
  );

  const [jobReady, setJobReady] = useState<Readyz | null>(null);
  const [candidateReady, setCandidateReady] = useState<Readyz | null>(null);

  useEffect(() => {
    const sync = () => setTab(tabFromHash());
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);

  useEffect(() => store('jp.recruiter', recruiterSession), [recruiterSession]);
  useEffect(() => store('jp.candidate', candidateSession), [candidateSession]);
  useEffect(() => store('jp.internal', internalToken), [internalToken]);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      const [job, candidate] = await Promise.all([
        api.job.ready().catch(() => null),
        api.candidate.ready().catch(() => null),
      ]);
      if (cancelled) return;
      setJobReady(job);
      setCandidateReady(candidate);
    }
    void check();
    const timer = window.setInterval(() => void check(), 20000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const jobState = fromReady(jobReady);
  const candidateState = fromReady(candidateReady);
  const kafkaState = combine([jobReady?.checks.kafka, candidateReady?.checks.kafka]);
  const current = TABS.find((item) => item.id === tab) ?? TABS[0];

  function selectTab(next: Tab) {
    setTab(next);
    window.location.hash = next;
  }

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
            <p className="brand__latin">Jaagir · job portal</p>
          </div>
        </div>

        <p className="brand__note">One workbench for both services and every endpoint.</p>

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
                <Badge tone={tone(fromCheck(candidateReady?.checks.consumer ?? candidateReady?.checks.kafka))}>
                  consumer {candidateReady?.checks.consumer ?? 'unknown'}
                </Badge>
              </dd>
            </div>
          </dl>
        </section>

        <nav className="nav" aria-label="Sections">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className="nav__item"
              aria-current={tab === item.id ? 'page' : undefined}
              onClick={() => selectTab(item.id)}
            >
              <span className="nav__label">{item.label}</span>
              <span className="nav__hint">{item.hint}</span>
            </button>
          ))}
        </nav>

        <div className="rail__foot">
          <p className="rail__who">
            {recruiterSession ? `Recruiter: ${recruiterSession.profile.full_name}` : 'No recruiter'}
            <br />
            {candidateSession ? `Candidate: ${candidateSession.profile.full_name}` : 'No candidate'}
          </p>
          <p className="rail__urls mono">
            {BASES.job.replace(/^https?:\/\//, '')}
            <br />
            {BASES.candidate.replace(/^https?:\/\//, '')}
          </p>
          <div className="row row--wrap">
            <a className="link link--small" href={`${BASES.job}/docs`} target="_blank" rel="noreferrer">
              Job API docs
            </a>
            <a
              className="link link--small"
              href={`${BASES.candidate}/docs`}
              target="_blank"
              rel="noreferrer"
            >
              Candidate API docs
            </a>
          </div>
          {recruiterSession || candidateSession || internalToken ? (
            <button
              type="button"
              className="link link--small"
              onClick={() => {
                setRecruiterSession(null);
                setCandidateSession(null);
                setInternalToken('');
              }}
            >
              Clear saved sessions
            </button>
          ) : null}
        </div>
      </aside>

      <main className="board">
        <header className="board__head">
          <div>
            <h2 className="board__title">{current.label}</h2>
            <p className="board__say">{current.say}</p>
          </div>
          <p className="board__meta mono">
            {tab === 'ops' ? 'internal routes need the token' : 'tokens stay in this browser'}
          </p>
        </header>

        {tab === 'discover' ? (
          <Discover
            candidateToken={candidateSession?.token ?? null}
            candidateName={candidateSession?.profile.full_name ?? null}
            onNeedCandidate={() => selectTab('candidate')}
          />
        ) : null}

        {tab === 'recruiter' ? (
          <Recruiter session={recruiterSession} onSession={setRecruiterSession} />
        ) : null}

        {tab === 'candidate' ? (
          <Candidate session={candidateSession} onSession={setCandidateSession} />
        ) : null}

        {tab === 'ops' ? (
          <Ops internalToken={internalToken} onInternalToken={setInternalToken} />
        ) : null}
      </main>
    </div>
  );
}
