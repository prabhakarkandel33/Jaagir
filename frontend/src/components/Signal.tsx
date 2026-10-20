import type { Readyz } from '../lib/types';

export type Signal = 'ok' | 'degraded' | 'down' | 'unknown';

export function fromReady(ready: Readyz | null): Signal {
  if (!ready) return 'unknown';
  return ready.status === 'ok' ? 'ok' : 'degraded';
}

export function fromCheck(value: string | undefined): Signal {
  if (value === 'ok' || value === 'up') return 'ok';
  if (value === 'degraded' || value === 'stale') return 'degraded';
  if (value === 'down') return 'down';
  return 'unknown';
}

export function combine(values: (string | undefined)[]): Signal {
  const states = values.map(fromCheck);
  if (states.some((state) => state === 'down')) return 'down';
  if (states.some((state) => state === 'degraded')) return 'degraded';
  if (states.length > 0 && states.every((state) => state === 'ok')) return 'ok';
  return 'unknown';
}

export function tone(state: Signal): 'ok' | 'warn' | 'danger' | 'muted' {
  if (state === 'ok') return 'ok';
  if (state === 'degraded') return 'warn';
  if (state === 'down') return 'danger';
  return 'muted';
}

export function SignalPath({
  nodes,
}: {
  nodes: { id: string; label: string; state: Signal }[];
}) {
  const spoken = nodes.map((node) => `${node.label} ${node.state}`).join(', ');
  return (
    <div className="signal" role="img" aria-label={`Pipeline: ${spoken}`}>
      <span className="signal__track" aria-hidden="true" />
      {nodes.map((node) => (
        <div key={node.id} className={`signal__node is-${node.state}`}>
          <span className="signal__dot" aria-hidden="true">
            <span key={node.state} className="signal__halo" />
          </span>
          <span className="signal__label">{node.label}</span>
          <span className="signal__state">{node.state}</span>
        </div>
      ))}
    </div>
  );
}
