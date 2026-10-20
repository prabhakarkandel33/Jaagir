import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Breakdown, PageHead, StatCard } from '../../components/portal';
import { Badge, Empty, ErrorNote, Skeleton, statusLabel, statusTone } from '../../components/ui';
import { api } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';

const CV_REMINDER_KEY = 'jp.cvReminder';

export function CandidateDashboard() {
  const { token, candidate } = useSession();
  const activeToken = token ?? '';

  const dashboard = useAsync(() => api.candidate.dashboard(activeToken), [activeToken]);
  const roles = useAsync(() => api.candidate.searchJobs({ page: 1, pageSize: 3 }), []);

  const stats = dashboard.data?.applications.byStatus ?? {};
  const [cvReminderHidden, setCvReminderHidden] = useState(() => {
    try {
      return window.localStorage.getItem(CV_REMINDER_KEY) === 'hidden';
    } catch {
      return false;
    }
  });
  const showCvReminder = Boolean(candidate && !candidate.has_resume && !cvReminderHidden);

  function hideCvReminder() {
    setCvReminderHidden(true);
    try {
      window.localStorage.setItem(CV_REMINDER_KEY, 'hidden');
    } catch {
      return;
    }
  }

  const applicationsCard = (
    <section className="pcard">
      <header className="pcard__head">
        <div>
          <h2 className="pcard__title">Your applications</h2>
          <p className="pcard__sub">Where each one stands.</p>
        </div>
        <Link className="plink" to="/me/applications">
          See all
        </Link>
      </header>
      <div className="pcard__body">
        <ErrorNote error={dashboard.error} plain />
        {dashboard.loading && !dashboard.data ? <Skeleton lines={4} /> : null}
        {dashboard.data ? (
          <Breakdown
            byStatus={stats}
            order={['SUBMITTED', 'IN_REVIEW', 'SHORTLISTED', 'ACCEPTED', 'REJECTED']}
            total={dashboard.data.applications.total}
          />
        ) : null}
      </div>
    </section>
  );

  return (
    <div className="pstack">
      <PageHead
        title={`Hello, ${candidate?.full_name.split(' ')[0] ?? 'there'}`}
        sub={candidate?.headline || 'Tell employers what you do best.'}
        actions={
          <Link className="pbtn pbtn--primary" to="/jobs">
            Find roles
          </Link>
        }
      />

      <section className="statgrid">
        <StatCard
          label="Applications"
          value={dashboard.data?.applications.total ?? '—'}
          note="All time"
        />
        <StatCard
          label="In review"
          value={stats.IN_REVIEW ?? 0}
          note="An employer is reading"
          tone="warn"
        />
        <StatCard
          label="Shortlisted"
          value={stats.SHORTLISTED ?? 0}
          note="You moved forward"
          tone="cand"
        />
        <StatCard
          label="Accepted"
          value={stats.ACCEPTED ?? 0}
          note="Offers"
          tone="ok"
        />
      </section>

      {showCvReminder ? (
        <div className="twocol">
          <section className="cvmemo">
            <span className="cvmemo__mark" aria-hidden="true">
              PDF
            </span>
            <div className="cvmemo__text">
              <h2 className="cvmemo__title">Add your CV when you are ready</h2>
              <p>
                A CV lets employers see your full history. Your profile works without one, so
                there is no rush.
              </p>
            </div>
            <div className="cvmemo__actions">
              <Link className="pbtn pbtn--primary" to="/me/profile">
                Upload CV
              </Link>
              <button type="button" className="plink" onClick={hideCvReminder}>
                Do not remind me
              </button>
            </div>
          </section>
          {applicationsCard}
        </div>
      ) : (
        applicationsCard
      )}

      <section className="pcard">
        <header className="pcard__head">
          <div>
            <h2 className="pcard__title">Recent applications</h2>
            <p className="pcard__sub">The five newest.</p>
          </div>
          <Link className="plink" to="/me/applications">
            See all
          </Link>
        </header>
        <div className="pcard__body">
          {dashboard.data && dashboard.data.recent.length === 0 ? (
            <Empty>
              No applications yet.{' '}
              <Link className="link" to="/jobs">
                Find a role
              </Link>{' '}
              and apply.
            </Empty>
          ) : null}
          {dashboard.data && dashboard.data.recent.length > 0 ? (
            <ul className="plist">
              {dashboard.data.recent.map((application) => (
                <li key={application.id}>
                  <Link className="plist__row" to={`/me/applications/${application.id}`}>
                    <span className="plist__main">
                      <strong>{application.job_title_snapshot}</strong>
                      <span className="meta">
                        {application.company_snapshot} · applied{' '}
                        {formatDate(application.applied_at)}
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

      <section className="pcard">
        <header className="pcard__head">
          <div>
            <h2 className="pcard__title">Roles for you</h2>
            <p className="pcard__sub">A few roles that are open right now.</p>
          </div>
          <Link className="plink" to="/jobs">
            Search all
          </Link>
        </header>
        <div className="pcard__body">
          <ErrorNote error={roles.error} plain />
          {roles.loading && !roles.data ? <Skeleton lines={3} /> : null}
          {roles.data && roles.data.items.length > 0 ? (
            <ul className="plist">
              {roles.data.items.map((hit) => (
                <li key={hit.id}>
                  <Link className="plist__row" to={`/jobs/${hit.id}`}>
                    <span className="plist__main">
                      <strong>{hit.title}</strong>
                      <span className="meta">
                        {hit.company} · {hit.location || 'Anywhere'}
                      </span>
                    </span>
                    <span className="plink">View role</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </section>
    </div>
  );
}
