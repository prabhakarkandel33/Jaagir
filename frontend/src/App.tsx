import { useCallback, useEffect, useState } from 'react';

import { api } from './lib/api';
import { Admin, type AdminTokens } from './views/Admin';
import { Candidate, type CandidateSession } from './views/Candidate';
import { Discover } from './views/Discover';
import { Landing } from './views/Landing';
import { Recruiter, type RecruiterSession } from './views/Recruiter';

const PUBLIC_PATHS = ['/', '/jobs', '/employers', '/me'];

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

function currentPath(): string {
  const path = window.location.pathname.replace(/\/+$/, '');
  return path === '' ? '/' : path;
}

export default function App() {
  const [path, setPath] = useState<string>(currentPath);

  const [recruiterSession, setRecruiterSession] = useState<RecruiterSession | null>(() =>
    readStored<RecruiterSession | null>('jp.recruiter', null),
  );
  const [candidateSession, setCandidateSession] = useState<CandidateSession | null>(() =>
    readStored<CandidateSession | null>('jp.candidate', null),
  );
  const [adminTokens, setAdminTokens] = useState<AdminTokens | null>(() =>
    readStored<AdminTokens | null>('jp.admin', null),
  );
  const [openRoles, setOpenRoles] = useState<number | null>(null);

  const go = useCallback((next: string) => {
    if (currentPath() !== next) {
      window.history.pushState({}, '', next);
    }
    setPath(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    const sync = () => setPath(currentPath());
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, []);

  useEffect(() => store('jp.recruiter', recruiterSession), [recruiterSession]);
  useEffect(() => store('jp.candidate', candidateSession), [candidateSession]);
  useEffect(() => store('jp.admin', adminTokens), [adminTokens]);

  useEffect(() => {
    document.body.dataset.world = path === '/admin' ? 'admin' : 'public';
  }, [path]);

  useEffect(() => {
    api.candidate
      .searchJobs({ page: 1, pageSize: 1 })
      .then((page) => setOpenRoles(page.total))
      .catch(() => setOpenRoles(null));
  }, [path]);

  if (path === '/admin') {
    return <Admin tokens={adminTokens} onTokens={setAdminTokens} />;
  }

  const route = PUBLIC_PATHS.includes(path) ? path : '/';

  return (
    <div className="site">
      <header className="sitehead">
        <a
          className="wordmark"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            go('/');
          }}
        >
          <span className="wordmark__deva" lang="hi">
            जागीर
          </span>
          <span className="wordmark__latin">job portal</span>
        </a>

        <nav className="sitenav" aria-label="Main">
          <a
            href="/jobs"
            aria-current={route === '/jobs' ? 'page' : undefined}
            onClick={(event) => {
              event.preventDefault();
              go('/jobs');
            }}
          >
            Find jobs
          </a>
          <a
            href="/employers"
            aria-current={route === '/employers' ? 'page' : undefined}
            onClick={(event) => {
              event.preventDefault();
              go('/employers');
            }}
          >
            For employers
          </a>
        </nav>

        <div className="sitehead__account">
          {candidateSession ? (
            <a
              className="pill"
              href="/me"
              onClick={(event) => {
                event.preventDefault();
                go('/me');
              }}
            >
              Hi, {candidateSession.profile.full_name.split(' ')[0]}
            </a>
          ) : (
            <a
              className="cta cta--small cta--primary"
              href="/me"
              onClick={(event) => {
                event.preventDefault();
                go('/me');
              }}
            >
              Sign in
            </a>
          )}
        </div>
      </header>

      <main className="sitemain">
        {route === '/' ? <Landing go={go} /> : null}

        {route === '/jobs' ? (
          <Discover
            candidateToken={candidateSession?.token ?? null}
            candidateName={candidateSession?.profile.full_name ?? null}
            onOpenAccount={() => go('/me')}
          />
        ) : null}

        {route === '/employers' ? (
          <Recruiter session={recruiterSession} onSession={setRecruiterSession} />
        ) : null}

        {route === '/me' ? (
          <Candidate
            session={candidateSession}
            onSession={setCandidateSession}
            onExplore={() => go('/jobs')}
            onEmployer={() => go('/employers')}
          />
        ) : null}
      </main>

      <footer className="sitefoot">
        <p className="sitefoot__brand">
          <span lang="hi">जागीर</span> · good work, good people
        </p>
        <p className="sitefoot__meta">
          {openRoles === null ? 'Roles updated every day' : `${openRoles.toLocaleString()} open roles`}
        </p>
        <a className="sitefoot__ops" href="/admin">
          Ops console
        </a>
      </footer>
    </div>
  );
}
