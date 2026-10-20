import { Link, useParams } from 'react-router-dom';

import { PageHead } from '../../components/portal';
import { Badge, ErrorNote, Skeleton, statusLabel, statusTone } from '../../components/ui';
import { api } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';

export function CandidateApplicationDetail() {
  const { applicationId = '' } = useParams();
  const { token } = useSession();
  const activeToken = token ?? '';
  const detail = useAsync(() => api.candidate.myApplication(activeToken, applicationId), [
    activeToken,
    applicationId,
  ]);

  const application = detail.data;

  return (
    <div className="pstack">
      <Link className="pback" to="/me/applications">
        ← All applications
      </Link>

      {detail.loading && !application ? <Skeleton lines={5} /> : null}
      <ErrorNote error={detail.error} plain />

      {application ? (
        <>
          <PageHead
            title={application.job_title_snapshot}
            sub={`${application.company_snapshot} · applied ${formatDate(application.applied_at)}`}
            actions={
              <Badge tone={statusTone(application.status)}>
                {statusLabel(application.status)}
              </Badge>
            }
          />

          <div className="twocol">
            <section className="pcard">
              <header className="pcard__head">
                <div>
                  <h2 className="pcard__title">Your cover letter</h2>
                  <p className="pcard__sub">Sent with the application.</p>
                </div>
              </header>
              <div className="pcard__body">
                <p className="prose">
                  {application.cover_letter || 'You did not write a cover letter.'}
                </p>
              </div>
            </section>

            <section className="pcard">
              <header className="pcard__head">
                <div>
                  <h2 className="pcard__title">The role</h2>
                  <p className="pcard__sub">
                    Status last changed {formatDate(application.status_updated_at)}
                  </p>
                </div>
              </header>
              <div className="pcard__body">
                <p className="meta">
                  {application.job.location || 'Anywhere'} ·{' '}
                  {application.job.employment_type.replace('_', ' ').toLowerCase()}
                </p>
                <div className="row row--wrap">
                  {application.job.skills.map((skill) => (
                    <Badge key={skill} tone="muted">
                      {skill}
                    </Badge>
                  ))}
                </div>
                <p className="prose prose--small">{application.job.description}</p>
                <p className="meta">
                  This role is {application.job.status === 'PUBLISHED' ? 'still open' : 'closed'}.
                </p>
              </div>
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}
