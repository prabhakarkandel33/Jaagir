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
  const [createNote, setCreateNote] = useState<string | null>(null);

  const [selected, setSelected] = useState<Job | null>(null);
  const [editForm, setEditForm] = useState<JobFormState>(EMPTY_JOB);
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState<unknown>(null);
  const [editNote, setEditNote] = useState<string | null>(null);

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
      setJobs(await api.job.listJobs(activeToken, nextPage, 10));
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
      if (!data) throw new Error('The sign-in response did not include your profile.');
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
      setProfileNote('Your profile is saved.');
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
    setCreateNote(null);
    try {
      const job = await api.job.createJob(token, toPayload(createForm));
      setCreateForm(EMPTY_JOB);
      setJobsPage(1);
      await loadJobs(token, 1);
      setSelected(job);
      setEditForm(toForm(job));
      setCreateNote('Role saved as a draft. Publish it when you are ready.');
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
    setEditNote(null);
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
    setEditNote(null);
    try {
      const job = await api.job.updateJob(token, selected.id, toPayload(editForm));
      setSelected(job);
      setEditForm(toForm(job));
      await loadJobs(token, jobsPage);
      setEditNote('Changes saved.');
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
    setEditNote(null);
    try {
      const job =
        action === 'publish'
          ? await api.job.publishJob(token, selected.id)
          : await api.job.closeJob(token, selected.id);
      setSelected(job);
      setEditForm(toForm(job));
      await loadJobs(token, jobsPage);
      setEditNote(action === 'publish' ? 'Role is live.' : 'Role is closed.');
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
      <div className="authsplit">
        <section className="authcard">
          <div className="authcard__head">
            <h1 className="authcard__title">
              {mode === 'login' ? 'Employer sign in' : 'Start hiring on Jaagir'}
            </h1>
            <p className="authcard__sub">
              {mode === 'login'
                ? 'Sign in to manage your roles and read applicants.'
                : 'Create an account, post a role, and start meeting candidates.'}
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
            <Field label="Work email" wide>
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
          <ErrorNote error={authError} plain />
        </section>

        <aside className="authside">
          <h2 className="authside__title">Hire without the busywork</h2>
          <ul className="authside__list">
            <li>Write a role once and publish it with one click.</li>
            <li>See every applicant in a single list.</li>
            <li>Keep your company profile up to date.</li>
          </ul>
        </aside>
      </div>
    );
  }

  const totalPages = jobs ? Math.max(1, Math.ceil(jobs.total / jobs.pageSize)) : 1;
  const live = jobs?.items.filter((job) => job.status === 'PUBLISHED').length ?? 0;

  return (
    <div className="portal">
      <header className="portal__head">
        <div>
          <h1 className="portal__title">Hello, {profile?.full_name ?? 'there'}</h1>
          <p className="portal__sub">
            {profile?.company_name ? `${profile.company_name} · ` : ''}
            {jobs?.total ?? 0} {jobs?.total === 1 ? 'role' : 'roles'} · {live} live
          </p>
        </div>
        <div className="row">
          <Button variant="ghost" onClick={() => onSession(null)}>
            Sign out
          </Button>
        </div>
      </header>

      <section className="panel">
        <header className="panel__head">
          <div className="panel__intro">
            <h2 className="panel__title">Company profile</h2>
            <p className="panel__subtitle">Candidates see this name and company on your roles.</p>
          </div>
        </header>
        <div className="panel__body">
          <form className="grid" onSubmit={saveProfile}>
            <Field label="Your name">
              <input
                className="input"
                required
                maxLength={200}
                value={profileForm.full_name}
                onChange={(event) =>
                  setProfileForm({ ...profileForm, full_name: event.target.value })
                }
              />
            </Field>
            <Field label="Company">
              <input
                className="input"
                maxLength={200}
                value={profileForm.company_name}
                onChange={(event) =>
                  setProfileForm({ ...profileForm, company_name: event.target.value })
                }
              />
            </Field>
            <Field label="Phone">
              <input
                className="input"
                maxLength={50}
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
          <ErrorNote error={profileError} plain />
          {profileNote ? <p className="note note--ok">{profileNote}</p> : null}
        </div>
      </section>

      <section className="panel">
        <header className="panel__head">
          <div className="panel__intro">
            <h2 className="panel__title">Post a role</h2>
            <p className="panel__subtitle">Save it as a draft first. Publish when it is ready.</p>
          </div>
        </header>
        <div className="panel__body">
          <form className="grid" onSubmit={createJob}>
            <Field label="Role title" wide>
              <input
                className="input"
                required
                maxLength={200}
                placeholder="Senior Backend Engineer"
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
                placeholder="Remote, Berlin…"
                value={createForm.location}
                onChange={(event) => setCreateForm({ ...createForm, location: event.target.value })}
              />
            </Field>
            <Field label="Type of work">
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
            <Field label="Skills" hint="Separate with commas.">
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
                placeholder="What the person will do, who they will work with, and what you look for."
                value={createForm.description}
                onChange={(event) =>
                  setCreateForm({ ...createForm, description: event.target.value })
                }
              />
            </Field>
            <div className="grid__submit">
              <Button type="submit" busy={createBusy}>
                Save draft
              </Button>
            </div>
          </form>
          <ErrorNote error={createError} plain />
          {createNote ? <p className="note note--ok">{createNote}</p> : null}
        </div>
      </section>

      <section className="panel">
        <header className="panel__head">
          <div className="panel__intro">
            <h2 className="panel__title">Your roles</h2>
            <p className="panel__subtitle">Only you can see and edit these roles.</p>
          </div>
          <div className="panel__actions">
            <Button variant="ghost" onClick={() => void loadJobs(token, jobsPage)}>
              Refresh
            </Button>
          </div>
        </header>
        <div className="panel__body">
          <ErrorNote error={jobsError} plain />
          {jobsLoading && !jobs ? <p className="meta">Loading…</p> : null}
          {jobs && jobs.items.length === 0 ? (
            <Empty>No roles yet. Post your first role above.</Empty>
          ) : null}
          {jobs && jobs.items.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Status</th>
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
                      <Badge tone={statusTone(job.status)}>{statusLabel(job.status)}</Badge>
                    </td>
                    <td>{formatDate(job.updated_at)}</td>
                    <td>
                      <Button variant="quiet" onClick={() => void loadApplications(job.id)}>
                        Applicants
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
            <span className="pager__count">
              Page {jobsPage} of {totalPages}
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
        </div>
      </section>

      {selected ? (
        <section className="panel">
          <header className="panel__head">
            <div className="panel__intro">
              <h2 className="panel__title">{selected.title}</h2>
              <p className="panel__subtitle">
                {statusLabel(selected.status)} · posted {formatDate(selected.published_at)}
              </p>
            </div>
            <div className="panel__actions">
              <Badge tone={statusTone(selected.status)}>{statusLabel(selected.status)}</Badge>
            </div>
          </header>
          <div className="panel__body">
            <form className="grid" onSubmit={saveJob}>
              <Field label="Role title" wide>
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
              <Field label="Type of work">
                <select
                  className="input"
                  value={editForm.employment_type}
                  onChange={(event) =>
                    setEditForm({
                      ...editForm,
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
              <Field label="Skills" hint="Separate with commas.">
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
                <Button
                  variant="ghost"
                  disabled={selected.status !== 'DRAFT'}
                  onClick={() => void transition('publish')}
                >
                  Publish
                </Button>
                <Button
                  variant="danger"
                  disabled={selected.status === 'CLOSED'}
                  onClick={() => void transition('close')}
                >
                  Close role
                </Button>
              </div>
            </form>
            <ErrorNote error={editError} plain />
            {editNote ? <p className="note note--ok">{editNote}</p> : null}
          </div>
        </section>
      ) : null}

      {appsJobId ? (
        <section className="panel">
          <header className="panel__head">
            <div className="panel__intro">
              <h2 className="panel__title">Applicants</h2>
              <p className="panel__subtitle">
                {apps?.total ?? 0} {apps?.total === 1 ? 'person has' : 'people have'} applied.
              </p>
            </div>
            <div className="panel__actions">
              <Button variant="ghost" onClick={() => void loadApplications(appsJobId)}>
                Refresh
              </Button>
            </div>
          </header>
          <div className="panel__body">
            <ErrorNote error={appsError} plain />
            {appsLoading ? <p className="meta">Loading…</p> : null}
            {apps && apps.items.length === 0 ? (
              <Empty>No applications for this role yet.</Empty>
            ) : null}
            {apps && apps.items.length > 0 ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Applied</th>
                    <th>Status</th>
                    <th>Cover letter</th>
                  </tr>
                </thead>
                <tbody>
                  {apps.items.map((application) => (
                    <tr key={application.id}>
                      <td>{formatDate(application.applied_at)}</td>
                      <td>
                        <Badge tone={statusTone(application.status)}>
                          {statusLabel(application.status)}
                        </Badge>
                      </td>
                      <td className="prose prose--small">
                        {application.cover_letter || (
                          <span className="meta">No cover letter</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
