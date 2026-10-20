import { useCallback, useEffect, useState } from 'react';

import { Badge, Button, Empty, ErrorNote, Field, Json, Panel, Skeleton, statusTone } from '../components/ui';
import { api, type ServiceName } from '../lib/api';
import { EMPLOYMENT_LABELS, EMPLOYMENT_TYPES } from '../lib/types';
import type { Job, JobHit, Page } from '../lib/types';
import { formatDate, joinList, splitList } from '../lib/format';

type Filters = {
  q: string;
  employmentType: string;
  location: string;
  skills: string;
};

const EMPTY_FILTERS: Filters = { q: '', employmentType: '', location: '', skills: '' };

export function Discover({
  candidateToken,
  candidateName,
  onNeedCandidate,
}: {
  candidateToken: string | null;
  candidateName: string | null;
  onNeedCandidate: () => void;
}) {
  const [source, setSource] = useState<ServiceName>('candidate');
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<Page<JobHit> | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [jobError, setJobError] = useState<unknown>(null);
  const [jobLoading, setJobLoading] = useState(false);

  const [coverLetter, setCoverLetter] = useState('');
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<unknown>(null);
  const [applied, setApplied] = useState<string | null>(null);

  const search = useCallback(
    async (nextPage: number, nextFilters: Filters, nextSource: ServiceName) => {
      setLoading(true);
      setError(null);
      const started = performance.now();
      try {
        const params = {
          q: nextFilters.q,
          employmentType: nextFilters.employmentType,
          location: nextFilters.location,
          skills: splitList(nextFilters.skills),
          page: nextPage,
          pageSize: 10,
        };
        const data =
          nextSource === 'job'
            ? await api.job.searchJobs(params)
            : await api.candidate.searchJobs(params);
        setResult(data);
        setLatency(Math.round(performance.now() - started));
      } catch (cause) {
        setError(cause);
        setResult(null);
        setLatency(null);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void search(1, EMPTY_FILTERS, 'candidate');
  }, [search]);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setPage(1);
    setSelectedId(null);
    setJob(null);
    void search(1, filters, source);
  }

  function changeSource(next: ServiceName) {
    setSource(next);
    setPage(1);
    void search(1, filters, next);
  }

  function goToPage(next: number) {
    setPage(next);
    void search(next, filters, source);
  }

  async function openJob(id: string) {
    setSelectedId(id);
    setJob(null);
    setJobError(null);
    setApplyError(null);
    setApplied(null);
    setCoverLetter('');
    setJobLoading(true);
    try {
      const data = source === 'job' ? await api.job.getPublicJob(id) : await api.candidate.getJob(id);
      setJob(data);
    } catch (cause) {
      setJobError(cause);
    } finally {
      setJobLoading(false);
    }
  }

  async function apply() {
    if (!job) return;
    if (!candidateToken) {
      onNeedCandidate();
      return;
    }
    setApplying(true);
    setApplyError(null);
    setApplied(null);
    try {
      const application = await api.candidate.apply(candidateToken, job.id, coverLetter);
      setApplied(application.id);
      setCoverLetter('');
    } catch (cause) {
      setApplyError(cause);
    } finally {
      setApplying(false);
    }
  }

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.pageSize)) : 1;

  return (
    <div className="stack">
      <Panel
        title="Job search"
        service={source}
        subtitle="Full-text search over PostgreSQL. The candidate copy answers while Kafka is down."
        actions={
          <div className="segmented" role="group" aria-label="Source service">
            <button
              type="button"
              aria-pressed={source === 'candidate'}
              onClick={() => changeSource('candidate')}
            >
              Candidate replica
            </button>
            <button type="button" aria-pressed={source === 'job'} onClick={() => changeSource('job')}>
              Job service
            </button>
          </div>
        }
      >
        <form className="grid grid--query" onSubmit={submit}>
          <Field label="Keywords" wide>
            <input
              className="input"
              value={filters.q}
              onChange={(event) => setFilters({ ...filters, q: event.target.value })}
              placeholder="python engineer"
            />
          </Field>
          <Field label="Employment type">
            <select
              className="input"
              value={filters.employmentType}
              onChange={(event) => setFilters({ ...filters, employmentType: event.target.value })}
            >
              <option value="">Any</option>
              {EMPLOYMENT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {EMPLOYMENT_LABELS[type]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Location">
            <input
              className="input"
              value={filters.location}
              onChange={(event) => setFilters({ ...filters, location: event.target.value })}
              placeholder="Berlin"
            />
          </Field>
          <Field label="Skills" hint="Comma separated; matches all of them.">
            <input
              className="input"
              value={filters.skills}
              onChange={(event) => setFilters({ ...filters, skills: event.target.value })}
              placeholder="django, postgres"
            />
          </Field>
          <div className="grid__submit grid__submit--end">
            <Button type="submit" busy={loading}>
              Search
            </Button>
          </div>
        </form>

        <ErrorNote error={error} />

        {loading && !result ? <Skeleton lines={5} /> : null}

        {result ? (
          <p className="meta">
            {result.total.toLocaleString()} results · page {result.page} of {totalPages}
            {latency !== null ? ` · ${latency} ms` : ''}
          </p>
        ) : null}

        {result && result.items.length === 0 ? (
          <Empty>No published job matches these filters. Clear a filter or publish a job first.</Empty>
        ) : null}

        <ul className="hits">
          {result?.items.map((hit) => (
            <li key={hit.id}>
              <button
                type="button"
                className={`hit${selectedId === hit.id ? ' hit--active' : ''}`}
                onClick={() => void openJob(hit.id)}
              >
                <span className="hit__title">{hit.title}</span>
                <span className="hit__meta">
                  {hit.company} · {hit.location || 'Anywhere'} ·{' '}
                  {EMPLOYMENT_LABELS[hit.employment_type]}
                </span>
                <span className="hit__skills">{joinList(hit.skills) || 'no skills listed'}</span>
                <span className="hit__foot">
                  <span className="mono">{formatDate(hit.published_at)}</span>
                  <span className="mono hit__id">{hit.id.slice(0, 8)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>

        <div className="pager">
          <Button variant="ghost" disabled={page <= 1 || loading} onClick={() => goToPage(page - 1)}>
            Previous
          </Button>
          <span className="mono">{page}</span>
          <Button
            variant="ghost"
            disabled={loading || page >= totalPages}
            onClick={() => goToPage(page + 1)}
          >
            Next
          </Button>
        </div>
      </Panel>

      {selectedId ? (
        <Panel
          title={job ? job.title : 'Job detail'}
          service={source}
          subtitle={job ? `${job.company} · ${job.location || 'Anywhere'}` : undefined}
          actions={
            job ? (
              <div className="row">
                <Badge tone={statusTone(job.status)}>{job.status}</Badge>
                <Badge tone="job">v{job.version}</Badge>
              </div>
            ) : null
          }
        >
          {jobLoading ? <Skeleton lines={4} /> : null}
          <ErrorNote error={jobError} />

          {job ? (
            <div className="stack stack--tight">
              <p className="prose">{job.description}</p>
              <div className="row row--wrap">
                <Badge tone="muted">{EMPLOYMENT_LABELS[job.employment_type]}</Badge>
                {job.skills.map((skill) => (
                  <Badge key={skill} tone="muted">
                    {skill}
                  </Badge>
                ))}
              </div>
              <dl className="facts">
                <div>
                  <dt>Published</dt>
                  <dd>{formatDate(job.published_at)}</dd>
                </div>
                <div>
                  <dt>Job id</dt>
                  <dd className="mono">{job.id}</dd>
                </div>
                <div>
                  <dt>Updated</dt>
                  <dd>{formatDate(job.updated_at)}</dd>
                </div>
              </dl>

              <div className="apply">
                <h3 className="apply__title">Apply</h3>
                {candidateToken ? (
                  <>
                    <p className="meta">
                      Applying as {candidateName ?? 'candidate'} through the candidate service.
                    </p>
                    <Field
                      label="Cover letter"
                      hint="Optional. One application per candidate per job is enforced by a unique index."
                      wide
                    >
                      <textarea
                        className="input input--area"
                        rows={4}
                        value={coverLetter}
                        onChange={(event) => setCoverLetter(event.target.value)}
                        placeholder="Why this role?"
                      />
                    </Field>
                    <div className="row">
                      <Button onClick={() => void apply()} busy={applying}>
                        Send application
                      </Button>
                    </div>
                    <ErrorNote error={applyError} />
                    {applied ? (
                      <p className="note note--ok">
                        Application created: <span className="mono">{applied}</span>
                      </p>
                    ) : null}
                  </>
                ) : (
                  <p className="note note--info">
                    Sign in as a candidate to apply.{' '}
                    <button type="button" className="link" onClick={onNeedCandidate}>
                      Open the candidate tab
                    </button>
                    .
                  </p>
                )}
              </div>
            </div>
          ) : null}
        </Panel>
      ) : null}

      <Panel
        title="Raw response"
        service={source}
        subtitle="The exact JSON from the last search, for cross-checking against the API docs."
      >
        {result ? <Json value={result} /> : <Empty>Run a search to see the payload.</Empty>}
      </Panel>
    </div>
  );
}
