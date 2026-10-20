import { useCallback, useEffect, useState } from 'react';

import { Badge, Button, Empty, ErrorNote, Field, Panel, statusTone } from '../components/ui';
import { api } from '../lib/api';
import { formatDate, joinList, splitList } from '../lib/format';
import {
  EMPLOYMENT_LABELS,
  EMPLOYMENT_TYPES,
  type Application,
  type EmploymentType,
  type Job,
  type Page,
  type Recruiter as RecruiterProfile,
} from '../lib/types';

export type RecruiterSession = { token: string; profile: RecruiterProfile };

type JobFormState = {
  title: string;
  description: string;
  company: string;
  location: string;
  employment_type: EmploymentType;
  skills: string;
};

const EMPTY_JOB: JobFormState = {
  title: '',
  description: '',
  company: '',
  location: '',
  employment_type: 'FULL_TIME',
  skills: '',
};

function toForm(job: Job): JobFormState {
  return {
    title: job.title,
    description: job.description,
    company: job.company,
    location: job.location,
    employment_type: job.employment_type,
    skills: joinList(job.skills),
  };
}

function toPayload(form: JobFormState) {
  return {
    title: form.title,
    description: form.description,
    company: form.company,
    location: form.location,
    employment_type: form.employment_type,
    skills: splitList(form.skills),
  };
}

export function Recruiter({
  session,
  onSession,
}: {
  session: RecruiterSession | null;
  onSession: (session: RecruiterSession | null) => void;
}) {
  const token = session?.token ?? null;

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [credentials, setCredentials] = useState({
    email: '',
    password: '',
    full_name: '',
    company_name: '',
    phone: '',
  });
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<unknown>(null);

  const [profile, setProfile] = useState<RecruiterProfile | null>(session?.profile ?? null);
  const [profileForm, setProfileForm] = useState({ full_name: '', company_name: '', phone: '' });
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState<unknown>(null);
  const [profileNote, setProfileNote] = useState<string | null>(null);

  const [jobs, setJobs] = useState<Page<Job> | null>(null);
  const [jobsPage, setJobsPage] = useState(1);
  const [jobsError, setJobsError] = useState<unknown>(null);
  const [jobsLoading, setJobsLoading] = useState(false);

  const [createForm, setCreateForm] = useState<JobFormState>(EMPTY_JOB);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState<unknown>(null);

  const [selected, setSelected] = useState<Job | null>(null);
  const [editForm, setEditForm] = useState<JobFormState>(EMPTY_JOB);
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState<unknown>(null);

  const [apps, setApps] = useState<Page<Application> | null>(null);
  const [appsJobId, setAppsJobId] = useState<string | null>(null);
  const [appsError, setAppsError] = useState<unknown>(null);
  const [appsLoading, setAppsLoading] = useState(false);

  const loadProfile = useCallback(async (activeToken: string) => {
    setProfileError(null);
    try {
      const data = await api.job.me(activeToken);
      setProfile(data);
      setProfileForm({
        full_name: data.full_name,
        company_name: data.company_name,
        phone: data.phone,
      });
    } catch (cause) {
      setProfileError(cause);
    }
  }, []);

  const loadJobs = useCallback(async (activeToken: string, nextPage: number) => {
    setJobsLoading(true);
    setJobsError(null);
    try {
      const data = await api.job.listJobs(activeToken, nextPage, 10);
      setJobs(data);
    } catch (cause) {
      setJobsError(cause);
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    void loadProfile(token);
    void loadJobs(token, 1);
  }, [token, loadProfile, loadJobs]);

  useEffect(() => {
    if (profile) {
      setProfileForm({
        full_name: profile.full_name,
        company_name: profile.company_name,
        phone: profile.phone,
      });
    }
  }, [profile]);

  async function submitAuth(event: React.FormEvent) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthError(null);
    try {
      const response =
        mode === 'login'
          ? await api.job.loginRecruiter({
              email: credentials.email,
              password: credentials.password,
            })
          : await api.job.registerRecruiter({
              email: credentials.email,
              password: credentials.password,
              full_name: credentials.full_name,
              company_name: credentials.company_name,
              phone: credentials.phone,
            });
      const data = response.recruiter;
      if (!data) throw new Error('The auth response did not include the recruiter profile.');
      onSession({ token: response.access, profile: data });
      setCredentials({ email: '', password: '', full_name: '', company_name: '', phone: '' });
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
      const data = await api.job.updateMe(token, profileForm);
      setProfile(data);
      onSession({ token, profile: data });
      setProfileNote('Profile saved.');
    } catch (cause) {
      setProfileError(cause);
    } finally {
      setProfileBusy(false);
    }
  }

  async function createJob(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setCreateBusy(true);
    setCreateError(null);
    try {
      const job = await api.job.createJob(token, toPayload(createForm));
      setCreateForm(EMPTY_JOB);
      setJobsPage(1);
      await loadJobs(token, 1);
      setSelected(job);
      setEditForm(toForm(job));
    } catch (cause) {
      setCreateError(cause);
    } finally {
      setCreateBusy(false);
    }
  }

  async function selectJob(job: Job) {
    setSelected(job);
    setEditForm(toForm(job));
    setEditError(null);
    setApps(null);
    setAppsJobId(null);
    setAppsError(null);
    if (!token) return;
    try {
      const fresh = await api.job.getJob(token, job.id);
      setSelected(fresh);
      setEditForm(toForm(fresh));
    } catch (cause) {
      setEditError(cause);
    }
  }

  async function saveJob(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !selected) return;
    setEditBusy(true);
    setEditError(null);
    try {
      const job = await api.job.updateJob(token, selected.id, toPayload(editForm));
      setSelected(job);
      setEditForm(toForm(job));
      await loadJobs(token, jobsPage);
    } catch (cause) {
      setEditError(cause);
    } finally {
      setEditBusy(false);
    }
  }

  async function transition(action: 'publish' | 'close') {
    if (!token || !selected) return;
    setEditBusy(true);
    setEditError(null);
    try {
      const job =
        action === 'publish'
          ? await api.job.publishJob(token, selected.id)
          : await api.job.closeJob(token, selected.id);
      setSelected(job);
      setEditForm(toForm(job));
      await loadJobs(token, jobsPage);
    } catch (cause) {
      setEditError(cause);
    } finally {
      setEditBusy(false);
    }
  }

  async function loadApplications(jobId: string) {
    if (!token) return;
    setAppsLoading(true);
    setAppsError(null);
    setAppsJobId(jobId);
    try {
      setApps(await api.candidate.jobApplications(token, jobId, 1, 10));
    } catch (cause) {
      setAppsError(cause);
      setApps(null);
    } finally {
      setAppsLoading(false);
    }
  }

  if (!session || !token) {
    return (
      <div className="split">
        <Panel
          title={mode === 'login' ? 'Recruiter sign in' : 'Create a recruiter account'}
          service="job"
          subtitle="Auth routes are throttled at 10 requests per minute."
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
                <Field label="Company">
                  <input
                    className="input"
                    value={credentials.company_name}
                    onChange={(event) =>
                      setCredentials({ ...credentials, company_name: event.target.value })
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

        <Panel title="What happens here" service="both">
          <ol className="steps">
            <li>The job service checks the password with argon2id and signs an ES256 token.</li>
            <li>The token carries the claims sub, role=recruiter and iss=job-service.</li>
            <li>The candidate service accepts the same token with the published key.</li>
            <li>Any write to a published job adds an outbox row in the same transaction.</li>
          </ol>
        </Panel>
      </div>
    );
  }

  const totalPages = jobs ? Math.max(1, Math.ceil(jobs.total / jobs.pageSize)) : 1;

  return (
    <div className="stack">
      <Panel
        title="Recruiter profile"
        service="job"
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
              value={profileForm.full_name}
              onChange={(event) =>
                setProfileForm({ ...profileForm, full_name: event.target.value })
              }
            />
          </Field>
          <Field label="Company">
            <input
              className="input"
              value={profileForm.company_name}
              onChange={(event) =>
                setProfileForm({ ...profileForm, company_name: event.target.value })
              }
            />
          </Field>
          <Field label="Phone">
            <input
              className="input"
              value={profileForm.phone}
              onChange={(event) => setProfileForm({ ...profileForm, phone: event.target.value })}
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
        {profile ? (
          <p className="meta">
            id <span className="mono">{profile.id}</span> · created {formatDate(profile.created_at)}
          </p>
        ) : null}
      </Panel>

      <Panel title="New job" service="job" subtitle="Creates a DRAFT. No event is emitted yet.">
        <form className="grid" onSubmit={createJob}>
          <Field label="Title" wide>
            <input
              className="input"
              required
              maxLength={200}
              value={createForm.title}
              onChange={(event) => setCreateForm({ ...createForm, title: event.target.value })}
            />
          </Field>
          <Field label="Company">
            <input
              className="input"
              required
              maxLength={200}
              value={createForm.company}
              onChange={(event) => setCreateForm({ ...createForm, company: event.target.value })}
            />
          </Field>
          <Field label="Location">
            <input
              className="input"
              maxLength={200}
              value={createForm.location}
              onChange={(event) => setCreateForm({ ...createForm, location: event.target.value })}
            />
          </Field>
          <Field label="Employment type">
            <select
              className="input"
              value={createForm.employment_type}
              onChange={(event) =>
                setCreateForm({
                  ...createForm,
                  employment_type: event.target.value as EmploymentType,
                })
              }
            >
              {EMPLOYMENT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {EMPLOYMENT_LABELS[type]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Skills" hint="Comma separated.">
            <input
              className="input"
              value={createForm.skills}
              onChange={(event) => setCreateForm({ ...createForm, skills: event.target.value })}
            />
          </Field>
          <Field label="Description" wide>
            <textarea
              className="input input--area"
              rows={5}
              required
              value={createForm.description}
              onChange={(event) =>
                setCreateForm({ ...createForm, description: event.target.value })
              }
            />
          </Field>
          <div className="grid__submit">
            <Button type="submit" busy={createBusy}>
              Create draft
            </Button>
          </div>
        </form>
        <ErrorNote error={createError} />
      </Panel>

      <Panel
        title="My jobs"
        service="job"
        subtitle="Scoped to this recruiter; another recruiter's job id returns 404."
        actions={
          <div className="row">
            <span className="mono meta">{jobs?.total ?? 0} total</span>
            <Button variant="ghost" onClick={() => void loadJobs(token, jobsPage)}>
              Reload
            </Button>
          </div>
        }
      >
        <ErrorNote error={jobsError} />
        {jobsLoading && !jobs ? <p className="meta">Loading…</p> : null}
        {jobs && jobs.items.length === 0 ? <Empty>No jobs yet. Create a draft above.</Empty> : null}
        {jobs && jobs.items.length > 0 ? (
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Version</th>
                <th>Updated</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {jobs.items.map((job) => (
                <tr key={job.id} className={selected?.id === job.id ? 'row--active' : undefined}>
                  <td>
                    <button type="button" className="link" onClick={() => void selectJob(job)}>
                      {job.title}
                    </button>
                    <span className="meta block">{job.company}</span>
                  </td>
                  <td>
                    <Badge tone={statusTone(job.status)}>{job.status}</Badge>
                  </td>
                  <td className="mono">v{job.version}</td>
                  <td className="mono">{formatDate(job.updated_at)}</td>
                  <td>
                    <Button variant="quiet" onClick={() => void loadApplications(job.id)}>
                      Applications
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
            disabled={jobsPage <= 1 || jobsLoading}
            onClick={() => {
              const next = jobsPage - 1;
              setJobsPage(next);
              void loadJobs(token, next);
            }}
          >
            Previous
          </Button>
          <span className="mono">
            {jobsPage} / {totalPages}
          </span>
          <Button
            variant="ghost"
            disabled={jobsLoading || jobsPage >= totalPages}
            onClick={() => {
              const next = jobsPage + 1;
              setJobsPage(next);
              void loadJobs(token, next);
            }}
          >
            Next
          </Button>
        </div>
      </Panel>

      {selected ? (
        <Panel
          title={`Edit: ${selected.title}`}
          service="job"
          subtitle="Every write bumps the version. Publish and close are the only status changes."
          actions={
            <div className="row">
              <Badge tone={statusTone(selected.status)}>{selected.status}</Badge>
              <Badge tone="job">v{selected.version}</Badge>
            </div>
          }
        >
          <form className="grid" onSubmit={saveJob}>
            <Field label="Title" wide>
              <input
                className="input"
                required
                maxLength={200}
                value={editForm.title}
                onChange={(event) => setEditForm({ ...editForm, title: event.target.value })}
              />
            </Field>
            <Field label="Company">
              <input
                className="input"
                required
                maxLength={200}
                value={editForm.company}
                onChange={(event) => setEditForm({ ...editForm, company: event.target.value })}
              />
            </Field>
            <Field label="Location">
              <input
                className="input"
                maxLength={200}
                value={editForm.location}
                onChange={(event) => setEditForm({ ...editForm, location: event.target.value })}
              />
            </Field>
            <Field label="Employment type">
              <select
                className="input"
                value={editForm.employment_type}
                onChange={(event) =>
                  setEditForm({ ...editForm, employment_type: event.target.value as EmploymentType })
                }
              >
                {EMPLOYMENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {EMPLOYMENT_LABELS[type]}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Skills" hint="Comma separated.">
              <input
                className="input"
                value={editForm.skills}
                onChange={(event) => setEditForm({ ...editForm, skills: event.target.value })}
              />
            </Field>
            <Field label="Description" wide>
              <textarea
                className="input input--area"
                rows={6}
                required
                value={editForm.description}
                onChange={(event) => setEditForm({ ...editForm, description: event.target.value })}
              />
            </Field>
            <div className="grid__submit row">
              <Button type="submit" busy={editBusy}>
                Save changes
              </Button>
              <Button variant="ghost" busy={editBusy} onClick={() => void transition('publish')}>
                Publish
              </Button>
              <Button variant="danger" busy={editBusy} onClick={() => void transition('close')}>
                Close
              </Button>
            </div>
          </form>
          <ErrorNote error={editError} />
          <dl className="facts">
            <div>
              <dt>Job id</dt>
              <dd className="mono">{selected.id}</dd>
            </div>
            <div>
              <dt>Published</dt>
              <dd>{formatDate(selected.published_at)}</dd>
            </div>
            <div>
              <dt>Closed</dt>
              <dd>{formatDate(selected.closed_at)}</dd>
            </div>
          </dl>
        </Panel>
      ) : null}

      {appsJobId ? (
        <Panel
          title="Applications"
          service="candidate"
          subtitle={
            <>
              Job <span className="mono">{appsJobId}</span> · read through the candidate service with
              the recruiter token.
            </>
          }
          actions={
            <Button variant="ghost" onClick={() => void loadApplications(appsJobId)}>
              Reload
            </Button>
          }
        >
          <ErrorNote error={appsError} />
          {appsLoading ? <p className="meta">Loading…</p> : null}
          {apps && apps.items.length === 0 ? <Empty>No applications for this job yet.</Empty> : null}
          {apps && apps.items.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Applied</th>
                  <th>Status</th>
                  <th>Candidate note</th>
                  <th>Application</th>
                </tr>
              </thead>
              <tbody>
                {apps.items.map((application) => (
                  <tr key={application.id}>
                    <td className="mono">{formatDate(application.applied_at)}</td>
                    <td>
                      <Badge tone={statusTone(application.status)}>{application.status}</Badge>
                    </td>
                    <td className="prose prose--small">
                      {application.cover_letter || <span className="meta">no cover letter</span>}
                    </td>
                    <td className="mono">{application.id.slice(0, 8)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <p className="meta">{apps?.total ?? 0} application(s) total</p>
        </Panel>
      ) : null}
    </div>
  );
}
