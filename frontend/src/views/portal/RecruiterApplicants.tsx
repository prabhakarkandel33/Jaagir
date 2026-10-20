import { useState } from 'react';
import { Link } from 'react-router-dom';

import { PageHead } from '../../components/portal';
import { Badge, Button, Empty, ErrorNote, Skeleton, statusLabel, statusTone } from '../../components/ui';
import { api } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';

export function RecruiterApplicants() {
  const { token } = useSession();
  const activeToken = token ?? '';
  const [page, setPage] = useState(1);
  const apps = useAsync(() => api.candidate.allApplications(activeToken, page, 20), [
    activeToken,
    page,
  ]);

  const totalPages = apps.data ? Math.max(1, Math.ceil(apps.data.total / apps.data.pageSize)) : 1;

  return (
    <div className="pstack">
      <PageHead
        title="Applicants"
        sub="Everyone who applied to one of your roles, newest first."
        actions={
          <Button variant="ghost" onClick={apps.reload}>
            Refresh
          </Button>
        }
      />

      <section className="pcard">
        <div className="pcard__body">
          <ErrorNote error={apps.error} plain />
          {apps.loading && !apps.data ? <Skeleton lines={6} /> : null}
          {apps.data && apps.data.items.length === 0 ? (
            <Empty>No applicants yet. Publish a role and share it.</Empty>
          ) : null}

          {apps.data && apps.data.items.length > 0 ? (
            <div className="ptable-wrap">
              <table className="ptable">
                <thead>
                  <tr>
                    <th>Applicant</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Applied</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {apps.data.items.map((application) => (
                    <tr key={application.id}>
                      <td data-label="Applicant">
                        <Link
                          className="plink plink--strong"
                          to={`/employers/applicants/${application.id}`}
                        >
                          {application.candidate.full_name}
                        </Link>
                        <span className="meta block">
                          {application.candidate.headline || application.candidate.email}
                        </span>
                      </td>
                      <td data-label="Role">{application.job_title_snapshot}</td>
                      <td data-label="Status">
                        <Badge tone={statusTone(application.status)}>
                          {statusLabel(application.status)}
                        </Badge>
                      </td>
                      <td data-label="Applied">{formatDate(application.applied_at)}</td>
                      <td data-label="">
                        <Link
                          className="plink"
                          to={`/employers/applicants/${application.id}`}
                        >
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
