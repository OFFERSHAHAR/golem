# One-click launcher: clean stale GOLEM processes, start supervisor, open UI.
$ErrorActionPreference = 'SilentlyContinue'
$dir = $PSScriptRoot
Set-Location $dir

# 1) stop only GOLEM's own python processes (never touches other python)
Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
  Where-Object { $_.CommandLine -match 'golem_live|golem_app|keepalive' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 3

# 2) start one supervisor that brings up wall engine + interface and keeps them alive
Start-Process -FilePath "$dir\.venv\Scripts\pythonw.exe" -ArgumentList 'keepalive.py' -WorkingDirectory $dir -WindowStyle Hidden

# 3) wait for the server, then open the browser
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try { if ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8770/ -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}
}
Start-Process "http://127.0.0.1:8770/"
