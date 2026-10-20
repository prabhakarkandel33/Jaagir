import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { PageHead } from '../../components/portal';
import { Button, ErrorNote, Field } from '../../components/ui';
import { api } from '../../lib/api';
import { splitList } from '../../lib/format';
import { useSession } from '../../lib/session';
import { EMPLOYMENT_LABELS, EMPLOYMENT_TYPES, type EmploymentType, type JobWrite } from '../../lib/types';

export function PostRole() {
  const { token, recruiter } = useSession();
  const navigate = useNavigate();
  const activeToken = token ?? '';

  const [form, setForm] = useState({
    title: '',
    company: recruiter?.company_name ?? '',
    location: '',
    employment_type: 'FULL_TIME' as EmploymentType,
    skills: '',
    description: '',
  });
  const [busy, setBusy] = useState<'draft' | 'publish' | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function create(publish: boolean) {
    setBusy(publish ? 'publish' : 'draft');
    setError(null);
    const payload: JobWrite = {
      title: form.title,
      description: form.description,
      company: form.company,
      location: form.location,
      employment_type: form.employment_type,
      skills: splitList(form.skills),
    };
    try {
      const draft = await api.job.createJob(activeToken, payload);
      if (publish) {
        await api.job.publishJob(activeToken, draft.id);
      }
      navigate(`/employers/roles/${draft.id}`, { replace: true });
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="pstack">
      <PageHead
        title="Post a role"
        sub="Write it once. Save a draft, or publish it for candidates now."
      />

      <section className="pcard pcard--narrow">
        <div className="pcard__body">
          <form
            className="grid"
            onSubmit={(event) => {
              event.preventDefault();
              void create(false);
            }}
          >
            <Field label="Role title" wide>
              <input
                className="input"
                required
                maxLength={200}
                placeholder="Senior Backend Engineer"
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
                placeholder="Remote, Berlin…"
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
                placeholder="What the person will do, who they will work with, and what you look for."
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </Field>
            <div className="grid__submit row">
              <Button type="submit" variant="ghost" busy={busy === 'draft'}>
                Save draft
              </Button>
              <Button busy={busy === 'publish'} onClick={() => void create(true)}>
                Publish now
              </Button>
            </div>
          </form>
          <ErrorNote error={error} plain />
        </div>
      </section>
    </div>
  );
}
