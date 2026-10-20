import { useCallback, useEffect, useRef, useState } from 'react';

import { Badge, Button, Empty, ErrorNote, Field, Skeleton } from '../components/ui';
import { api } from '../lib/api';
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

function filtersFromUrl(): Filters {
  const params = new URLSearchParams(window.location.search);
  return {
    q: params.get('q') ?? '',
    employmentType: params.get('employmentType') ?? '',
    location: params.get('location') ?? '',
    skills: params.get('skills') ?? '',
  };
}

function syncUrl(nextFilters: Filters, nextPage: number) {
  const params = new URLSearchParams();
  if (nextFilters.q) params.set('q', nextFilters.q);
  if (nextFilters.employmentType) params.set('employmentType', nextFilters.employmentType);
  if (nextFilters.location) params.set('location', nextFilters.location);
  if (nextFilters.skills) params.set('skills', nextFilters.skills);
  if (nextPage > 1) params.set('page', String(nextPage));
  const query = params.toString();
  window.history.replaceState(null, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
}

export function Discover({
  candidateToken,
  candidateName,
  onOpenAccount,
}: {
  candidateToken: string | null;
  candidateName: string | null;
  onOpenAccount: () => void;
}) {
  const [filters, setFilters] = useState<Filters>(filtersFromUrl);
  const [applied, setApplied] = useState<Filters>(filtersFromUrl);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<Page<JobHit> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [jobError, setJobError] = useState<unknown>(null);
  const [jobLoading, setJobLoading] = useState(false);

  const [coverLetter, setCoverLetter] = useState('');
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<unknown>(null);
  const [appliedNote, setAppliedNote] = useState(false);

  const requestSeq = useRef(0);
  const debounceRef = useRef<number | null>(null);
  const detailRef = useRef<HTMLDivElement | null>(null);
  const firstRun = useRef(true);

  const runSearch = useCallback(async (nextFilters: Filters, nextPage: number) => {
    const seq = requestSeq.current + 1;
    requestSeq.current = seq;
    setLoading(true);
    setError(null);
    setApplied(nextFilters);
    syncUrl(nextFilters, nextPage);
    try {
      const data = await api.candidate.searchJobs({
        q: nextFilters.q,
        employmentType: nextFilters.employmentType,
        location: nextFilters.location,
        skills: splitList(nextFilters.skills),
        page: nextPage,
        pageSize: 10,
      });
      if (requestSeq.current !== seq) return;
      setResult(data);
    } catch (cause) {
      if (requestSeq.current !== seq) return;
      setError(cause);
      setResult(null);
    } finally {
      if (requestSeq.current === seq) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      void runSearch(filtersFromUrl(), 1);
      return;
    }
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      setPage(1);
      void runSearch(filters, 1);
    }, 350);
    return () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    };
  }, [filters, runSearch]);

  useEffect(() => {
    if (!selectedId) return;
    if (window.matchMedia('(max-width: 980px)').matches) {
      detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [selectedId]);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    setPage(1);
    void runSearch(filters, 1);
  }

  function clearFilters() {
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
    setFilters(EMPTY_FILTERS);
    setPage(1);
    void runSearch(EMPTY_FILTERS, 1);
  }

  function goToPage(next: number) {
    setPage(next);
    void runSearch(applied, next);
  }

  async function openJob(id: string) {
    setSelectedId(id);
    setJob(null);
    setJobError(null);
    setApplyError(null);
    setAppliedNote(false);
    setCoverLetter('');
    setJobLoading(true);
    try {
      setJob(await api.candidate.getJob(id));
    } catch (cause) {
      setJobError(cause);
    } finally {
      setJobLoading(false);
    }
  }

  async function apply() {
    if (!job) return;
    if (!candidateToken) {
      onOpenAccount();
      return;
    }
    setApplying(true);
    setApplyError(null);
    try {
      await api.candidate.apply(candidateToken, job.id, coverLetter);
      setAppliedNote(true);
      setCoverLetter('');
    } catch (cause) {
      setApplyError(cause);
    } finally {
      setApplying(false);
    }
  }

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.pageSize)) : 1;
  const hasFilter =
    applied.q !== '' ||
    applied.employmentType !== '' ||
    applied.location !== '' ||
    applied.skills !== '';

  return (
    <div className="stack">
      <section className="searchbox">
        <div className="searchbox__head">
          <h1 className="searchbox__title">Find your next role</h1>
          <p className="searchbox__sub">
            Search open jobs by title, skill, place, or type of work.
          </p>
        </div>

        <form className="searchbox__form" onSubmit={submit}>
          <Field label="Search">
            <input
              className="input input--lg"
              value={filters.q}
              onChange={(event) => setFilters({ ...filters, q: event.target.value })}
              placeholder="Product designer, python, marketing…"
            />
          </Field>
          <div className="searchbox__row">
            <Field label="Type of work">
              <select
                className="input"
                value={filters.employmentType}
                onChange={(event) => setFilters({ ...filters, employmentType: event.target.value })}
              >
                <option value="">Any type</option>
                {EMPLOYMENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {EMPLOYMENT_LABELS[type]}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Where">
              <input
                className="input"
                value={filters.location}
                onChange={(event) => setFilters({ ...filters, location: event.target.value })}
                placeholder="City or remote"
              />
            </Field>
            <Field label="Skills">
              <input
                className="input"
                value={filters.skills}
                onChange={(event) => setFilters({ ...filters, skills: event.target.value })}
                placeholder="figma, python"
              />
            </Field>
          </div>
          <div className="searchbox__actions">
            <Button type="submit" busy={loading}>
              Search jobs
            </Button>
            {hasFilter ? (
              <button type="button" className="link" onClick={clearFilters}>
                Clear filters
              </button>
            ) : null}
          </div>
        </form>
      </section>

      <ErrorNote error={error} plain />

      <div className="results">
        <div className="results__list">
          {result ? (
            <p className="resultsline" aria-live="polite">
              <strong>{result.total.toLocaleString()}</strong>{' '}
              {result.total === 1 ? 'role' : 'roles'}
              {applied.q ? ` for “${applied.q}”` : ''}
              {loading ? <span className="resultsline__busy"> · updating…</span> : null}
            </p>
          ) : null}

          {loading && !result ? <Skeleton lines={5} /> : null}

          {result && result.items.length === 0 ? (
            <Empty>No roles match these filters yet. Try a different word or clear a filter.</Empty>
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
                  <span className="hit__skills">
                    {hit.skills.length > 0 ? joinList(hit.skills) : 'No skills listed'}
                  </span>
                  <span className="hit__foot">
                    <span>Posted {formatDate(hit.published_at)}</span>
                    <span className="hit__open">View role</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>

          {result && result.total > result.pageSize ? (
            <div className="pager">
              <Button
                variant="ghost"
                disabled={page <= 1 || loading}
                onClick={() => goToPage(page - 1)}
              >
                Previous
              </Button>
              <span className="pager__count">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="ghost"
                disabled={loading || page >= totalPages}
                onClick={() => goToPage(page + 1)}
              >
                Next
              </Button>
            </div>
          ) : null}
        </div>

        <div className="results__detail" ref={detailRef}>
          {selectedId ? (
            <section className="panel">
              <header className="panel__head">
                <div className="panel__intro">
                  <h2 className="panel__title">{job ? job.title : 'Loading role'}</h2>
                  <p className="panel__subtitle">
                    {job ? `${job.company} · ${job.location || 'Anywhere'}` : null}
                  </p>
                </div>
                <div className="panel__actions">
                  <Button
                    variant="quiet"
                    onClick={() => {
                      setSelectedId(null);
                      setJob(null);
                    }}
                  >
                    Close
                  </Button>
                </div>
              </header>
              <div className="panel__body">
                {jobLoading ? <Skeleton lines={4} /> : null}
                <ErrorNote error={jobError} plain />

                {job ? (
                  <div className="stack stack--tight">
                    <div className="row row--wrap">
                      <Badge tone="muted">{EMPLOYMENT_LABELS[job.employment_type]}</Badge>
                      {job.skills.map((skill) => (
                        <Badge key={skill} tone="muted">
                          {skill}
                        </Badge>
                      ))}
                    </div>

                    <p className="prose">{job.description}</p>

                    <p className="posted">Posted {formatDate(job.published_at)}</p>

                    <div className="apply">
                      <h3 className="apply__title">Apply for this role</h3>
                      {appliedNote ? (
                        <p className="note note--ok">
                          Application sent. You can follow it under My applications.
                        </p>
                      ) : null}

                      {candidateToken ? (
                        <>
                          <p className="meta">Applying as {candidateName ?? 'you'}.</p>
                          <Field label="Cover letter" hint="Optional." wide>
                            <textarea
                              className="input input--area"
                              rows={4}
                              value={coverLetter}
                              onChange={(event) => setCoverLetter(event.target.value)}
                              placeholder="Tell them why this role fits you."
                            />
                          </Field>
                          <div className="row">
                            <Button onClick={() => void apply()} busy={applying}>
                              Send application
                            </Button>
                          </div>
                          <ErrorNote error={applyError} plain />
                        </>
                      ) : (
                        <div className="apply__signin">
                          <p>Sign in to apply. Your profile goes with the application.</p>
                          <Button onClick={onOpenAccount}>Sign in or create an account</Button>
                        </div>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
            </section>
          ) : (
            <p className="results__hint">
              Pick a role to read the full description and apply.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
