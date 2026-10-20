import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { PageHead } from '../../components/portal';
import { Badge, Button, Empty, ErrorNote, Skeleton, statusLabel, statusTone } from '../../components/ui';
import { api } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';
import type { Page, RecruiterApplication } from '../../lib/types';

const EMPTY_PAGE: Page<RecruiterApplication> = { items: [], page: 1, pageSize: 10, total: 0 };

export function RoleDetail() {
  const { id = '' } = useParams();
  const { token } = useSession();
  const activeToken = token ?? '';
  const [appsPage, setAppsPage] = useState(1);
  const [busy, setBusy] = useState<'publish' | 'close' | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [note, setNote] = useState<string | null>(null);

  const detail = useAsync(() => api.job.getJob(activeToken, id), [activeToken, id]);
  const apps = useAsync(
    () =>
      detail.data?.status === 'DRAFT'
        ? Promise.resolve(EMPTY_PAGE)
        : api.candidate.jobApplications(activeToken, id, appsPage, 10),
    [activeToken, id, appsPage, detail.data?.status],
  );

  async function transition(action: 'publish' | 'close') {
    setBusy(action);
    setActionError(null);
    setNote(null);
    try {
      if (action === 'publish') {
        await api.job.publishJob(activeToken, id);
        setNote('Role is live now.');
      } else {
        await api.job.closeJob(activeToken, id);
        setNote('Role closed. It no longer accepts applications.');
      }
      detail.reload();
      apps.reload();
    } catch (cause) {
      setActionError(cause);
    } finally {
      setBusy(null);
    }
  }

  const job = detail.data;
  const totalPages = apps.data ? Math.max(1, Math.ceil(apps.data.total / apps.data.pageSize)) : 1;

  return (
    <div className="pstack">
      <Link className="pback" to="/employers/roles">
        ← All roles
      </Link>

      {detail.loading && !job ? <Skeleton lines={5} /> : null}
      <ErrorNote error={detail.error} plain />

      {job ? (
        <>
          <PageHead
            title={job.title}
            sub={`${job.company} · ${job.location || 'Anywhere'} · updated ${formatDate(job.updated_at)}`}
            actions={
              <>
                <Link className="pbtn pbtn--ghost" to={`/employers/roles/${job.id}/edit`}>
                  Edit role
                </Link>
                {job.status === 'DRAFT' ? (
                  <Button busy={busy === 'publish'} onClick={() => void transition('publish')}>
                    Publish
                  </Button>
                ) : null}
                {job.status !== 'CLOSED' ? (
                  <Button
                    variant="danger"
                    busy={busy === 'close'}
                    onClick={() => void transition('close')}
                  >
                    Close role
                  </Button>
                ) : null}
              </>
            }
          />

          <ErrorNote error={actionError} plain />
          {note ? <p className="note note--ok">{note}</p> : null}

          <div className="twocol">
            <section className="pcard">
              <header className="pcard__head">
                <div>
                  <h2 className="pcard__title">Role details</h2>
                  <p className="pcard__sub">
                    {statusLabel(job.status)} · posted {formatDate(job.published_at)}
                  </p>
                </div>
                <Badge tone={statusTone(job.status)}>{statusLabel(job.status)}</Badge>
              </header>
              <div className="pcard__body">
                <div className="row row--wrap">
                  <Badge tone="muted">{job.employment_type.replace('_', ' ').toLowerCase()}</Badge>
                  {job.skills.map((skill) => (
                    <Badge key={skill} tone="muted">
                      {skill}
                    </Badge>
                  ))}
                </div>
                <p className="prose">{job.description}</p>
              </div>
            </section>

            <section className="pcard">
              <header className="pcard__head">
                <div>
                  <h2 className="pcard__title">Applicants</h2>
                  <p className="pcard__sub">
                    {apps.data?.total ?? 0} {apps.data?.total === 1 ? 'person has' : 'people have'}{' '}
                    applied.
                  </p>
                </div>
                <Button variant="ghost" onClick={apps.reload}>
                  Refresh
                </Button>
              </header>
              <div className="pcard__body">
                <ErrorNote error={apps.error} plain />
                {apps.loading && !apps.data ? <Skeleton lines={4} /> : null}
                {job.status === 'DRAFT' ? (
                  <Empty>Publish this role to start receiving applications.</Empty>
                ) : null}
                {apps.data && apps.data.items.length === 0 && job.status !== 'DRAFT' ? (
                  <Empty>No applications for this role yet.</Empty>
                ) : null}
                {apps.data && apps.data.items.length > 0 ? (
                  <ul className="plist">
                    {apps.data.items.map((application) => (
                      <li key={application.id}>
                        <Link
                          className="plist__row"
                          to={`/employers/applicants/${application.id}`}
                        >
                          <span className="plist__main">
                            <strong>{application.candidate.full_name}</strong>
                            <span className="meta">
                              {application.candidate.headline || 'Applicant'} ·{' '}
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

                {apps.data && apps.data.total > apps.data.pageSize ? (
                  <div className="pager">
                    <Button
                      variant="ghost"
                      disabled={appsPage <= 1}
                      onClick={() => setAppsPage((value) => value - 1)}
                    >
                      Previous
                    </Button>
                    <span className="pager__count">
                      Page {appsPage} of {totalPages}
                    </span>
                    <Button
                      variant="ghost"
                      disabled={appsPage >= totalPages}
                      onClick={() => setAppsPage((value) => value + 1)}
                    >
                      Next
                    </Button>
                  </div>
                ) : null}
              </div>
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}
