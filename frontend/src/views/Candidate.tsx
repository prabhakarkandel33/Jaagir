import { useCallback, useEffect, useState } from 'react';

import {
  Badge,
  Button,
  Empty,
  ErrorNote,
  Field,
  statusLabel,
  statusTone,
} from '../components/ui';
import { api } from '../lib/api';
import { formatDate, joinList, splitList } from '../lib/format';
import type { Application, Candidate as CandidateProfile, Page } from '../lib/types';

export type CandidateSession = { token: string; profile: CandidateProfile };

export function Candidate({
  session,
  onSession,
  onExplore,
  onEmployer,
}: {
  session: CandidateSession | null;
  onSession: (session: CandidateSession | null) => void;
  onExplore: () => void;
  onEmployer: () => void;
}) {
  const token = session?.token ?? null;

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [credentials, setCredentials] = useState({
    email: '',
    password: '',
    full_name: '',
    phone: '',
  });
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<unknown>(null);

  const [profile, setProfile] = useState<CandidateProfile | null>(session?.profile ?? null);
  const [form, setForm] = useState({
    full_name: '',
    phone: '',
    headline: '',
    location: '',
    skills: '',
    summary: '',
    resume_url: '',
  });
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState<unknown>(null);
  const [profileNote, setProfileNote] = useState<string | null>(null);

  const [applications, setApplications] = useState<Page<Application> | null>(null);
  const [appsPage, setAppsPage] = useState(1);
  const [appsError, setAppsError] = useState<unknown>(null);
  const [appsLoading, setAppsLoading] = useState(false);

  const [detail, setDetail] = useState<Application | null>(null);
  const [detailError, setDetailError] = useState<unknown>(null);

  const loadProfile = useCallback(async (activeToken: string) => {
    setProfileError(null);
    try {
      setProfile(await api.candidate.me(activeToken));
    } catch (cause) {
      setProfileError(cause);
    }
  }, []);

  const loadApplications = useCallback(async (activeToken: string, nextPage: number) => {
    setAppsLoading(true);
    setAppsError(null);
    try {
      setApplications(await api.candidate.myApplications(activeToken, nextPage, 10));
    } catch (cause) {
      setAppsError(cause);
    } finally {
      setAppsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    void loadProfile(token);
    void loadApplications(token, 1);
  }, [token, loadProfile, loadApplications]);

  useEffect(() => {
    if (!profile) return;
    setForm({
      full_name: profile.full_name,
      phone: profile.phone,
      headline: profile.headline,
      location: profile.location,
      skills: joinList(profile.skills),
      summary: profile.summary,
      resume_url: profile.resume_url,
    });
  }, [profile]);

  async function submitAuth(event: React.FormEvent) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthError(null);
    try {
      const response =
        mode === 'login'
          ? await api.candidate.login({
              email: credentials.email,
              password: credentials.password,
            })
          : await api.candidate.register({
              email: credentials.email,
              password: credentials.password,
              full_name: credentials.full_name,
              phone: credentials.phone,
            });
      const data = response.candidate;
      if (!data) throw new Error('The sign-in response did not include your profile.');
      onSession({ token: response.access, profile: data });
      setCredentials({ email: '', password: '', full_name: '', phone: '' });
    } catch (cause) {
      setAuthError(cause);
    } finally {
      setAuthBusy(false);
    }
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setProfileBusy(true);
    setProfileError(null);
    setProfileNote(null);
    try {
      const data = await api.candidate.updateMe(token, {
        full_name: form.full_name,
        phone: form.phone,
        headline: form.headline,
        location: form.location,
        skills: splitList(form.skills),
        summary: form.summary,
        resume_url: form.resume_url,
      });
      setProfile(data);
      onSession({ token, profile: data });
      setProfileNote('Profile saved.');
    } catch (cause) {
      setProfileError(cause);
    } finally {
      setProfileBusy(false);
    }
  }

  async function openApplication(id: string) {
    if (!token) return;
    setDetail(null);
    setDetailError(null);
    try {
      setDetail(await api.candidate.myApplication(token, id));
    } catch (cause) {
      setDetailError(cause);
    }
  }

  if (!session || !token) {
    return (
      <div className="authsplit">
        <section className="authcard">
          <div className="authcard__head">
            <h1 className="authcard__title">
              {mode === 'login' ? 'Job seeker sign in' : 'Create a job seeker account'}
            </h1>
            <p className="authcard__sub">
              {mode === 'login'
                ? 'Sign in to apply for roles and track your applications.'
                : 'One account for applying, saving your profile, and following every role.'}
            </p>
          </div>

          <div className="segmented" role="group" aria-label="Sign in or create an account">
            <button type="button" aria-pressed={mode === 'login'} onClick={() => setMode('login')}>
              Sign in
            </button>
            <button
              type="button"
              aria-pressed={mode === 'register'}
              onClick={() => setMode('register')}
            >
              Create account
            </button>
          </div>

          <form className="grid" onSubmit={submitAuth}>
            <Field label="Email" wide>
              <input
                className="input"
                type="email"
                autoComplete="username"
                required
                value={credentials.email}
                onChange={(event) => setCredentials({ ...credentials, email: event.target.value })}
              />
            </Field>
            <Field label="Password" hint="At least 8 characters." wide>
              <input
                className="input"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                minLength={8}
                value={credentials.password}
                onChange={(event) =>
                  setCredentials({ ...credentials, password: event.target.value })
                }
              />
            </Field>
            {mode === 'register' ? (
              <>
                <Field label="Your name" wide>
                  <input
                    className="input"
                    required
                    value={credentials.full_name}
                    onChange={(event) =>
                      setCredentials({ ...credentials, full_name: event.target.value })
                    }
                  />
                </Field>
                <Field label="Phone">
                  <input
                    className="input"
                    value={credentials.phone}
                    onChange={(event) =>
                      setCredentials({ ...credentials, phone: event.target.value })
                    }
                  />
                </Field>
              </>
            ) : null}
            <div className="grid__submit">
              <Button type="submit" busy={authBusy}>
                {mode === 'login' ? 'Sign in' : 'Create account'}
              </Button>
            </div>
          </form>
          <ErrorNote error={authError} plain />
        </section>

        <aside className="authside">
          <h2 className="authside__title">A profile that works for you</h2>
          <ul className="authside__list">
            <li>Keep your skills, headline, and resume in one place.</li>
            <li>Apply in a click and follow every application.</li>
            <li>Come back any time to see what moved.</li>
          </ul>
          <button type="button" className="link" onClick={onExplore}>
            Browse open roles first
          </button>
          <p className="authside__switch">
            Hiring instead?{' '}
            <a href="/employers" onClick={(event) => { event.preventDefault(); onEmployer(); }}>
              Go to the employer sign in
            </a>
          </p>
        </aside>
      </div>
    );
  }

  const totalPages = applications
    ? Math.max(1, Math.ceil(applications.total / applications.pageSize))
    : 1;

  return (
    <div className="portal">
      <header className="portal__head">
        <div>
          <h1 className="portal__title">Hello, {profile?.full_name ?? 'there'}</h1>
          <p className="portal__sub">
            {profile?.headline || 'Tell employers what you do best.'}
            {profile?.location ? ` · ${profile.location}` : ''}
          </p>
        </div>
        <div className="row">
          <Button variant="ghost" onClick={onExplore}>
            Find roles
          </Button>
          <Button variant="quiet" onClick={() => onSession(null)}>
            Sign out
          </Button>
        </div>
      </header>

      <section className="panel">
        <header className="panel__head">
          <div className="panel__intro">
            <h2 className="panel__title">Your profile</h2>
            <p className="panel__subtitle">{profile?.email}</p>
          </div>
        </header>
        <div className="panel__body">
          <form className="grid" onSubmit={saveProfile}>
            <Field label="Full name" wide>
              <input
                className="input"
                required
                value={form.full_name}
                onChange={(event) => setForm({ ...form, full_name: event.target.value })}
              />
            </Field>
            <Field label="Headline">
              <input
                className="input"
                maxLength={200}
                value={form.headline}
                onChange={(event) => setForm({ ...form, headline: event.target.value })}
                placeholder="Backend engineer"
              />
            </Field>
            <Field label="Where you live">
              <input
                className="input"
                maxLength={200}
                value={form.location}
                onChange={(event) => setForm({ ...form, location: event.target.value })}
                placeholder="Berlin"
              />
            </Field>
            <Field label="Phone">
              <input
                className="input"
                maxLength={50}
                value={form.phone}
                onChange={(event) => setForm({ ...form, phone: event.target.value })}
              />
            </Field>
            <Field label="Resume link" hint="A link to your resume or portfolio.">
              <input
                className="input"
                maxLength={500}
                value={form.resume_url}
                onChange={(event) => setForm({ ...form, resume_url: event.target.value })}
                placeholder="https://…"
              />
            </Field>
            <Field label="Skills" hint="Separate with commas." wide>
              <input
                className="input"
                value={form.skills}
                onChange={(event) => setForm({ ...form, skills: event.target.value })}
              />
            </Field>
            <Field label="About you" wide>
              <textarea
                className="input input--area"
                rows={4}
                value={form.summary}
                onChange={(event) => setForm({ ...form, summary: event.target.value })}
                placeholder="A short introduction employers will read."
              />
            </Field>
            <div className="grid__submit">
              <Button type="submit" busy={profileBusy}>
                Save profile
              </Button>
            </div>
          </form>
          <ErrorNote error={profileError} plain />
          {profileNote ? <p className="note note--ok">{profileNote}</p> : null}
        </div>
      </section>

      <section className="panel">
        <header className="panel__head">
          <div className="panel__intro">
            <h2 className="panel__title">Your applications</h2>
            <p className="panel__subtitle">Newest first. Open one to read the full record.</p>
          </div>
          <div className="panel__actions">
            <Button variant="ghost" onClick={() => void loadApplications(token, appsPage)}>
              Refresh
            </Button>
          </div>
        </header>
        <div className="panel__body">
          <ErrorNote error={appsError} plain />
          {appsLoading && !applications ? <p className="meta">Loading…</p> : null}
          {applications && applications.items.length === 0 ? (
            <Empty>
              No applications yet.{' '}
              <button type="button" className="link" onClick={onExplore}>
                Find a role
              </button>{' '}
              and apply.
            </Empty>
          ) : null}
          {applications && applications.items.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Company</th>
                  <th>Status</th>
                  <th>Applied</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {applications.items.map((application) => (
                  <tr
                    key={application.id}
                    className={detail?.id === application.id ? 'row--active' : undefined}
                  >
                    <td>{application.job_title_snapshot}</td>
                    <td>{application.company_snapshot}</td>
                    <td>
                      <Badge tone={statusTone(application.status)}>
                        {statusLabel(application.status)}
                      </Badge>
                    </td>
                    <td>{formatDate(application.applied_at)}</td>
                    <td>
                      <Button variant="quiet" onClick={() => void openApplication(application.id)}>
                        Open
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <div className="pager">
            <Button
              variant="ghost"
              disabled={appsPage <= 1 || appsLoading}
              onClick={() => {
                const next = appsPage - 1;
                setAppsPage(next);
                void loadApplications(token, next);
              }}
            >
              Previous
            </Button>
            <span className="pager__count">
              Page {appsPage} of {totalPages}
            </span>
            <Button
              variant="ghost"
              disabled={appsLoading || appsPage >= totalPages}
              onClick={() => {
                const next = appsPage + 1;
                setAppsPage(next);
                void loadApplications(token, next);
              }}
            >
              Next
            </Button>
          </div>
        </div>
      </section>

      {detail || detailError ? (
        <section className="panel">
          <header className="panel__head">
            <div className="panel__intro">
              <h2 className="panel__title">
                {detail ? detail.job_title_snapshot : 'Application'}
              </h2>
              <p className="panel__subtitle">
                {detail ? `${detail.company_snapshot} · applied ${formatDate(detail.applied_at)}` : null}
              </p>
            </div>
            {detail ? (
              <div className="panel__actions">
                <Badge tone={statusTone(detail.status)}>{statusLabel(detail.status)}</Badge>
              </div>
            ) : null}
          </header>
          <div className="panel__body">
            <ErrorNote error={detailError} plain />
            {detail ? (
              <>
                <h3 className="apply__title">Your cover letter</h3>
                <p className="prose">{detail.cover_letter || 'No cover letter.'}</p>
              </>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
