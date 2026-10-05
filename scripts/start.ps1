# Startet den FC27-Collector im Hintergrund (ohne Fenster). Mehrfachstart ist harmlos.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force (Join-Path $root "data"), (Join-Path $root "logs") | Out-Null
$pidFile = Join-Path $root "data\collector.pid"
if (Test-Path $pidFile) {
    $old = (Get-Content $pidFile -Raw).Trim()
    if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
        Write-Host "Collector laeuft bereits (PID $old)."
        exit 0
    }
}
$py = (Get-Command python -ErrorAction Stop).Source
$pyw = Join-Path (Split-Path $py) "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $py }
Remove-Item (Join-Path $root "data\STOP") -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $pyw -ArgumentList "-m", "collector.main" -WorkingDirectory $root -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 3
if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) {
    Write-Host "Collector gestartet (PID $($p.Id)). Log: logs\collector.log"
} else {
    Write-Host "Collector hat sich sofort beendet - siehe logs\collector.log"
    exit 1
}
