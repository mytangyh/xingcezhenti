$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
  & .\.venv\Scripts\python.exe start_workbench.py @args
  exit $LASTEXITCODE
} finally { Pop-Location }
