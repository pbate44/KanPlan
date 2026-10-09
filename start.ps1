# Install (if needed) and start KanPlan. Safe to re-run: finished steps are skipped.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Always use this project's .venv, even if another virtualenv is active.
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue

$Port = if ($env:PORT) { $env:PORT } else { "8000" }
$Url  = "http://localhost:$Port"

function Invoke-Checked {
    & $args[0] $args[1..($args.Length - 1)]
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    $uvDir = Join-Path $HOME ".local\bin"
    if (Test-Path (Join-Path $uvDir "uv.exe")) {
        $env:Path = "$uvDir;$env:Path"
    } else {
        Write-Host "KanPlan uses uv (https://docs.astral.sh/uv) to install Python and its dependencies."
        $answer = Read-Host "Install uv now? [Y/n]"
        if ($answer -match '^[nN]') {
            Write-Host "Install uv yourself, then re-run start.bat"
            exit 1
        }
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        $env:Path = "$uvDir;$env:Path"
    }
}

# --inexact keeps dev tools installed for contributors who run this script.
Write-Host "Installing dependencies..."
Invoke-Checked uv sync --no-dev --inexact --quiet

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env (AI uses a local Ollama by default; see .env for other providers)."
}

Invoke-Checked uv run --no-sync python manage.py migrate --verbosity 0

Invoke-Checked uv run --no-sync python manage.py setup_first_user

# Open the browser once the server responds
Start-Job -ArgumentList $Url -ScriptBlock {
    param($Url)
    for ($i = 0; $i -lt 15; $i++) {
        try {
            Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
            Start-Process $Url
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }
} | Out-Null

Write-Host "Starting KanPlan at $Url (press Ctrl+C to stop)"
uv run --no-sync python manage.py runserver $Port
