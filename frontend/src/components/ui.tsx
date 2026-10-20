import type { ReactNode } from 'react';

import { isApiError } from '../lib/api';
import { errorText } from '../lib/format';

type ServiceTag = 'job' | 'candidate' | 'both' | 'none';

const SERVICE_LABEL: Record<ServiceTag, string> = {
  job: 'Job service',
  candidate: 'Candidate service',
  both: 'Both services',
  none: '',
};

export function Panel({
  title,
  service = 'none',
  subtitle,
  actions,
  children,
  className,
}: {
  title: string;
  service?: ServiceTag;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const badgeTone = service === 'job' ? 'job' : service === 'candidate' ? 'cand' : 'muted';
  return (
    <section className={`panel panel--${service}${className ? ` ${className}` : ''}`}>
      <header className="panel__head">
        <div className="panel__intro">
          <div className="panel__titleRow">
            <h2 className="panel__title">{title}</h2>
            {service === 'none' ? null : (
              <Badge tone={badgeTone}>{SERVICE_LABEL[service]}</Badge>
            )}
          </div>
          {subtitle ? <p className="panel__subtitle">{subtitle}</p> : null}
        </div>
        {actions ? <div className="panel__actions">{actions}</div> : null}
      </header>
      <div className="panel__body">{children}</div>
    </section>
  );
}

export function Button({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  disabled,
  busy,
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit';
  variant?: 'primary' | 'ghost' | 'danger' | 'quiet';
  disabled?: boolean;
  busy?: boolean;
  title?: string;
}) {
  return (
    <button
      type={type}
      className={`btn btn--${variant}`}
      onClick={onClick}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      title={title}
    >
      {busy ? <span className="spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  children,
  wide,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <label className={`field${wide ? ' field--wide' : ''}`}>
      <span className="field__label">{label}</span>
      {children}
      {hint ? <span className="field__hint">{hint}</span> : null}
    </label>
  );
}

export function Badge({
  children,
  tone = 'muted',
}: {
  children: ReactNode;
  tone?: 'job' | 'cand' | 'ok' | 'warn' | 'danger' | 'muted';
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function statusTone(status: string): 'ok' | 'warn' | 'danger' | 'muted' | 'job' {
  switch (status) {
    case 'PUBLISHED':
    case 'ACCEPTED':
    case 'up':
    case 'ok':
      return 'ok';
    case 'DRAFT':
    case 'SUBMITTED':
    case 'IN_REVIEW':
      return 'warn';
    case 'CLOSED':
    case 'REJECTED':
    case 'down':
    case 'degraded':
      return 'danger';
    case 'SHORTLISTED':
      return 'job';
    default:
      return 'muted';
  }
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const code = isApiError(error) ? error.code : null;
  const status = isApiError(error) ? error.status : null;
  const details = isApiError(error) ? error.details : null;
  return (
    <div className="note note--error" role="alert">
      <div className="note__head">
        <strong>{code ?? 'Error'}</strong>
        {status ? <span className="note__meta">HTTP {status}</span> : null}
      </div>
      <p>{errorText(error)}</p>
      {details ? <pre className="json json--small">{JSON.stringify(details, null, 2)}</pre> : null}
    </div>
  );
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'ok' }) {
  return <p className={`note note--${tone}`}>{children}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} className={index === 0 ? 'skeleton__row skeleton__row--lead' : 'skeleton__row'} />
      ))}
    </div>
  );
}

export function Json({ value }: { value: unknown }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}

export function Spinner() {
  return <span className="spinner" aria-label="Loading" />;
}
