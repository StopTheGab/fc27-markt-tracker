# Optional: Collector bei jeder Windows-Anmeldung automatisch starten (Aufgabenplanung, nur dein Benutzer).
$root = Split-Path -Parent $PSScriptRoot
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$root\scripts\start.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
Register-ScheduledTask -TaskName "FC27-Collector" -Action $action -Trigger $trigger -Description "FC27 Markt-Tracker Collector" -Force | Out-Null
Write-Host "Autostart eingerichtet (Aufgabe 'FC27-Collector')."
