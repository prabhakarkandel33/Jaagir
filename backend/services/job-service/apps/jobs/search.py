"""SQL-level full-text search over the ``jobs`` table (invariant I4).

Everything happens in PostgreSQL: filtering, ranking, ordering and paging.
Rows are never fetched into memory and filtered in Python.

Two query shapes:
  * non-empty ``q`` -> ``websearch_to_tsquery`` + ``ts_rank_cd`` (relevance,
    then recency, then id for a stable order);
  * empty ``q`` -> browse, ordered by recency only.

``status = 'PUBLISHED'`` is written as a literal predicate because the partial
GIN index can only be used when the planner sees that exact condition.

The ``{filters}`` placeholders below are filled from code-chosen fragments only;
every user value travels as a bound parameter (never string interpolation).
"""

from __future__ import annotations

from typing import Any

from django.db import connection

# Columns returned to the API. Keep in sync with JobSearchResultSerializer.
_SELECT_COLUMNS = "id, title, company, location, employment_type, skills, published_at"

_SEARCH_COUNT = """
    SELECT count(*)
    FROM jobs, websearch_to_tsquery('english', %(q)s) AS q
    WHERE status = 'PUBLISHED' AND search_vector @@ q
    {filters}
"""

_SEARCH_ROWS = """
    SELECT {columns}, ts_rank_cd(search_vector, q) AS rank
    FROM jobs, websearch_to_tsquery('english', %(q)s) AS q
    WHERE status = 'PUBLISHED' AND search_vector @@ q
    {filters}
    ORDER BY rank DESC, published_at DESC NULLS LAST, id
    LIMIT %(limit)s OFFSET %(offset)s
"""

_BROWSE_COUNT = """
    SELECT count(*)
    FROM jobs
    WHERE status = 'PUBLISHED'
    {filters}
"""

_BROWSE_ROWS = """
    SELECT {columns}, NULL::real AS rank
    FROM jobs
    WHERE status = 'PUBLISHED'
    {filters}
    ORDER BY published_at DESC NULLS LAST, id
    LIMIT %(limit)s OFFSET %(offset)s
"""


def _filter_sql(
    *,
    employment_type: str | None,
    location: str | None,
    skills: list[str] | None,
) -> tuple[str, dict[str, Any]]:
    """Build the optional WHERE fragment plus its bound parameters."""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if employment_type:
        clauses.append("AND employment_type = %(employment_type)s")
        params["employment_type"] = employment_type
    if location:
        clauses.append("AND lower(location) = lower(%(location)s)")
        params["location"] = location
    if skills:
        clauses.append("AND skills @> %(skills)s")
        params["skills"] = skills
    return "\n    ".join(clauses), params


def search_jobs(
    *,
    q: str = "",
    employment_type: str | None = None,
    location: str | None = None,
    skills: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Return ``(rows, total)`` for one page. Drafts and closed jobs never appear."""
    query = (q or "").strip()
    filters, params = _filter_sql(
        employment_type=employment_type,
        location=location,
        skills=skills,
    )
    offset = (page - 1) * page_size
    fill = {"columns": _SELECT_COLUMNS, "filters": filters}

    if query:
        count_sql = _SEARCH_COUNT.format(**fill)
        rows_sql = _SEARCH_ROWS.format(**fill)
        count_params: dict[str, Any] = {**params, "q": query}
    else:
        count_sql = _BROWSE_COUNT.format(**fill)
        rows_sql = _BROWSE_ROWS.format(**fill)
        count_params = dict(params)
    rows_params = {**count_params, "limit": page_size, "offset": offset}

    with connection.cursor() as cursor:
        cursor.execute(count_sql, count_params)
        row = cursor.fetchone()
        total = int(row[0]) if row else 0
        cursor.execute(rows_sql, rows_params)
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]
    return rows, total
