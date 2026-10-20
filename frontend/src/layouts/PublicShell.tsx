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
        <Link className="sitefoot__ops" to="/admin">
          Ops console
        </Link>
      </footer>
    </div>
  );
}
