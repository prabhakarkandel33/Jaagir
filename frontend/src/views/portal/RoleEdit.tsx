import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { PageHead } from '../../components/portal';
import { Badge, Button, ErrorNote, Field, Skeleton, statusLabel, statusTone } from '../../components/ui';
import { api } from '../../lib/api';
import { joinList, splitList } from '../../lib/format';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';
import { EMPLOYMENT_LABELS, EMPLOYMENT_TYPES, type EmploymentType } from '../../lib/types';

export function RoleEdit() {
  const { id = '' } = useParams();
  const { token } = useSession();
  const activeToken = token ?? '';
  const navigate = useNavigate();

  const detail = useAsync(() => api.job.getJob(activeToken, id), [activeToken, id]);
  const [form, setForm] = useState({
    title: '',
    company: '',
    location: '',
    employment_type: 'FULL_TIME' as EmploymentType,
    skills: '',
    description: '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!detail.data) return;
    setForm({
      title: detail.data.title,
      company: detail.data.company,
      location: detail.data.location,
      employment_type: detail.data.employment_type,
      skills: joinList(detail.data.skills),
      description: detail.data.description,
    });
  }, [detail.data]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      await api.job.updateJob(activeToken, id, {
        title: form.title,
        description: form.description,
        company: form.company,
        location: form.location,
        employment_type: form.employment_type,
        skills: splitList(form.skills),
      });
      setNote('Changes saved.');
      detail.reload();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="pstack">
      <Link className="pback" to={`/employers/roles/${id}`}>
        ← Back to the role
      </Link>

      <PageHead
        title="Edit role"
        sub={detail.data ? detail.data.title : 'Loading role…'}
        actions={
          detail.data ? (
            <Badge tone={statusTone(detail.data.status)}>{statusLabel(detail.data.status)}</Badge>
          ) : null
        }
      />

      {detail.loading && !detail.data ? <Skeleton lines={6} /> : null}
      <ErrorNote error={detail.error} plain />

      {detail.data ? (
        <section className="pcard pcard--narrow">
          <div className="pcard__body">
            <form className="grid" onSubmit={save}>
              <Field label="Role title" wide>
                <input
                  className="input"
                  required
                  maxLength={200}
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                />
              </Field>
              <Field label="Company">
                <input
                  className="input"
                  required
                  maxLength={200}
                  value={form.company}
                  onChange={(event) => setForm({ ...form, company: event.target.value })}
                />
              </Field>
              <Field label="Location">
                <input
                  className="input"
                  maxLength={200}
                  value={form.location}
                  onChange={(event) => setForm({ ...form, location: event.target.value })}
                />
              </Field>
              <Field label="Type of work">
                <select
                  className="input"
                  value={form.employment_type}
                  onChange={(event) =>
                    setForm({ ...form, employment_type: event.target.value as EmploymentType })
                  }
                >
                  {EMPLOYMENT_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {EMPLOYMENT_LABELS[type]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Skills" hint="Separate with commas.">
                <input
                  className="input"
                  value={form.skills}
                  onChange={(event) => setForm({ ...form, skills: event.target.value })}
                />
              </Field>
              <Field label="Description" wide>
                <textarea
                  className="input input--area"
                  rows={8}
                  required
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                />
              </Field>
              <div className="grid__submit row">
                <Button type="submit" busy={busy}>
                  Save changes
                </Button>
                <Button variant="quiet" onClick={() => navigate(`/employers/roles/${id}`)}>
                  Cancel
                </Button>
              </div>
            </form>
            <ErrorNote error={error} plain />
            {note ? <p className="note note--ok">{note}</p> : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
