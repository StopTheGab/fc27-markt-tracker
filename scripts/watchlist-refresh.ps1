<#
.SYNOPSIS
  Startet die Neu-Recherche der Watchlist mit `claude -p` und uebernimmt das Ergebnis nur nach Validierung.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\watchlist-refresh.ps1
  powershell -ExecutionPolicy Bypass -File scripts\watchlist-refresh.ps1 -Date 2026-10-19
#>
param(
  [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),
  [int]$MaxAgeDays = 14,
  [string]$Model = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$minDate   = ([datetime]::ParseExact($Date, 'yyyy-MM-dd', $null)).AddDays(-$MaxAgeDays).ToString('yyyy-MM-dd')
$candidate = 'data/watchlist_candidate.json'
$target    = 'watchlist.json'
$backup    = "data/watchlist_backup_$Date.json"

New-Item -ItemType Directory -Force 'data', 'logs', 'knowledge' | Out-Null
if (Test-Path $candidate) { Remove-Item $candidate -Force }

$template = Get-Content 'prompts/watchlist_refresh.md' -Raw -Encoding UTF8
$prompt = $template.Replace('{{DATE}}', $Date).Replace('{{MIN_DATE}}', $minDate).Replace('{{OUT}}', $candidate)

$log = "logs/watchlist-refresh_$Date.log"
Write-Host "Starte claude -p (Datum $Date, Quellen ab $minDate) ... Log: $log"

$claudeArgs = @(
  '-p', $prompt,
  '--permission-mode', 'acceptEdits',
  '--allowedTools', 'WebSearch,WebFetch,Read,Write,Edit,Glob,Grep,Bash(python:*),Bash(python3:*),PowerShell'
)
if ($Model) { $claudeArgs += @('--model', $Model) }

& claude @claudeArgs 2>&1 | Tee-Object -FilePath $log
if ($LASTEXITCODE -ne 0) { Write-Warning "claude beendet mit Exit-Code $LASTEXITCODE" }

if (-not (Test-Path $candidate)) {
  Write-Error "Keine Kandidatendatei $candidate erzeugt - watchlist.json bleibt unveraendert."
  exit 1
}

Write-Host "Validiere $candidate ..."
& python -m collector.watchlist_tool validate $candidate --today $Date --max-age $MaxAgeDays
if ($LASTEXITCODE -ne 0) {
  Write-Error "Validierung fehlgeschlagen - watchlist.json bleibt unveraendert. Kandidat: $candidate"
  exit 1
}

if (Test-Path $target) {
  Copy-Item $target $backup -Force
  Write-Host "Altes watchlist.json gesichert als $backup"
}
Move-Item $candidate $target -Force
Write-Host "watchlist.json aktualisiert."
