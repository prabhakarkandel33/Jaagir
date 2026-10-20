import { useState } from 'react';
import { Link } from 'react-router-dom';

import { PageHead } from '../../components/portal';
import { Badge, Button, Empty, ErrorNote, Skeleton, statusLabel, statusTone } from '../../components/ui';
import { api } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';

export function RecruiterRoles() {
  const { token } = useSession();
  const activeToken = token ?? '';
  const [page, setPage] = useState(1);

  const jobs = useAsync(() => api.job.listJobs(activeToken, page, 20), [activeToken, page]);
  const counts = useAsync(() => api.candidate.applicationCounts(activeToken), [activeToken]);

  const countByJob = new Map((counts.data ?? []).map((item) => [item.jobId, item]));
  const totalPages = jobs.data ? Math.max(1, Math.ceil(jobs.data.total / jobs.data.pageSize)) : 1;

  return (
    <div className="pstack">
      <PageHead
        title="Roles"
        sub="Every role you have written, with its applicant count."
        actions={
          <Link className="pbtn pbtn--primary" to="/employers/post">
            Post a role
          </Link>
        }
      />

      <section className="pcard">
        <div className="pcard__body">
          <ErrorNote error={jobs.error} plain />
          <ErrorNote error={counts.error} plain />
          {jobs.loading && !jobs.data ? <Skeleton lines={5} /> : null}

          {jobs.data && jobs.data.items.length === 0 ? (
            <Empty>
              No roles yet.{' '}
              <Link className="link" to="/employers/post">
                Post your first role
              </Link>
              .
            </Empty>
          ) : null}

          {jobs.data && jobs.data.items.length > 0 ? (
            <div className="ptable-wrap">
              <table className="ptable">
                <thead>
                  <tr>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Applicants</th>
                    <th>Updated</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {jobs.data.items.map((job) => {
                    const count = countByJob.get(job.id);
                    return (
                      <tr key={job.id}>
                        <td data-label="Role">
                          <Link className="plink plink--strong" to={`/employers/roles/${job.id}`}>
                            {job.title}
                          </Link>
                          <span className="meta block">{job.company}</span>
                        </td>
                        <td data-label="Status">
                          <Badge tone={statusTone(job.status)}>{statusLabel(job.status)}</Badge>
                        </td>
                        <td data-label="Applicants">{count?.total ?? 0}</td>
                        <td data-label="Updated">{formatDate(job.updated_at)}</td>
                        <td data-label="">
                          <div className="row">
                            <Link className="plink" to={`/employers/roles/${job.id}`}>
                              Open
                            </Link>
                            <Link className="plink" to={`/employers/roles/${job.id}/edit`}>
                              Edit
                            </Link>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          <div className="pager">
            <Button
              variant="ghost"
              disabled={page <= 1 || jobs.loading}
              onClick={() => setPage((value) => value - 1)}
            >
              Previous
            </Button>
            <span className="pager__count">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="ghost"
              disabled={jobs.loading || page >= totalPages}
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
