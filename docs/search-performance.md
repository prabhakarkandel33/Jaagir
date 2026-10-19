# Search performance

Evidence for milestone M5. The numbers below come from the local development
machine (Windows, Docker Desktop, PostgreSQL 16 in a container) with 100k
seeded rows. Treat them as a shape, not a benchmark score: the point is the
plan change (Seq Scan to Bitmap Index Scan), not the absolute milliseconds.

## Indexing strategy

Both services carry the same design, copied per service because each owns its
database (invariant I1). The candidate copy indexes its replica.

### `search_vector` is maintained by a trigger, not a generated column

A generated column is impossible here. `array_to_string` is only `STABLE`, and
PostgreSQL rejects non-immutable expressions in a generation expression. A
`BEFORE INSERT OR UPDATE` trigger computes the column instead:

```sql
NEW.search_vector :=
    setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A')
 || setweight(to_tsvector('english', coalesce(array_to_string(NEW.skills, ' '), '')), 'B')
 || setweight(to_tsvector('english', coalesce(NEW.company, '')), 'B')
 || setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
```

Weights make a title hit outrank a description hit. The trigger also fires for
the consumer's version-guarded upsert, so the replica needs no extra code to
stay searchable.

The migration order matters: add the column, create the trigger, backfill with
`UPDATE jobs SET search_vector = NULL` (which fires the trigger), and only then
build the indexes. That builds each GIN index once, on final values.

### Indexes

| Index | Type | Purpose |
|---|---|---|
| `jobs_search_vector_gin` | GIN, partial `WHERE status = 'PUBLISHED'` | Full-text match |
| `jobs_skills_gin` | GIN on `skills` | `skills @> ARRAY[...]` filter |
| `jobs_pub_browse_idx` | btree `(-published_at, id)`, partial | Empty-query browse and tie-break |
| `jobs_employment_idx` | btree on `employment_type` | Type filter |
| `jobs_location_lower_idx` | btree on `lower(location)` | Case-insensitive location filter |

The candidate service uses the `cjobs_*` prefix; otherwise the definitions are
identical.

The partial GIN index is only usable when the query contains the literal
predicate `status = 'PUBLISHED'`. The query modules write that literal, never a
bound parameter, for exactly this reason.

## Query shapes

Two shapes, both fully in SQL (invariant I4):

1. **Keyword search** (`q` non-empty):
   ```sql
   SELECT id, title, company, location, employment_type, skills, published_at,
          ts_rank_cd(search_vector, q) AS rank
   FROM jobs, websearch_to_tsquery('english', $1) AS q
   WHERE status = 'PUBLISHED' AND search_vector @@ q
   ORDER BY rank DESC, published_at DESC NULLS LAST, id
   LIMIT $2 OFFSET $3;
   ```
2. **Browse** (`q` empty): same projection, ordered by
   `published_at DESC NULLS LAST, id`.

`total` comes from a separate `count(*)` with the same predicate. Ordering ends
with `id` so pages cannot overlap when `published_at` ties.

`websearch_to_tsquery` is used, not `to_tsquery`: it accepts arbitrary user
input (quotes, `&`, `:*`, unbalanced parentheses) without raising, so hostile
input cannot produce a 500. It does not do prefix matching.

Filters are appended as fixed fragments with bound parameters:

```sql
AND employment_type = %(employment_type)s
AND lower(location) = lower(%(location)s)
AND skills @> %(skills)s
```

No user value is ever interpolated into SQL text.

## Seed

`scripts/seed_jobs.py` inserts 100,000 rows per database in one `COPY` per
batch of 5,000. Vocabulary comes from local word lists, so there is no heavy
dependency. Mix: ~90% PUBLISHED, 5% CLOSED, 5% DRAFT. `ANALYZE jobs` runs at
the end.

Observed: about 21 seconds per database on this machine.

```powershell
./tasks.ps1 seed -N 100000
./tasks.ps1 explain
```

## Captured plans

Commands: `python scripts/explain_analyze.py --service job` and
`--service candidate`. Baseline disables index and bitmap scans with
session-level `SET`; indexed restores them. Both run
`EXPLAIN (ANALYZE, BUFFERS)`.

### Job Service (`job_db`)

100,207 rows, 90,372 PUBLISHED, table plus indexes 134 MB.

#### Q1: `python engineer`

Baseline (Seq Scan), 173.256 ms:

```
Limit  (cost=0.00..8398.09 rows=20 width=53) (actual time=...)
  ->  Sort  ...
        ->  Seq Scan on jobs  (cost=0.00..13897.75 rows=3857 width=53)
              (actual time=0.126..169.687 rows=3707 loops=1)
              Filter: ((search_vector @@ ...) AND ((status)::text = 'PUBLISHED'::text))
Execution Time: 173.256 ms
```

Indexed, 29.097 ms:

```
Limit  (cost=8398.04..8398.09 rows=20 width=53) (actual time=28.995..29.001 rows=20 loops=1)
  ->  Sort  ...
        ->  Bitmap Heap Scan on jobs  (cost=74.71..8295.41 rows=3857 width=53)
              (actual time=4.646..27.431 rows=3707 loops=1)
              Recheck Cond: ((search_vector @@ '''python'' & ''engin'''::tsquery)
                             AND ((status)::text = 'PUBLISHED'::text))
              ->  Bitmap Index Scan on jobs_search_vector_gin  (cost=0.00..73.74 rows=3857 width=0)
                    (actual time=3.916..3.916 rows=3708 loops=1)
Execution Time: 29.097 ms
```

#### Q2: `kubernetes` + `employment_type = 'CONTRACT'`

Baseline 88.122 ms (Seq Scan) to indexed 16.311 ms. The indexed plan is a
BitmapAnd of two indexes:

```
->  Bitmap Heap Scan on jobs  (cost=286.76..4693.51 rows=1569 width=53)
      (actual time=10.750..15.479 rows=1584 loops=1)
      ->  Bitmap Index Scan on jobs_search_vector_gin  (actual time=3.897..3.897 rows=8114)
      ->  Bitmap Index Scan on jobs_employment_idx     (actual time=5.618..5.618 rows=19910)
Execution Time: 16.311 ms
```

#### Q3: `skills @> ARRAY['python','django']`

Baseline 84.783 ms (Seq Scan) to indexed 3.136 ms:

```
->  Bitmap Heap Scan on jobs  (cost=46.10..2631.28 rows=739 width=49)
      (actual time=1.209..2.816 rows=704 loops=1)
      ->  Bitmap Index Scan on jobs_skills_gin  (actual time=1.091..1.092 rows=783 loops=1)
Execution Time: 3.136 ms
```

### Candidate Service (`candidate_db`)

100,205 rows, 90,371 PUBLISHED, table plus indexes 134 MB.

| Query | Baseline (Seq Scan) | Indexed (GIN) |
|---|---|---|
| Q1 `python engineer` | 60.519 ms | 24.136 ms |
| Q2 `kubernetes` + CONTRACT | 76.225 ms | 18.576 ms |
| Q3 skills `python,django` | 91.586 ms | 2.598 ms |

Indexed Q1 uses `Bitmap Index Scan on cjobs_search_vector_gin` (actual
1.604 ms, 3,706 rows); Q2 uses `cjobs_search_vector_gin` plus
`cjobs_employment_idx`; Q3 uses `cjobs_skills_gin` (actual 1.314 ms).

## Caveats

- **Row counts drive the plan.** At a few hundred rows PostgreSQL correctly
  chooses a Seq Scan even with the index present. The demonstration needs 100k
  rows plus `ANALYZE`. This is expected behaviour, not a missing index.
- **The indexed plans still show a Bitmap Heap Scan with ~3,250 heap blocks
  for Q1.** A broad query matches about 3,700 of 90,000 published rows, so the
  heap fetch dominates. A rarer term shows a much larger relative gain.
- **`LIMIT/OFFSET` paging.** Deep offsets get slower because PostgreSQL still
  walks the skipped rows. Keyset pagination would fix that and is out of scope
  for the assignment; the API contract uses `page`/`pageSize`.
- **The count is a separate scan.** `total` costs another pass with the same
  predicate. At this scale it is a few milliseconds.
- **Timings include Docker Desktop overhead on Windows.** Compare baseline and
  indexed from the same run; do not compare against another machine.
- **The candidate replica can be seeded directly** (`--service candidate`).
  This is allowed only for benchmark seeding inside `scripts/`, as recorded in
  CONTEXT.md. Real replica writes always go through the consumer.
- **Language configuration is `english`.** It stems words (`engineer` matches
  `engineering`), which is what makes the seeded vocabulary behave like real
  data. A different language would need a different configuration and index.
