import { useEffect, useState } from 'react';

import { PageHead } from '../../components/portal';
import { Button, ErrorNote, Field, Skeleton } from '../../components/ui';
import { api } from '../../lib/api';
import { useSession } from '../../lib/session';
import { useAsync } from '../../lib/useAsync';

export function RecruiterProfile() {
  const { token, updateProfile } = useSession();
  const activeToken = token ?? '';
  const profile = useAsync(() => api.job.me(activeToken), [activeToken]);

  const [form, setForm] = useState({ full_name: '', company_name: '', phone: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!profile.data) return;
    setForm({
      full_name: profile.data.full_name,
      company_name: profile.data.company_name,
      phone: profile.data.phone,
    });
  }, [profile.data]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const data = await api.job.updateMe(activeToken, form);
      updateProfile(data);
      setNote('Company profile saved.');
      profile.reload();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="pstack">
      <PageHead
        title="Company profile"
        sub="Candidates see this name and company on every role you post."
      />

      <section className="pcard pcard--narrow">
        <div className="pcard__body">
          <ErrorNote error={profile.error} plain />
          {profile.loading && !profile.data ? <Skeleton lines={4} /> : null}

          {profile.data ? (
            <>
              <p className="meta">Signed in as {profile.data.email}</p>
              <form className="grid" onSubmit={save}>
                <Field label="Your name">
                  <input
                    className="input"
                    required
                    maxLength={200}
                    value={form.full_name}
                    onChange={(event) => setForm({ ...form, full_name: event.target.value })}
                  />
                </Field>
                <Field label="Company">
                  <input
                    className="input"
                    maxLength={200}
                    value={form.company_name}
                    onChange={(event) => setForm({ ...form, company_name: event.target.value })}
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
                <div className="grid__submit">
                  <Button type="submit" busy={busy}>
                    Save profile
                  </Button>
                </div>
              </form>
            </>
          ) : null}

          <ErrorNote error={error} plain />
          {note ? <p className="note note--ok">{note}</p> : null}
        </div>
      </section>
    </div>
  );
}
