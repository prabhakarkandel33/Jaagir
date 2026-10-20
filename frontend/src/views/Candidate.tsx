import { useCallback, useEffect, useState } from 'react';

import { Badge, Button, Empty, ErrorNote, Field, Panel, statusTone } from '../components/ui';
import { api } from '../lib/api';
import { formatDate, joinList, splitList } from '../lib/format';
import type { Application, Candidate as CandidateProfile, Page } from '../lib/types';

export type CandidateSession = { token: string; profile: CandidateProfile };

export function Candidate({
  session,
  onSession,
}: {
  session: CandidateSession | null;
  onSession: (session: CandidateSession | null) => void;
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
      if (!data) throw new Error('The auth response did not include the candidate profile.');
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
      <div className="split">
        <Panel
          title={mode === 'login' ? 'Candidate sign in' : 'Create a candidate account'}
          service="candidate"
          subtitle="Tokens are issued by the candidate service and verified locally."
          actions={
            <div className="segmented" role="group" aria-label="Auth mode">
              <button type="button" aria-pressed={mode === 'login'} onClick={() => setMode('login')}>
                Sign in
              </button>
              <button
                type="button"
                aria-pressed={mode === 'register'}
                onClick={() => setMode('register')}
              >
                Register
              </button>
            </div>
          }
        >
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
                <Field label="Full name" wide>
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
          <ErrorNote error={authError} />
        </Panel>

        <Panel title="What happens here" service="candidate">
          <ol className="steps">
            <li>Search reads the local replica, so it survives a Kafka outage.</li>
            <li>Apply writes one row; a unique index blocks a second application.</li>
            <li>History is paged, newest first.</li>
            <li>Each application stores the job title and company as a snapshot.</li>
          </ol>
        </Panel>
      </div>
    );
  }

  const totalPages = applications
    ? Math.max(1, Math.ceil(applications.total / applications.pageSize))
    : 1;

  return (
    <div className="stack">
      <Panel
        title="My profile"
        service="candidate"
        subtitle={profile?.email}
        actions={
          <div className="row">
            <Button variant="ghost" onClick={() => void loadProfile(token)}>
              Reload
            </Button>
            <Button variant="quiet" onClick={() => onSession(null)}>
              Sign out
            </Button>
          </div>
        }
      >
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
          <Field label="Location">
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
          <Field label="Resume URL">
            <input
              className="input"
              maxLength={500}
              value={form.resume_url}
              onChange={(event) => setForm({ ...form, resume_url: event.target.value })}
              placeholder="https://…"
            />
          </Field>
          <Field label="Skills" hint="Comma separated." wide>
            <input
              className="input"
              value={form.skills}
              onChange={(event) => setForm({ ...form, skills: event.target.value })}
            />
          </Field>
          <Field label="Summary" wide>
            <textarea
              className="input input--area"
              rows={4}
              value={form.summary}
              onChange={(event) => setForm({ ...form, summary: event.target.value })}
            />
          </Field>
          <div className="grid__submit">
            <Button type="submit" busy={profileBusy}>
              Save profile
            </Button>
          </div>
        </form>
        <ErrorNote error={profileError} />
        {profileNote ? <p className="note note--ok">{profileNote}</p> : null}
      </Panel>

      <Panel
        title="My applications"
        service="candidate"
        subtitle="Newest first. Select a row to read the full record."
        actions={
          <div className="row">
            <span className="mono meta">{applications?.total ?? 0} total</span>
            <Button variant="ghost" onClick={() => void loadApplications(token, appsPage)}>
              Reload
            </Button>
          </div>
        }
      >
        <ErrorNote error={appsError} />
        {appsLoading && !applications ? <p className="meta">Loading…</p> : null}
        {applications && applications.items.length === 0 ? (
          <Empty>No applications yet. Find a job in Discover and apply.</Empty>
        ) : null}
        {applications && applications.items.length > 0 ? (
          <table className="table">
            <thead>
              <tr>
                <th>Job</th>
                <th>Company</th>
                <th>Status</th>
                <th>Applied</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {applications.items.map((application) => (
                <tr key={application.id} className={detail?.id === application.id ? 'row--active' : undefined}>
                  <td>{application.job_title_snapshot}</td>
                  <td>{application.company_snapshot}</td>
                  <td>
                    <Badge tone={statusTone(application.status)}>{application.status}</Badge>
                  </td>
                  <td className="mono">{formatDate(application.applied_at)}</td>
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
          <span className="mono">
            {appsPage} / {totalPages}
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
      </Panel>

      {detail || detailError ? (
        <Panel title="Application detail" service="candidate">
          <ErrorNote error={detailError} />
          {detail ? (
            <>
              <dl className="facts">
                <div>
                  <dt>Application id</dt>
                  <dd className="mono">{detail.id}</dd>
                </div>
                <div>
                  <dt>Job id</dt>
                  <dd className="mono">{detail.job_id}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>
                    <Badge tone={statusTone(detail.status)}>{detail.status}</Badge>
                  </dd>
                </div>
                <div>
                  <dt>Applied</dt>
                  <dd>{formatDate(detail.applied_at)}</dd>
                </div>
                <div>
                  <dt>Status updated</dt>
                  <dd>{formatDate(detail.status_updated_at)}</dd>
                </div>
              </dl>
              <h3 className="apply__title">Cover letter</h3>
              <p className="prose">{detail.cover_letter || 'No cover letter.'}</p>
            </>
          ) : null}
        </Panel>
      ) : null}
    </div>
  );
}
