# Removes the autostart entry and stops the running lock.
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Productivity Lock.lnk'
if (Test-Path $shortcutPath) { Remove-Item $shortcutPath }

$main = Join-Path $PSScriptRoot 'main.py'
Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($main) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Output 'Autostart entfernt und Sperre beendet.'
