$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Platform venv is missing. Run scripts/setup.ps1 first."
}

& $Python -m streamlit run (Join-Path $Root "app.py")

