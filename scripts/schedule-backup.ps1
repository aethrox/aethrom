# Schedule the vault backup to run hourly (Windows).
# Usage: powershell -ExecutionPolicy Bypass -File schedule-backup.ps1 -VaultPath C:\Users\me\Documents\MyOS -VaultName MyOS
#
# Registers a per-user scheduled task. No admin rights, no service, and it is
# removable with one command (printed at the end).
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$VaultPath,
  [Parameter(Mandatory = $true)][string]$VaultName,
  [string]$BashPath
)
$ErrorActionPreference = 'Stop'

$backup = Join-Path $VaultPath '.claude\backup.sh'
if (-not (Test-Path $backup)) { throw "no backup.sh at $backup" }

# backup.sh is a bash script: it needs Git Bash, not System32\bash.exe (that is WSL
# and cannot see the vault at a Windows path).
if (-not $BashPath) {
  $gitCmd = Get-Command git -ErrorAction SilentlyContinue
  if (-not $gitCmd) { throw "git not found, cannot locate Git Bash" }
  $BashPath = Join-Path (Split-Path -Parent (Split-Path -Parent $gitCmd.Source)) 'bin\bash.exe'
  if (-not (Test-Path $BashPath)) {
    $BashPath = $gitCmd.Source -replace '\\cmd\\git\.exe$', '\bin\bash.exe'
  }
}
if (-not (Test-Path $BashPath)) { throw "Git Bash not found (looked for: $BashPath)" }

$taskName = "$VaultName Vault Backup"
$fwd = $VaultPath.Replace('\', '/')

# Git Bash is a console program, so an hourly task flashes a black window on the
# desktop every hour. wscript.exe runs it with no window at all. The wrapper waits
# and returns the exit code, so LastTaskResult still reports a failed backup.
$hidden = Join-Path $VaultPath '.claude\run-hidden.vbs'
if (Test-Path $hidden) {
  $action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\wscript.exe" `
    -Argument ('//nologo "{0}" "{1}" "{2}/.claude/backup.sh" "{2}"' -f $hidden, $BashPath, $fwd)
}
else {
  Write-Output "note: .claude\run-hidden.vbs missing, the task will show a console window each hour"
  $action = New-ScheduledTaskAction -Execute $BashPath -Argument "`"$fwd/.claude/backup.sh`" `"$fwd`""
}
# One trigger repeating hourly, rather than 24 daily triggers.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1)
# StartWhenAvailable catches up a run missed while the machine was off.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Output "scheduled: $taskName, hourly"
Write-Output "check with:  Get-ScheduledTaskInfo -TaskName '$taskName' | Select LastRunTime,LastTaskResult"
Write-Output "remove with: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Output "note: LastTaskResult other than 0 means the backup is stuck, nothing else announces it."
