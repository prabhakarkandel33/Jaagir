import { Link } from 'react-router-dom';

import { Breakdown, PageHead, StatCard } from '../../components/portal';
import { Badge, Button, Empty, ErrorNote, Skeleton, statusLabel, statusTone } from '../../components/ui';
import { api } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';

export function RecruiterDashboard() {
  const { token, recruiter } = useSession();
  const activeToken = token ?? '';

  const jobs = useAsync(() => api.job.dashboard(activeToken), [activeToken]);
  const apps = useAsync(() => api.candidate.recruiterDashboard(activeToken), [activeToken]);

  const jobStats = jobs.data?.jobs.byStatus ?? {};
  const appStats = apps.data?.applications.byStatus ?? {};

  return (
    <div className="pstack">
      <PageHead
        title={`Welcome back, ${recruiter?.full_name.split(' ')[0] ?? 'there'}`}
        sub={recruiter?.company_name ? `Hiring at ${recruiter.company_name}.` : 'Your hiring desk.'}
        actions={
          <Link className="pbtn pbtn--primary" to="/employers/post">
            Post a role
          </Link>
        }
      />

      <section className="statgrid">
        <StatCard label="Roles" value={jobs.data?.jobs.total ?? '—'} note="All time" />
        <StatCard
          label="Live"
          value={jobStats.PUBLISHED ?? 0}
          note="Published now"
          tone="ok"
        />
        <StatCard label="Drafts" value={jobStats.DRAFT ?? 0} note="Not published yet" tone="warn" />
        <StatCard
          label="Applicants"
          value={apps.data?.applications.total ?? '—'}
          note={`${apps.data?.applications.newCount ?? 0} not reviewed`}
          tone="cand"
        />
      </section>

      <div className="twocol">
        <section className="pcard">
          <header className="pcard__head">
            <div>
              <h2 className="pcard__title">Applicant pipeline</h2>
              <p className="pcard__sub">Where everyone stands right now.</p>
            </div>
            <Link className="plink" to="/employers/applicants">
              See all
            </Link>
          </header>
          <div className="pcard__body">
            <ErrorNote error={apps.error} plain />
            {apps.loading && !apps.data ? <Skeleton lines={4} /> : null}
            {apps.data ? (
              <Breakdown
                byStatus={appStats}
                order={['SUBMITTED', 'IN_REVIEW', 'SHORTLISTED', 'ACCEPTED', 'REJECTED']}
                total={apps.data.applications.total}
              />
            ) : null}
          </div>
        </section>

        <section className="pcard">
          <header className="pcard__head">
            <div>
              <h2 className="pcard__title">Recent applicants</h2>
              <p className="pcard__sub">The newest people who applied.</p>
            </div>
            <Link className="plink" to="/employers/applicants">
              See all
            </Link>
          </header>
          <div className="pcard__body">
            <ErrorNote error={apps.error} plain />
            {apps.loading && !apps.data ? <Skeleton lines={4} /> : null}
            {apps.data && apps.data.recent.length === 0 ? (
              <Empty>No applications yet. Share a live role to start.</Empty>
            ) : null}
            {apps.data && apps.data.recent.length > 0 ? (
              <ul className="plist">
                {apps.data.recent.map((application) => (
                  <li key={application.id}>
                    <Link
                      className="plist__row"
                      to={`/employers/applicants/${application.id}`}
                    >
                      <span className="plist__main">
                        <strong>{application.candidate.full_name}</strong>
                        <span className="meta">
                          {application.job_title_snapshot} · {formatDate(application.applied_at)}
                        </span>
                      </span>
                      <Badge tone={statusTone(application.status)}>
                        {statusLabel(application.status)}
                      </Badge>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </section>
      </div>

      <section className="pcard">
        <header className="pcard__head">
          <div>
            <h2 className="pcard__title">Your latest roles</h2>
            <p className="pcard__sub">Open one to edit it or read its applicants.</p>
          </div>
          <Link className="plink" to="/employers/roles">
            All roles
          </Link>
        </header>
        <div className="pcard__body">
          <ErrorNote error={jobs.error} plain />
          {jobs.loading && !jobs.data ? <Skeleton lines={4} /> : null}
          {jobs.data && jobs.data.recentJobs.length === 0 ? (
            <Empty>
              No roles yet.{' '}
              <Link className="link" to="/employers/post">
                Post your first role
              </Link>
              .
            </Empty>
          ) : null}
          {jobs.data && jobs.data.recentJobs.length > 0 ? (
            <ul className="plist">
              {jobs.data.recentJobs.map((job) => (
                <li key={job.id}>
                  <Link className="plist__row" to={`/employers/roles/${job.id}`}>
                    <span className="plist__main">
                      <strong>{job.title}</strong>
                      <span className="meta">
                        {job.company} · {job.location || 'Anywhere'} · updated{' '}
                        {formatDate(job.updated_at)}
                      </span>
                    </span>
                    <Badge tone={statusTone(job.status)}>{statusLabel(job.status)}</Badge>
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="pcard__foot">
            <Button variant="ghost" onClick={jobs.reload}>
              Refresh
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
