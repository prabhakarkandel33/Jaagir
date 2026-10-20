# Job Portal - top-level commands for Windows (mirror of Makefile).
# Usage:  ./tasks.ps1 <target>   e.g.  ./tasks.ps1 infra-up
#         ./tasks.ps1 seed -N 100000

param(
    [Parameter(Position = 0)]
    [string]$Target = 'help',
    [int]$N = 100000,
    [switch]$Build
)

$ErrorActionPreference = 'Stop'

$Backend   = 'backend'
$Job       = "$Backend/services/job-service"
$Cand      = "$Backend/services/candidate-service"
$Contracts = "$Backend/packages/contracts"
$Compose   = 'deploy/docker-compose.dev.yml'
$ComposeFull = 'deploy/docker-compose.dev-full.yml'

function Invoke-In {
    param([string]$Dir, [scriptblock]$Block)
    Push-Location $Dir
    try { & $Block } finally { Pop-Location }
}

function Write-Help {
    @'
targets:
  infra-up / infra-down   kafka + 2 postgres (deploy/docker-compose.dev.yml)
  stack-up                whole stack in docker: infra + 2 services + relay + consumer
  stack-down / stack-logs stack lifecycle ('stack-up -Build' rebuilds images)
  stack-ps                container status of the full stack
  sync                    uv sync --all-packages
  migrate                 migrate both DBs independently
  dev                     run both services (watch mode)
  verify                  lint + typecheck + unit + integration tests
  openapi                 dump OpenAPI JSON for both services into docs/
  seed -N 100000          seed jobs for search benchmarks (M5)
  explain                 EXPLAIN (ANALYZE, BUFFERS) benchmark (M5)
  e2e                     outage/recovery scenarios (M6)
  prod-local              prod compose behind Caddy (M7)
'@ | Write-Output
}

switch ($Target) {
    'help' { Write-Help }
    'sync' { Invoke-In $Backend { uv sync --all-packages } }
    'infra-up' { docker compose -f $Compose up -d --wait }
    'infra-down' { docker compose -f $Compose down }
    'stack-up' {
        if ($Build) { docker compose -f $ComposeFull up -d --build --wait }
        else { docker compose -f $ComposeFull up -d --wait }
    }
    'stack-down' { docker compose -f $ComposeFull down }
    'stack-logs' { docker compose -f $ComposeFull logs -f }
    'stack-ps' { docker compose -f $ComposeFull ps }
    'migrate' {
        Invoke-In $Job  { uv run python manage.py migrate }
        Invoke-In $Cand { uv run python manage.py migrate }
    }
    'dev-job' { Invoke-In $Job { uv run python manage.py runserver 3001 } }
    'dev-candidate' { Invoke-In $Cand { uv run python manage.py runserver 3002 } }
    'dev' {
        Start-Process powershell -ArgumentList '-NoProfile', '-Command', "& '$PSCommandPath' dev-job"
        Start-Process powershell -ArgumentList '-NoProfile', '-Command', "& '$PSCommandPath' dev-candidate"
    }
    'lint' {
        Invoke-In $Backend { uv run ruff check . }
        Invoke-In $Backend { uv run ruff format --check . }
    }
    'typecheck' {
        Invoke-In $Backend { uv run mypy packages/contracts/src }
        Invoke-In $Job { uv run mypy --config-file mypy.ini . }
        Invoke-In $Cand { uv run mypy --config-file mypy.ini . }
    }
    'test' {
        Invoke-In $Contracts { uv run pytest -q }
        Invoke-In $Job { uv run pytest -q }
        Invoke-In $Cand { uv run pytest -q }
    }
    'verify' {
        & $PSCommandPath lint
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $PSCommandPath typecheck
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $PSCommandPath test
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    'openapi' {
        New-Item -ItemType Directory -Force -Path 'docs' | Out-Null
        Invoke-In $Job  { uv run python manage.py spectacular --file ../../../docs/openapi-job-service.json }
        Invoke-In $Cand { uv run python manage.py spectacular --file ../../../docs/openapi-candidate-service.json }
    }
    'seed' {
        Invoke-In '.' { uv run --project backend python scripts/seed_jobs.py --service job --count $N }
        Invoke-In '.' { uv run --project backend python scripts/seed_jobs.py --service candidate --count $N }
    }
    'explain' {
        Invoke-In '.' { uv run --project backend python scripts/explain_analyze.py --service job }
        Invoke-In '.' { uv run --project backend python scripts/explain_analyze.py --service candidate }
    }
    'e2e' { Invoke-In '.' { uv run --project backend python e2e/run_e2e.py } }
    'prod-local' { Write-Output 'tasks.ps1 prod-local: not implemented yet (M7)' }
    default { Write-Output "Unknown target: $Target"; Write-Help; exit 1 }
}

