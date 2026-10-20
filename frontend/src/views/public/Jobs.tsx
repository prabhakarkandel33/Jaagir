import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { Button, Empty, ErrorNote, Field, Skeleton } from '../../components/ui';
import { api } from '../../lib/api';
import { formatDate, joinList, splitList } from '../../lib/format';
import { EMPLOYMENT_LABELS, EMPLOYMENT_TYPES, type JobHit, type Page } from '../../lib/types';

type Filters = {
  q: string;
  employmentType: string;
  location: string;
  skills: string;
};

const EMPTY_FILTERS: Filters = { q: '', employmentType: '', location: '', skills: '' };

export function Jobs() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initial = useRef<Filters>({
    q: searchParams.get('q') ?? '',
    employmentType: searchParams.get('employmentType') ?? '',
    location: searchParams.get('location') ?? '',
    skills: searchParams.get('skills') ?? '',
  });

  const [filters, setFilters] = useState<Filters>(initial.current);
  const [applied, setApplied] = useState<Filters>(initial.current);
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1);
  const [result, setResult] = useState<Page<JobHit> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const requestSeq = useRef(0);
  const debounceRef = useRef<number | null>(null);
  const firstRun = useRef(true);

  const runSearch = useCallback(
    async (nextFilters: Filters, nextPage: number) => {
      const seq = requestSeq.current + 1;
      requestSeq.current = seq;
      setLoading(true);
      setError(null);
      setApplied(nextFilters);

      const params = new URLSearchParams();
      if (nextFilters.q) params.set('q', nextFilters.q);
      if (nextFilters.employmentType) params.set('employmentType', nextFilters.employmentType);
      if (nextFilters.location) params.set('location', nextFilters.location);
      if (nextFilters.skills) params.set('skills', nextFilters.skills);
      if (nextPage > 1) params.set('page', String(nextPage));
      setSearchParams(params, { replace: true });

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
    },
    [setSearchParams],
  );

  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      void runSearch(initial.current, Number(searchParams.get('page')) || 1);
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
    // The browser history object is not part of the filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, runSearch]);

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

      <div className="results results--single">
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
                  className="hit"
                  onClick={() => navigate(`/jobs/${hit.id}`)}
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
      </div>
    </div>
  );
}
