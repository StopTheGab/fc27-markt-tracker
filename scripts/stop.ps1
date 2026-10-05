# Beendet den FC27-Collector sauber (Stopp-Datei), notfalls nach 60 s hart.
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root "data\collector.pid"
if (-not (Test-Path $pidFile)) { Write-Host "Collector laeuft nicht (keine PID-Datei)."; exit 0 }
$id = (Get-Content $pidFile -Raw).Trim()
if (-not (Get-Process -Id $id -ErrorAction SilentlyContinue)) {
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    Write-Host "Collector laeuft nicht (alte PID-Datei entfernt)."; exit 0
}
New-Item -ItemType File -Force (Join-Path $root "data\STOP") | Out-Null
Write-Host "Stopp angefordert, warte auf PID $id ..."
for ($i = 0; $i -lt 60; $i++) {
    if (-not (Get-Process -Id $id -ErrorAction SilentlyContinue)) { Write-Host "Collector sauber beendet."; exit 0 }
    Start-Sleep -Seconds 1
}
Write-Host "Laeuft noch (vermutlich mitten in einem Abruf) - beende hart."
Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
Remove-Item $pidFile, (Join-Path $root "data\STOP") -ErrorAction SilentlyContinue
