import { useEffect, useState } from 'react';

import { PageHead } from '../../components/portal';
import { Button, ErrorNote, Field, Modal, Skeleton } from '../../components/ui';
import { api } from '../../lib/api';
import { saveBlob } from '../../lib/files';
import { formatDate, joinList, splitList } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';
import type { Candidate } from '../../lib/types';

const MAX_BYTES = 5 * 1024 * 1024;

export function CandidateProfile() {
  const { token, updateProfile } = useSession();
  const activeToken = token ?? '';
  const profile = useAsync(() => api.candidate.me(activeToken), [activeToken]);

  const [form, setForm] = useState({
    full_name: '',
    phone: '',
    headline: '',
    location: '',
    skills: '',
    summary: '',
    resume_url: '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [note, setNote] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [cvBusy, setCvBusy] = useState(false);
  const [cvError, setCvError] = useState<unknown>(null);
  const [cvNote, setCvNote] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  useEffect(() => {
    if (!profile.data) return;
    setForm({
      full_name: profile.data.full_name,
      phone: profile.data.phone,
      headline: profile.data.headline,
      location: profile.data.location,
      skills: joinList(profile.data.skills),
      summary: profile.data.summary,
      resume_url: profile.data.has_resume ? '' : profile.data.resume_url,
    });
  }, [profile.data]);

  function applyProfile(data: Candidate) {
    updateProfile(data);
    profile.reload();
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const data = await api.candidate.updateMe(activeToken, {
        full_name: form.full_name,
        phone: form.phone,
        headline: form.headline,
        location: form.location,
        skills: splitList(form.skills),
        summary: form.summary,
        resume_url: form.resume_url,
      });
      applyProfile(data);
      setNote('Profile saved.');
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  async function uploadCv() {
    if (!file) return;
    setCvError(null);
    setCvNote(null);
    if (file.size > MAX_BYTES) {
      setCvError(new Error('The CV must be 5 MB or smaller.'));
      return;
    }
    setCvBusy(true);
    try {
      const data = await api.candidate.uploadResume(activeToken, file);
      applyProfile(data);
      setFile(null);
      setCvNote('CV uploaded.');
    } catch (cause) {
      setCvError(cause);
    } finally {
      setCvBusy(false);
    }
  }

  async function removeCv() {
    setCvBusy(true);
    setCvError(null);
    setCvNote(null);
    try {
      const data = await api.candidate.removeResume(activeToken);
      applyProfile(data);
      setCvNote('CV removed.');
    } catch (cause) {
      setCvError(cause);
    } finally {
      setCvBusy(false);
    }
  }

  async function previewCv() {
    setCvBusy(true);
    setCvError(null);
    try {
      const blob = await api.candidate.resumeBlob(activeToken);
      setPreviewUrl(URL.createObjectURL(blob));
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
      saveBlob(
        await api.candidate.resumeBlob(activeToken),
        profile.data?.resume_filename || 'resume.pdf',
      );
    } catch (cause) {
      setCvError(cause);
    } finally {
      setCvBusy(false);
    }
  }

  const data = profile.data;

  return (
    <div className="pstack">
      <PageHead
        title="My profile"
        sub="Employers see this when you apply. Keep it short and true."
      />

      <ErrorNote error={profile.error} plain />
      {profile.loading && !data ? <Skeleton lines={6} /> : null}

      {data ? (
        <div className="twocol twocol--profile">
          <section className="pcard">
            <header className="pcard__head">
              <div>
                <h2 className="pcard__title">About you</h2>
                <p className="pcard__sub">Signed in as {data.email}</p>
              </div>
            </header>
            <div className="pcard__body">
              <form className="grid" onSubmit={save}>
                <Field label="Full name" wide>
                  <input
                    className="input"
                    required
                    maxLength={200}
                    value={form.full_name}
                    onChange={(event) => setForm({ ...form, full_name: event.target.value })}
                  />
                </Field>
                <Field label="Headline">
                  <input
                    className="input"
                    maxLength={200}
                    placeholder="Backend engineer"
                    value={form.headline}
                    onChange={(event) => setForm({ ...form, headline: event.target.value })}
                  />
                </Field>
                <Field label="Where you live">
                  <input
                    className="input"
                    maxLength={200}
                    placeholder="Berlin"
                    value={form.location}
                    onChange={(event) => setForm({ ...form, location: event.target.value })}
                  />
                </Field>
                <Field label="Phone">
                  <input
                    className="input"
                    maxLength={50}
                    value={form.phone}
                    onChange={(event) => setForm({ ...form, phone: event.target.value })}
                  />
                </Field>
                <Field label="Portfolio link" hint="Optional. A link to your work.">
                  <input
                    className="input"
                    maxLength={500}
                    value={form.resume_url}
                    onChange={(event) => setForm({ ...form, resume_url: event.target.value })}
                    placeholder="https://example.com"
                  />
                </Field>
                <Field label="Skills" hint="Separate with commas." wide>
                  <input
                    className="input"
                    value={form.skills}
                    onChange={(event) => setForm({ ...form, skills: event.target.value })}
                  />
                </Field>
                <Field label="About you" wide>
                  <textarea
                    className="input input--area"
                    rows={5}
                    value={form.summary}
                    onChange={(event) => setForm({ ...form, summary: event.target.value })}
                    placeholder="A short introduction employers will read."
                  />
                </Field>
                <div className="grid__submit">
                  <Button type="submit" busy={busy}>
                    Save profile
                  </Button>
                </div>
              </form>
              <ErrorNote error={error} plain />
              {note ? <p className="note note--ok">{note}</p> : null}
            </div>
          </section>

          <section className="pcard">
            <header className="pcard__head">
              <div>
                <h2 className="pcard__title">Your CV</h2>
                <p className="pcard__sub">Employers open this first. PDF, up to 5 MB.</p>
              </div>
              {data.has_resume ? null : (
                <span className="cvtag">Not added yet</span>
              )}
            </header>
            <div className="pcard__body">
              {data.has_resume ? (
                <div className="cvbox">
                  <span className="cvbox__icon" aria-hidden="true">
                    PDF
                  </span>
                  <div className="cvbox__main">
                    <strong>{data.resume_filename || 'resume.pdf'}</strong>
                    <span className="meta">
                      Uploaded {formatDate(data.resume_uploaded_at)}
                    </span>
                  </div>
                  <div className="cvbox__actions">
                    <Button variant="ghost" busy={cvBusy} onClick={() => void previewCv()}>
                      Preview
                    </Button>
                    <Button variant="ghost" busy={cvBusy} onClick={() => void downloadCv()}>
                      Download
                    </Button>
                    <Button variant="quiet" busy={cvBusy} onClick={() => void removeCv()}>
                      Remove
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="cvhint">
                  Add a CV so employers can read your full history, not just your profile summary.
                </p>
              )}

              <div
                className={`cvdrop${dragging ? ' cvdrop--active' : ''}${file ? ' cvdrop--ready' : ''}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  const dropped = event.dataTransfer.files?.[0];
                  if (dropped) setFile(dropped);
                }}
              >
                <span className="cvdrop__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M12 16V4M12 4l-4 4M12 4l4 4" />
                    <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
                  </svg>
                </span>
                <div className="cvdrop__text">
                  <strong>
                    {file
                      ? file.name
                      : data.has_resume
                        ? 'Drop a new PDF here'
                        : 'Drop your PDF here'}
                  </strong>
                  <span className="meta">
                    {file
                      ? `${(file.size / (1024 * 1024)).toFixed(2)} MB ready to upload`
                      : 'or pick a file from your computer. PDF only, 5 MB maximum.'}
                  </span>
                </div>
                <div className="cvdrop__actions">
                  <label className="cvpick">
                    {file ? 'Choose another' : 'Choose file'}
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                    />
                  </label>
                  <Button disabled={!file} busy={cvBusy} onClick={() => void uploadCv()}>
                    {data.has_resume ? 'Replace CV' : 'Upload CV'}
                  </Button>
                </div>
              </div>

              <ErrorNote error={cvError} plain />
              {cvNote ? <p className="note note--ok">{cvNote}</p> : null}
            </div>
          </section>
        </div>
      ) : null}

      {previewUrl ? (
        <Modal
          title={data?.resume_filename || 'Your CV'}
          onClose={() => setPreviewUrl(null)}
          wide
          actions={
            <>
              <Button variant="ghost" onClick={() => void downloadCv()}>
                Download
              </Button>
              <Button variant="quiet" onClick={() => setPreviewUrl(null)}>
                Close
              </Button>
            </>
          }
        >
          <iframe className="cvframe" src={previewUrl} title="CV preview" />
        </Modal>
      ) : null}
    </div>
  );
}
