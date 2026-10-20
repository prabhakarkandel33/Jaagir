import { useEffect } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';

import { useSession } from '../lib/session';

type NavItem = { to: string; label: string; end?: boolean };

const RECRUITER_NAV: NavItem[] = [
  { to: '/employers/dashboard', label: 'Dashboard', end: true },
  { to: '/employers/roles', label: 'Roles' },
  { to: '/employers/applicants', label: 'Applicants' },
  { to: '/employers/post', label: 'Post a role' },
  { to: '/employers/profile', label: 'Company profile' },
];

const CANDIDATE_NAV: NavItem[] = [
  { to: '/me/dashboard', label: 'Dashboard', end: true },
  { to: '/me/applications', label: 'My applications' },
  { to: '/me/profile', label: 'My profile' },
];

export function PortalShell() {
  const { session, recruiter, candidate, signOut } = useSession();
  const location = useLocation();

  useEffect(() => {
    document.body.dataset.world = 'public';
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  if (!session) return null;

  const recruiterWorld = session.role === 'recruiter';
  const nav = recruiterWorld ? RECRUITER_NAV : CANDIDATE_NAV;
  const name = recruiter?.full_name ?? candidate?.full_name ?? 'there';
  const meta = recruiterWorld
    ? (recruiter?.company_name || recruiter?.email || '')
    : (candidate?.headline || candidate?.email || '');

  return (
    <div className="portal-shell" data-portal={session.role}>
      <aside className="portal-side">
        <Link className="portal-brand" to={recruiterWorld ? '/employers/dashboard' : '/me/dashboard'}>
          <span className="portal-brand__deva" lang="hi">
            जागीर
          </span>
          <span className="portal-brand__label">{recruiterWorld ? 'Employers' : 'Job seekers'}</span>
        </Link>

        <nav className="portal-nav" aria-label={recruiterWorld ? 'Employer' : 'Job seeker'}>
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="portal-who">
          <span className="portal-who__name">{name}</span>
          <span className="portal-who__meta">{meta}</span>
          <div className="portal-who__actions">
            <Link className="portal-who__link" to="/jobs">
              Browse jobs
            </Link>
            <button
              type="button"
              className="portal-who__link"
              onClick={() => {
                signOut();
                window.location.replace('/');
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <main className="portal-main">
        <Outlet />
      </main>
    </div>
  );
}
