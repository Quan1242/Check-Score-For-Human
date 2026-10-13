param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Create the Python 3.14 environment first; see README.md.'
}
& $pythonExe -c "import sys; assert sys.version_info[:2] == (3, 14), 'Backend requires Python 3.14'"
if ($LASTEXITCODE -ne 0) { throw 'The project .venv must use Python 3.14.' }
Push-Location (Join-Path $projectDir 'backend')
try {
    & $pythonExe -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
