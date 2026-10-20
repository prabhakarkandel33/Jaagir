import type { ReactNode } from 'react';

export function PageHead({
  title,
  sub,
  actions,
}: {
  title: string;
  sub?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="phead">
      <div>
        <h1 className="phead__title">{title}</h1>
        {sub ? <p className="phead__sub">{sub}</p> : null}
      </div>
      {actions ? <div className="phead__actions">{actions}</div> : null}
    </header>
  );
}

export function StatCard({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: number | string;
  note?: string;
  tone?: 'job' | 'cand' | 'ok' | 'warn' | 'danger';
}) {
  return (
    <div className={`stat${tone ? ` stat--${tone}` : ''}`}>
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
      {note ? <span className="stat__note">{note}</span> : null}
    </div>
  );
}

export function Breakdown({
  byStatus,
  order,
  total,
}: {
  byStatus: Record<string, number>;
  order: string[];
  total?: number;
}) {
  const shown = order.filter((status) => (byStatus[status] ?? 0) > 0);
  if (shown.length === 0) return <p className="meta">No activity yet.</p>;
  return (
    <ul className="breakdown">
      {shown.map((status) => (
        <li key={status} className={`breakdown__row breakdown__row--${status.toLowerCase()}`}>
          <span className="breakdown__label">{status.replace(/_/g, ' ').toLowerCase()}</span>
          <span className="breakdown__value">{byStatus[status] ?? 0}</span>
          <span
            className="breakdown__bar"
            style={{
              width: `${Math.max(4, Math.round(((byStatus[status] ?? 0) / Math.max(1, total ?? 1)) * 100))}%`,
            }}
          />
        </li>
      ))}
    </ul>
  );
}

export function Initials({ name }: { name: string }) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '');
  return (
    <span className="avatar" aria-hidden="true">
      {letters.join('') || '?'}
    </span>
  );
}
