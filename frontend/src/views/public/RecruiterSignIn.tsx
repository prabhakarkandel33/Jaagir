import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { Button, ErrorNote, Field } from '../../components/ui';
import { api } from '../../lib/api';
import { safeNext, useSession } from '../../lib/session';

export function RecruiterSignIn() {
  const { signInRecruiter } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get('next');

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [form, setForm] = useState({
    email: '',
    password: '',
    full_name: '',
    company_name: '',
    phone: '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response =
        mode === 'login'
          ? await api.job.loginRecruiter({ email: form.email, password: form.password })
          : await api.job.registerRecruiter({
              email: form.email,
              password: form.password,
              full_name: form.full_name,
              company_name: form.company_name,
              phone: form.phone,
            });
      signInRecruiter(response);
      navigate(safeNext(next, '/employers/dashboard'), { replace: true });
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="authsplit">
      <section className="authcard">
        <div className="authcard__head">
          <h1 className="authcard__title">
            {mode === 'login' ? 'Employer sign in' : 'Start hiring on Jaagir'}
          </h1>
          <p className="authcard__sub">
            {mode === 'login'
              ? 'Sign in to manage your roles and read applicants.'
              : 'Create an account, post a role, and start meeting candidates.'}
          </p>
        </div>

        <div className="segmented" role="group" aria-label="Sign in or create an account">
          <button type="button" aria-pressed={mode === 'login'} onClick={() => setMode('login')}>
            Sign in
          </button>
          <button
            type="button"
            aria-pressed={mode === 'register'}
            onClick={() => setMode('register')}
          >
            Create account
          </button>
        </div>

        <form className="grid" onSubmit={submit}>
          <Field label="Work email" wide>
            <input
              className="input"
              type="email"
              autoComplete="username"
              required
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </Field>
          <Field label="Password" hint="At least 8 characters." wide>
            <input
              className="input"
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
              minLength={8}
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
            />
          </Field>
          {mode === 'register' ? (
            <>
              <Field label="Your name" wide>
                <input
                  className="input"
                  required
                  value={form.full_name}
                  onChange={(event) => setForm({ ...form, full_name: event.target.value })}
                />
              </Field>
              <Field label="Company">
                <input
                  className="input"
                  value={form.company_name}
                  onChange={(event) => setForm({ ...form, company_name: event.target.value })}
                />
              </Field>
              <Field label="Phone">
                <input
                  className="input"
                  value={form.phone}
                  onChange={(event) => setForm({ ...form, phone: event.target.value })}
                />
              </Field>
            </>
          ) : null}
          <div className="grid__submit">
            <Button type="submit" busy={busy}>
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </Button>
          </div>
        </form>
        <ErrorNote error={error} plain />
      </section>

      <aside className="authside">
        <h2 className="authside__title">Hire without the busywork</h2>
        <ul className="authside__list">
          <li>Write a role once and publish it with one click.</li>
          <li>See every applicant in a single list.</li>
          <li>Read profiles and CVs without leaving the page.</li>
        </ul>
        <Link className="link" to="/jobs">
          Browse open roles first
        </Link>
        <p className="authside__switch">
          Looking for work?{' '}
          <Link to={next ? `/me?next=${encodeURIComponent(next)}` : '/me'}>
            Go to the job seeker sign in
          </Link>
        </p>
      </aside>
    </div>
  );
}
