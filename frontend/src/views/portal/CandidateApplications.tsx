import { useState } from 'react';
import { Link } from 'react-router-dom';

import { PageHead } from '../../components/portal';
import { Badge, Button, Empty, ErrorNote, Skeleton, statusLabel, statusTone } from '../../components/ui';
import { api } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';

export function CandidateApplications() {
  const { token } = useSession();
  const activeToken = token ?? '';
  const [page, setPage] = useState(1);
  const apps = useAsync(() => api.candidate.myApplications(activeToken, page, 20), [
    activeToken,
    page,
  ]);

  const totalPages = apps.data ? Math.max(1, Math.ceil(apps.data.total / apps.data.pageSize)) : 1;

  return (
    <div className="pstack">
      <PageHead
        title="My applications"
        sub="Newest first. Open one to read the full record."
        actions={
          <Link className="pbtn pbtn--primary" to="/jobs">
            Find roles
          </Link>
        }
      />

      <section className="pcard">
        <div className="pcard__body">
          <ErrorNote error={apps.error} plain />
          {apps.loading && !apps.data ? <Skeleton lines={6} /> : null}
          {apps.data && apps.data.items.length === 0 ? (
            <Empty>
              No applications yet.{' '}
              <Link className="link" to="/jobs">
                Find a role
              </Link>{' '}
              and apply.
            </Empty>
          ) : null}

          {apps.data && apps.data.items.length > 0 ? (
            <div className="ptable-wrap">
              <table className="ptable">
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
                  {apps.data.items.map((application) => (
                    <tr key={application.id}>
                      <td data-label="Role">
                        <Link
                          className="plink plink--strong"
                          to={`/me/applications/${application.id}`}
                        >
                          {application.job_title_snapshot}
                        </Link>
                      </td>
                      <td data-label="Company">{application.company_snapshot}</td>
                      <td data-label="Status">
                        <Badge tone={statusTone(application.status)}>
                          {statusLabel(application.status)}
                        </Badge>
                      </td>
                      <td data-label="Applied">{formatDate(application.applied_at)}</td>
                      <td data-label="">
                        <Link className="plink" to={`/me/applications/${application.id}`}>
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <div className="pager">
            <Button
              variant="ghost"
              disabled={page <= 1 || apps.loading}
              onClick={() => setPage((value) => value - 1)}
            >
              Previous
            </Button>
            <span className="pager__count">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="ghost"
              disabled={apps.loading || page >= totalPages}
              onClick={() => setPage((value) => value + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
