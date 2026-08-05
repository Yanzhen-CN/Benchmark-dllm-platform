$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

& $Python -m venv (Join-Path $Root ".venv")
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e $Root

Write-Host "Platform environment ready: $VenvPython"

