# Starts the lock with Windows for this user and right now. Needs no admin rights.
$root = $PSScriptRoot
$pythonw = Join-Path (Split-Path (Get-Command python).Source) 'pythonw.exe'
$main = Join-Path $root 'main.py'

$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Productivity Lock.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "`"$main`""
$shortcut.WorkingDirectory = $root
$shortcut.Save()

# Start through Explorer so the lock does not belong to this shell and survives it closing.
# A second instance could not bind the port and would exit by itself.
Start-Process -FilePath explorer.exe -ArgumentList "`"$shortcutPath`""
Write-Output "Autostart eingerichtet: $shortcutPath"
