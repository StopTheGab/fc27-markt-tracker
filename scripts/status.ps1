$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
python -m collector.cli status
