#!/usr/bin/env pwsh
# Prevent committing forbidden local files (PowerShell)
$forbidden = '^\.mdt_dlls/|^mdt_devices\.json$|^mdt_probe\.json$'
$staged = (& git diff --cached --name-only) -join "`n"
$matches = @()
foreach ($line in $staged -split "`n") {
    if ($line -match $forbidden) { $matches += $line }
}
if ($matches.Count -gt 0) {
    Write-Error "ERROR: Commit contains forbidden local files:"
    $matches | ForEach-Object { Write-Output "  $_" }
    Write-Output "These files should remain local only. To remove them from the index run:`n  git rm --cached <file>"
    exit 1
}
exit 0
