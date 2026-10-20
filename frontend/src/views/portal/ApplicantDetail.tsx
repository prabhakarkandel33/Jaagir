import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { Initials, PageHead } from '../../components/portal';
import { Badge, Button, ErrorNote, Skeleton, statusLabel, statusTone } from '../../components/ui';
import { api } from '../../lib/api';
import { openBlob, saveBlob } from '../../lib/files';
import { formatDate, joinList } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';
import { APPLICATION_STATUSES, type ApplicationStatus } from '../../lib/types';

export function ApplicantDetail() {
  const { applicationId = '' } = useParams();
  const { token } = useSession();
  const activeToken = token ?? '';
  const detail = useAsync(
    () => api.candidate.application(activeToken, applicationId),
    [activeToken, applicationId],
  );

  const [status, setStatus] = useState<ApplicationStatus>('IN_REVIEW');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [note, setNote] = useState<string | null>(null);
  const [cvBusy, setCvBusy] = useState(false);
  const [cvError, setCvError] = useState<unknown>(null);

  useEffect(() => {
    if (!detail.data) return;
    setStatus(
      APPLICATION_STATUSES.includes(detail.data.status) ? detail.data.status : 'IN_REVIEW',
    );
  }, [detail.data]);

  async function saveStatus() {
    setSaving(true);
    setSaveError(null);
    setNote(null);
    try {
      await api.candidate.setApplicationStatus(activeToken, applicationId, status);
      setNote(`Moved to ${statusLabel(status).toLowerCase()}.`);
      detail.reload();
    } catch (cause) {
      setSaveError(cause);
    } finally {
      setSaving(false);
    }
  }

  async function previewCv() {
    setCvBusy(true);
    setCvError(null);
    try {
      openBlob(await api.candidate.applicationResumeBlob(activeToken, applicationId));
    } catch (cause) {
      setCvError(cause);
    } finally {
      setCvBusy(false);
    }
  }

  async function downloadCv() {
    setCvBusy(true);
    setCvError(null);
    try {
      const name = detail.data?.candidate.resume_filename || 'resume.pdf';
      saveBlob(await api.candidate.applicationResumeBlob(activeToken, applicationId), name);
    } catch (cause) {
      setCvError(cause);
    } finally {
      setCvBusy(false);
    }
  }

  const application = detail.data;
  const candidate = application?.candidate;

  return (
    <div className="pstack">
      <Link className="pback" to="/employers/applicants">
        ← All applicants
      </Link>

      {detail.loading && !application ? <Skeleton lines={6} /> : null}
      <ErrorNote error={detail.error} plain />

      {application && candidate ? (
        <>
          <PageHead
            title={candidate.full_name}
            sub={`${application.job_title_snapshot} · applied ${formatDate(application.applied_at)}`}
            actions={
              <Badge tone={statusTone(application.status)}>
                {statusLabel(application.status)}
              </Badge>
            }
          />

          <div className="applicant-grid">
            <section className="pcard">
              <header className="pcard__head">
                <div className="applicant-head">
                  <Initials name={candidate.full_name} />
                  <div>
                    <h2 className="pcard__title">{candidate.headline || 'Applicant profile'}</h2>
                    <p className="pcard__sub">
                      {candidate.location || 'Location not given'} · {candidate.email}
                    </p>
                  </div>
                </div>
              </header>
              <div className="pcard__body">
                <dl className="facts">
                  <div>
                    <dt>Email</dt>
                    <dd>
                      <a className="plink" href={`mailto:${candidate.email}`}>
                        {candidate.email}
                      </a>
                    </dd>
                  </div>
                  <div>
                    <dt>Phone</dt>
                    <dd>{candidate.phone || 'Not given'}</dd>
                  </div>
                  <div>
                    <dt>Location</dt>
                    <dd>{candidate.location || 'Not given'}</dd>
                  </div>
                </dl>

                {candidate.skills.length > 0 ? (
                  <div className="row row--wrap">
                    {candidate.skills.map((skill) => (
                      <Badge key={skill} tone="muted">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="meta">No skills listed.</p>
                )}

                <h3 className="psection">About</h3>
                <p className="prose">
                  {candidate.summary || 'The candidate has not written a summary yet.'}
                </p>

                <h3 className="psection">Cover letter</h3>
                <p className="prose">
                  {application.cover_letter || 'No cover letter for this application.'}
                </p>
              </div>
            </section>

            <div className="pstack pstack--tight">
              <section className="pcard">
                <header className="pcard__head">
                  <div>
                    <h2 className="pcard__title">CV</h2>
                    <p className="pcard__sub">
                      {candidate.has_resume
                        ? candidate.resume_filename || 'Uploaded PDF'
                        : 'No CV uploaded.'}
                    </p>
                  </div>
                </header>
                <div className="pcard__body">
                  {candidate.has_resume ? (
                    <div className="row">
                      <Button variant="ghost" busy={cvBusy} onClick={() => void previewCv()}>
                        Preview
                      </Button>
                      <Button variant="ghost" busy={cvBusy} onClick={() => void downloadCv()}>
                        Download
                      </Button>
                    </div>
                  ) : (
                    <p className="meta">The candidate has not attached a CV.</p>
                  )}
                  <ErrorNote error={cvError} plain />
                </div>
              </section>

              <section className="pcard">
                <header className="pcard__head">
                  <div>
                    <h2 className="pcard__title">Application status</h2>
                    <p className="pcard__sub">
                      Last changed {formatDate(application.status_updated_at)}
                    </p>
                  </div>
                </header>
                <div className="pcard__body">
                  <label className="field">
                    <span className="field__label">Move this applicant to</span>
                    <select
                      className="input"
                      value={status}
                      onChange={(event) => setStatus(event.target.value as ApplicationStatus)}
                    >
                      {APPLICATION_STATUSES.map((item) => (
                        <option key={item} value={item}>
                          {statusLabel(item)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="row">
                    <Button busy={saving} onClick={() => void saveStatus()}>
                      Save status
                    </Button>
                  </div>
                  <ErrorNote error={saveError} plain />
                  {note ? <p className="note note--ok">{note}</p> : null}
                </div>
              </section>

              <section className="pcard">
                <header className="pcard__head">
                  <div>
                    <h2 className="pcard__title">Role</h2>
                    <p className="pcard__sub">{application.company_snapshot}</p>
                  </div>
                </header>
                <div className="pcard__body">
                  <p className="prose prose--small">{application.job.description}</p>
                  <p className="meta">
                    Skills: {joinList(application.job.skills) || 'none listed'}
                  </p>
                  <Link className="plink" to={`/employers/roles/${application.job.id}`}>
                    Open the role
                  </Link>
                </div>
              </section>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
