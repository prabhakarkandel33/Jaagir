import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { Button, ErrorNote, Field, PasswordInput } from '../../components/ui';
import { api } from '../../lib/api';
import { safeNext, useSession } from '../../lib/session';

export function CandidateSignIn() {
  const { signInCandidate } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get('next');

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [form, setForm] = useState({ email: '', password: '', full_name: '', phone: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response =
        mode === 'login'
          ? await api.candidate.login({ email: form.email, password: form.password })
          : await api.candidate.register({
              email: form.email,
              password: form.password,
              full_name: form.full_name,
              phone: form.phone,
            });
      signInCandidate(response);
      navigate(safeNext(next, '/me/dashboard'), { replace: true });
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
            {mode === 'login' ? 'Job seeker sign in' : 'Create a job seeker account'}
          </h1>
          <p className="authcard__sub">
            {mode === 'login'
              ? 'Sign in to apply for roles and track your applications.'
              : 'One account for applying, keeping your profile, and following every role.'}
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
          <Field label="Email" wide>
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
            <PasswordInput
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={8}
              value={form.password}
              onChange={(password) => setForm({ ...form, password })}
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
        <h2 className="authside__title">A profile that works for you</h2>
        <ul className="authside__list">
          <li>Keep your skills, headline, and CV in one place.</li>
          <li>Apply in a click and follow every application.</li>
          <li>Come back any time to see what moved.</li>
        </ul>
        <Link className="link" to="/jobs">
          Browse open roles first
        </Link>
        <p className="authside__switch">
          Hiring instead?{' '}
          <Link to={next ? `/employers?next=${encodeURIComponent(next)}` : '/employers'}>
            Go to the employer sign in
          </Link>
        </p>
      </aside>
    </div>
  );
}
