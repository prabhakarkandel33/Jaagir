import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { api } from '../lib/api';
import { dashboardPath, useSession } from '../lib/session';

export function PublicShell() {
  const { session, recruiter, candidate, signOut } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [openRoles, setOpenRoles] = useState<number | null>(null);

  useEffect(() => {
    document.body.dataset.world = 'public';
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  useEffect(() => {
    let cancelled = false;
    api.candidate
      .searchJobs({ page: 1, pageSize: 1 })
      .then((page) => {
        if (!cancelled) setOpenRoles(page.total);
      })
      .catch(() => {
        if (!cancelled) setOpenRoles(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const accountName = recruiter?.full_name ?? candidate?.full_name ?? null;

  return (
    <div className="site">
      <header className="sitehead">
        <Link className="wordmark" to="/">
          <span className="wordmark__deva" lang="hi">
            जागीर
          </span>
          <span className="wordmark__latin">job portal</span>
        </Link>

        <nav className="sitenav" aria-label="Main">
          <NavLink to="/jobs">Find jobs</NavLink>
          {session?.role === 'recruiter' ? (
            <NavLink to="/employers/dashboard">For employers</NavLink>
          ) : (
            <NavLink to="/employers">For employers</NavLink>
          )}
        </nav>

        <div className="sitehead__account">
          {session ? (
            <>
              <span className="sitehead__hello">Hi, {accountName?.split(' ')[0] ?? 'there'}</span>
              <Link className="pill" to={dashboardPath(session)}>
                Dashboard
              </Link>
              <button type="button" className="link" onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link className="pill" to="/me">
                Sign in
              </Link>
              <button
                type="button"
                className="cta cta--small cta--primary"
                onClick={() => navigate('/employers')}
              >
                Post a job
              </button>
            </>
          )}
        </div>
      </header>

      <main className="sitemain">
        <Outlet />
      </main>

      <footer className="sitefoot">
        <p className="sitefoot__brand">
          <span lang="hi">जागीर</span> · good work, good people
        </p>
        <p className="sitefoot__meta">
          {openRoles === null ? 'Roles updated every day' : `${openRoles.toLocaleString()} open roles`}
        </p>
        <div className="sitefoot__links">
          <a
            className="sitefoot__link"
            href="https://github.com/prabhakarkandel33/Jaagir"
            target="_blank"
            rel="noreferrer"
          >
            <svg
              className="sitefoot__github"
              viewBox="0 0 16 16"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
            </svg>
            Contribute on GitHub
          </a>
          <Link className="sitefoot__link" to="/admin">
            Ops console
          </Link>
        </div>
      </footer>
    </div>
  );
}
