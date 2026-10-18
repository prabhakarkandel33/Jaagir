# Job Portal - top-level commands for Windows (mirror of Makefile).
# Usage:  ./tasks.ps1 <target>   e.g.  ./tasks.ps1 infra-up
#         ./tasks.ps1 seed -N 100000

param(
    [Parameter(Position = 0)]
    [string]$Target = 'help',
    [int]$N = 100000
)

$ErrorActionPreference = 'Stop'

$Backend   = 'backend'
$Job       = "$Backend/services/job-service"
$Cand      = "$Backend/services/candidate-service"
$Contracts = "$Backend/packages/contracts"
$Compose   = 'deploy/docker-compose.dev.yml'

function Invoke-In {
    param([string]$Dir, [scriptblock]$Block)
    Push-Location $Dir
    try { & $Block } finally { Pop-Location }
}

function Write-Help {
    @'
targets:
  infra-up / infra-down   kafka + 2 postgres (deploy/docker-compose.dev.yml)
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
        Invoke-In $Backend { uv run mypy services/job-service }
        Invoke-In $Backend { uv run mypy services/candidate-service }
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
    'seed' { Write-Output "tasks.ps1 seed: not implemented yet (M5). N=$N" }
    'explain' { Write-Output 'tasks.ps1 explain: not implemented yet (M5)' }
    'e2e' { Write-Output 'tasks.ps1 e2e: not implemented yet (M6)' }
    'prod-local' { Write-Output 'tasks.ps1 prod-local: not implemented yet (M7)' }
    default { Write-Output "Unknown target: $Target"; Write-Help; exit 1 }
}
