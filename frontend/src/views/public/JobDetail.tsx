import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Badge, Button, ErrorNote, Field, Skeleton } from '../../components/ui';
import { api } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { useSession } from '../../lib/session';
import { EMPLOYMENT_LABELS, type Job } from '../../lib/types';

export function JobDetail() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { session, candidate, recruiter, signOut } = useSession();

  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const [coverLetter, setCoverLetter] = useState('');
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<unknown>(null);
  const [appliedNote, setAppliedNote] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.candidate
      .getJob(id)
      .then((data) => {
        if (!cancelled) setJob(data);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function apply() {
    if (!job || !session || session.role !== 'candidate') return;
    setApplying(true);
    setApplyError(null);
    try {
      await api.candidate.apply(session.access, job.id, coverLetter);
      setAppliedNote(true);
      setCoverLetter('');
    } catch (cause) {
      setApplyError(cause);
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="jobpage">
      <button type="button" className="link" onClick={() => navigate('/jobs')}>
        ← Back to search
      </button>

      {loading ? <Skeleton lines={6} /> : null}
      <ErrorNote error={error} plain />

      {!loading && !job && !error ? (
        <p className="empty">This role is not available.</p>
      ) : null}

      {job ? (
        <article className="jobpage__card">
          <header className="jobpage__head">
            <div>
              <h1 className="jobpage__title">{job.title}</h1>
              <p className="jobpage__meta">
                {job.company} · {job.location || 'Anywhere'} · posted{' '}
                {formatDate(job.published_at)}
              </p>
            </div>
            <Badge tone="muted">{EMPLOYMENT_LABELS[job.employment_type]}</Badge>
          </header>

          {job.skills.length > 0 ? (
            <div className="row row--wrap">
              {job.skills.map((skill) => (
                <Badge key={skill} tone="muted">
                  {skill}
                </Badge>
              ))}
            </div>
          ) : null}

          <p className="prose">{job.description}</p>

          <section className="apply">
            <h2 className="apply__title">Apply for this role</h2>

            {appliedNote ? (
              <p className="note note--ok">
                Application sent. You can follow it under My applications.
              </p>
            ) : null}

            {session?.role === 'candidate' ? (
              <>
                <p className="meta">Applying as {candidate?.full_name ?? 'you'}.</p>
                <Field label="Cover letter" hint="Optional." wide>
                  <textarea
                    className="input input--area"
                    rows={4}
                    value={coverLetter}
                    onChange={(event) => setCoverLetter(event.target.value)}
                    placeholder="Tell them why this role fits you."
                  />
                </Field>
                <div className="row">
                  <Button busy={applying} onClick={() => void apply()}>
                    Send application
                  </Button>
                </div>
                <ErrorNote error={applyError} plain />
              </>
            ) : null}

            {session?.role === 'recruiter' ? (
              <div className="apply__signin">
                <p>
                  You are signed in as an employer, {recruiter?.full_name ?? 'there'}. Sign out to
                  apply as a job seeker.
                </p>
                <div className="row">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      signOut();
                    }}
                  >
                    Sign out
                  </Button>
                </div>
              </div>
            ) : null}

            {!session ? (
              <div className="apply__signin">
                <p>Sign in to apply. Your profile goes with the application.</p>
                <Button onClick={() => navigate(`/me?next=${encodeURIComponent(`/jobs/${id}`)}`)}>
                  Sign in or create an account
                </Button>
              </div>
            ) : null}
          </section>

          <p className="jobpage__foot">
            Not for you? <Link to="/jobs">See more open roles</Link>
          </p>
        </article>
      ) : null}
    </div>
  );
}
