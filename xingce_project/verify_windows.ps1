# Reproducible native Windows smoke checks. Not evidence of a completed Windows run.
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot)
try {
  $env:PYTHONPATH = "$PWD;$PSScriptRoot"
  $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
  & $python -m unittest discover -s xingce_project/tests_backend -p 'test_*.py'
  if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed' }
  Push-Location xingce_project/apps/workbench/frontend
  try {
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw 'typecheck failed' }
    npm test
    if ($LASTEXITCODE -ne 0) { throw 'frontend tests failed' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'build failed' }
  } finally { Pop-Location }
  & $python xingce_project/start_workbench.py --diagnose
  if ($LASTEXITCODE -ne 0) { Write-Warning 'Private content missing/incomplete; smoke checks do not imply real practice acceptance.' }
} finally { Pop-Location }
