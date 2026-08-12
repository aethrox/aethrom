# Install the Aethrom skill into hermes and point hermes at the vault (Windows).
# Idempotent: safe to run repeatedly. Backs up config.yaml the way hermes itself does.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install-hermes.ps1 -VaultPath C:\Users\me\Documents\MyOS
param(
  [Parameter(Mandatory = $true)][string]$VaultPath,
  [string]$HermesHome = "$env:LOCALAPPDATA\hermes"
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $VaultPath)) { throw "no vault at: $VaultPath" }
if (-not (Test-Path $HermesHome)) { throw "no hermes at: $HermesHome" }

$skillsDir = (Resolve-Path (Join-Path $PSScriptRoot '..\hermes\skills')).Path
$configPath = Join-Path $HermesHome 'config.yaml'
$envPath = Join-Path $HermesHome '.env'

# --- 1. register the skills dir in config.yaml -------------------------------
$config = Get-Content $configPath -Raw
$needle = $skillsDir.Replace('\', '\\')

if ($config -match [regex]::Escape($skillsDir) -or $config -match [regex]::Escape($needle)) {
  Write-Output "external_dirs: already registered, skipped"
}
else {
  Copy-Item $configPath "$configPath.bak.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
  # skills:\n  external_dirs: []   ->   a one-entry list
  $pattern = "(?m)^(skills:\r?\n(?:[ \t]+.*\r?\n)*?[ \t]+external_dirs:)[ \t]*\[\][ \t]*$"
  if ($config -notmatch $pattern) {
    throw "no 'skills: external_dirs: []' in config.yaml. Add it by hand: external_dirs: ['$skillsDir']"
  }
  $config = [regex]::Replace($config, $pattern, "`$1`r`n    - '$skillsDir'")
  Set-Content -Path $configPath -Value $config -Encoding utf8 -NoNewline
  Write-Output "external_dirs: added -> $skillsDir"
}

# --- 2. point hermes at the vault -------------------------------------------
$envLines = if (Test-Path $envPath) { Get-Content $envPath } else { @() }
if ($envLines -match '^\s*OBSIDIAN_VAULT_PATH=') {
  $envLines = $envLines -replace '^\s*OBSIDIAN_VAULT_PATH=.*', "OBSIDIAN_VAULT_PATH=$VaultPath"
  Set-Content -Path $envPath -Value $envLines -Encoding utf8
  Write-Output "OBSIDIAN_VAULT_PATH updated -> $VaultPath"
}
else {
  Add-Content -Path $envPath -Value "OBSIDIAN_VAULT_PATH=$VaultPath" -Encoding utf8
  Write-Output "OBSIDIAN_VAULT_PATH added -> $VaultPath"
}

Write-Output ""
Write-Output "Done. Restart hermes, then ask it what you worked on last session."
