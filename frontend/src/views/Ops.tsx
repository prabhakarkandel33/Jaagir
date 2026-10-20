import { useEffect, useState } from 'react';

import {
  Badge,
  Button,
  Empty,
  ErrorNote,
  Field,
  Json,
  Panel,
  statusTone,
} from '../components/ui';
import { api, onWire, type WireEntry } from '../lib/api';
import { formatDate, formatRelative } from '../lib/format';
import type {
  DlqReplayResult,
  JobSnapshot,
  OutboxStatus,
  ReconcileResult,
  SnapshotPage,
  SyncStatus,
} from '../lib/types';

export function Ops({
  jobToken,
  candidateToken,
}: {
  jobToken: string;
  candidateToken: string;
}) {

  const [outbox, setOutbox] = useState<OutboxStatus | null>(null);
  const [outboxError, setOutboxError] = useState<unknown>(null);

  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [syncError, setSyncError] = useState<unknown>(null);
  const [reconcileMode, setReconcileMode] = useState<'full' | 'incremental'>('full');
  const [reconcileResult, setReconcileResult] = useState<ReconcileResult | null>(null);
  const [reconcileError, setReconcileError] = useState<unknown>(null);
  const [reconcileBusy, setReconcileBusy] = useState(false);

  const [dlqLimit, setDlqLimit] = useState(100);
  const [dlqResult, setDlqResult] = useState<DlqReplayResult | null>(null);
  const [dlqError, setDlqError] = useState<unknown>(null);
  const [dlqBusy, setDlqBusy] = useState(false);

  const [snapshotLimit, setSnapshotLimit] = useState(10);
  const [after, setAfter] = useState('');
  const [snapshot, setSnapshot] = useState<SnapshotPage | null>(null);
  const [snapshotError, setSnapshotError] = useState<unknown>(null);
  const [snapshotBusy, setSnapshotBusy] = useState(false);

  const [lookupId, setLookupId] = useState('');
  const [lookup, setLookup] = useState<JobSnapshot | null>(null);
  const [lookupError, setLookupError] = useState<unknown>(null);
  const [lookupBusy, setLookupBusy] = useState(false);

  const [wire, setWire] = useState<WireEntry[]>([]);

  useEffect(() => onWire((entry) => setWire((prev) => [entry, ...prev].slice(0, 40))), []);

  async function loadOutbox() {
    setOutboxError(null);
    try {
      setOutbox(await api.job.outbox(jobToken));
    } catch (cause) {
      setOutboxError(cause);
      setOutbox(null);
    }
  }

  async function loadSync() {
    setSyncError(null);
    try {
      setSync(await api.candidate.syncStatus(candidateToken));
    } catch (cause) {
      setSyncError(cause);
      setSync(null);
    }
  }

  async function runReconcile() {
    setReconcileBusy(true);
    setReconcileError(null);
    setReconcileResult(null);
    try {
      setReconcileResult(await api.candidate.reconcile(candidateToken, reconcileMode));
      await loadSync();
    } catch (cause) {
      setReconcileError(cause);
    } finally {
      setReconcileBusy(false);
    }
  }

  async function runDlq(dryRun: boolean) {
    setDlqBusy(true);
    setDlqError(null);
    setDlqResult(null);
    try {
      setDlqResult(await api.candidate.dlqReplay(candidateToken, dlqLimit, dryRun));
    } catch (cause) {
      setDlqError(cause);
    } finally {
      setDlqBusy(false);
    }
  }

  async function loadSnapshot(cursor: string) {
    setSnapshotBusy(true);
    setSnapshotError(null);
    try {
      const data = await api.job.snapshot(jobToken, cursor || undefined, snapshotLimit);
      setSnapshot(data);
      setAfter(cursor);
    } catch (cause) {
      setSnapshotError(cause);
      setSnapshot(null);
    } finally {
      setSnapshotBusy(false);
    }
  }

  async function lookupJob(event: React.FormEvent) {
    event.preventDefault();
    setLookupBusy(true);
    setLookupError(null);
    setLookup(null);
    try {
      setLookup(await api.job.internalJob(jobToken, lookupId.trim()));
    } catch (cause) {
      setLookupError(cause);
    } finally {
      setLookupBusy(false);
    }
  }

  return (
    <div className="stack">
      <Panel
        title="Outbox"
        service="job"
        subtitle="Pending rows mean the relay has not published yet. The API stays available."
        actions={
          <Button variant="ghost" onClick={() => void loadOutbox()}>
            Refresh
          </Button>
        }
      >
        <ErrorNote error={outboxError} />
        {outbox ? (
          <>
            <dl className="facts">
              <div>
                <dt>Pending</dt>
                <dd className={outbox.pending > 0 ? 'mark' : undefined}>{outbox.pending}</dd>
              </div>
              <div>
                <dt>Oldest pending</dt>
                <dd>{outbox.pending > 0 ? `${outbox.oldestPendingAgeSeconds}s` : '—'}</dd>
              </div>
              <div>
                <dt>Published last hour</dt>
                <dd>{outbox.publishedLastHour}</dd>
              </div>
              <div>
                <dt>Last error</dt>
                <dd className="prose prose--small">{outbox.lastError ?? 'none'}</dd>
              </div>
            </dl>
            <Json value={outbox} />
          </>
        ) : (
          <Empty>Read the outbox to see the backlog.</Empty>
        )}
      </Panel>

      <Panel
        title="Reconciliation"
        service="candidate"
        subtitle="Compares the replica with the job service snapshot and repairs missing or older rows."
        actions={
          <div className="row">
            <Button variant="ghost" onClick={() => void loadSync()}>
              Sync status
            </Button>
            <Button onClick={() => void runReconcile()} busy={reconcileBusy}>
              Run {reconcileMode}
            </Button>
          </div>
        }
      >
        <Field label="Mode">
          <select
            className="input"
            value={reconcileMode}
            onChange={(event) => setReconcileMode(event.target.value as 'full' | 'incremental')}
          >
            <option value="full">full</option>
            <option value="incremental">incremental</option>
          </select>
        </Field>
        <ErrorNote error={reconcileError} />
        <ErrorNote error={syncError} />
        {reconcileResult ? (
          <p className="note note--ok">
            {reconcileResult.mode}: checked {reconcileResult.checked}, repaired{' '}
            {reconcileResult.repaired}.
          </p>
        ) : null}
        {sync ? (
          <>
            <dl className="facts">
              <div>
                <dt>Local non-draft jobs</dt>
                <dd>{sync.localJobCount}</dd>
              </div>
              <div>
                <dt>Last repaired</dt>
                <dd>{sync.lastRepaired}</dd>
              </div>
              <div>
                <dt>Last run</dt>
                <dd>
                  {sync.lastRun
                    ? `${sync.lastRun.mode} · ${formatRelative(sync.lastRun.finishedAt ?? sync.lastRun.startedAt)}`
                    : 'never'}
                </dd>
              </div>
              <div>
                <dt>Last error</dt>
                <dd className="prose prose--small">{sync.lastRun?.error ?? 'none'}</dd>
              </div>
            </dl>
            <Json value={sync} />
          </>
        ) : (
          <Empty>Read the sync status to see the replica state.</Empty>
        )}
      </Panel>

      <Panel
        title="Dead letter queue"
        service="candidate"
        subtitle="Replay is safe: the consumer deduplicates and guards on version. The read set is the DLQ size at call start."
        actions={
          <div className="row">
            <Button variant="ghost" busy={dlqBusy} onClick={() => void runDlq(true)}>
              Dry run
            </Button>
            <Button busy={dlqBusy} onClick={() => void runDlq(false)}>
              Replay
            </Button>
          </div>
        }
      >
        <Field label="Limit" hint="At most this many messages are read from the DLQ.">
          <input
            className="input input--tight"
            type="number"
            min={1}
            max={100000}
            value={dlqLimit}
            onChange={(event) => setDlqLimit(Number(event.target.value) || 1)}
          />
        </Field>
        <ErrorNote error={dlqError} />
        {dlqResult ? (
          <p className="note note--ok">
            {dlqResult.dryRun ? 'Dry run' : 'Replay'}: read {dlqResult.read}, published{' '}
            {dlqResult.published}.
          </p>
        ) : null}
      </Panel>

      <Panel
        title="Snapshot"
        service="job"
        subtitle="Keyset paging over non-draft jobs; this is the reconciler's input."
        actions={
          <div className="row">
            <Button variant="ghost" busy={snapshotBusy} onClick={() => void loadSnapshot('')}>
              First page
            </Button>
            <Button
              variant="ghost"
              busy={snapshotBusy}
              disabled={!snapshot?.hasMore}
              onClick={() => void loadSnapshot(snapshot?.nextAfter ?? '')}
            >
              Next page
            </Button>
          </div>
        }
      >
        <div className="split split--tight">
          <Field label="Limit" hint="1 to 1000.">
            <input
              className="input input--tight"
              type="number"
              min={1}
              max={1000}
              value={snapshotLimit}
              onChange={(event) => setSnapshotLimit(Number(event.target.value) || 1)}
            />
          </Field>
          <Field label="after" hint="Keyset cursor; leave empty for the first page.">
            <input
              className="input"
              value={after}
              onChange={(event) => setAfter(event.target.value)}
              placeholder="uuid"
            />
          </Field>
        </div>
        <ErrorNote error={snapshotError} />
        {snapshot ? (
          <>
            <p className="meta">
              {snapshot.items.length} row(s) · hasMore {String(snapshot.hasMore)} · nextAfter{' '}
              <span className="mono">{snapshot.nextAfter ?? '—'}</span>
            </p>
            {snapshot.items.length > 0 ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Version</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.title}</td>
                      <td>
                        <Badge tone={statusTone(item.status)}>{item.status}</Badge>
                      </td>
                      <td className="mono">v{item.version}</td>
                      <td className="mono">{formatDate(item.updatedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <Empty>No rows after this cursor.</Empty>
            )}
            <Json value={snapshot} />
          </>
        ) : (
          <Empty>Fetch a page to inspect the snapshot shape.</Empty>
        )}
      </Panel>

      <Panel
        title="Internal job lookup"
        service="job"
        subtitle="One job by id, including CLOSED. Drafts return 404 here."
      >
        <form className="row" onSubmit={lookupJob}>
          <input
            className="input input--grow"
            value={lookupId}
            onChange={(event) => setLookupId(event.target.value)}
            placeholder="job uuid"
            required
          />
          <Button type="submit" busy={lookupBusy}>
            Look up
          </Button>
        </form>
        <ErrorNote error={lookupError} />
        {lookup ? <Json value={lookup} /> : null}
      </Panel>

      <Panel
        title="Wire log"
        service="both"
        subtitle="Every request this page sent, newest first."
        actions={
          <Button variant="quiet" onClick={() => setWire([])}>
            Clear
          </Button>
        }
      >
        {wire.length === 0 ? (
          <Empty>No requests yet.</Empty>
        ) : (
          <ol className="wire">
            {wire.map((entry) => (
              <li key={entry.id} className={entry.ok ? 'wire__ok' : 'wire__fail'}>
                <span className="mono wire__status">{entry.status || 'ERR'}</span>
                <span className="mono wire__method">{entry.method}</span>
                <span className="wire__url">{entry.url.replace(/^https?:\/\/[^/]+/, '')}</span>
                <span className="mono wire__ms">{entry.ms} ms</span>
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  );
}
