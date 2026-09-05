# מדליק את גולם: הגוף על הקיר + האוזניים, המוח והקול.
#   .\start_golem.ps1              מודל תמלול small
#   .\start_golem.ps1 -Model medium   תמלול טוב יותר, איטי יותר
param([string]$Model = "large-v3", [int]$Brightness = 38, [int]$Idle = 75, [string]$Mic = "4")

$env:WINDIR = 'C:\Windows'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location $PSScriptRoot

Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

Start-Process -WindowStyle Hidden python -ArgumentList 'golem_live.py',
    '--brightness', $Brightness, '--idle', $Idle
Start-Sleep -Seconds 3

$brainArgs = @('golem_brain.py', '--model', $Model)
if ($Mic) { $brainArgs += @('--mic', $Mic) }
Start-Process -WindowStyle Hidden -RedirectStandardOutput brain.log -RedirectStandardError brain.err `
    python -ArgumentList $brainArgs

Start-Process -WindowStyle Hidden -RedirectStandardOutput eyes.log -RedirectStandardError eyes.err `
    python -ArgumentList @('-m', 'senses.eyes', '--flip')

Write-Host 'קלוד ער ורואה אותך. תקרא לו בשם.'
Write-Host 'מה הוא שומע:  Get-Content brain.log -Wait -Tail 20 -Encoding UTF8'
Write-Host 'לכבות:        Get-Process python | Stop-Process'
