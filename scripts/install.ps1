# Aethrom setup wizard (Windows).
#
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
#
# Asks which language your companion should speak, where the vault should live,
# pulls an existing vault repo if you have one, scaffolds a fresh vault from
# template/ if you do not, wires the hooks for this platform, and offers the
# desktop launcher and an hourly backup.
#
# Idempotent: it never overwrites an existing vault without asking.
[CmdletBinding()]
param(
  [string]$VaultRepo,
  [string]$VaultPath,
  [string]$OsName,
  [string]$UserName,
  [string]$Companion,
  [string]$Language,
  [switch]$NoLauncher,
  [switch]$NoBackup,
  [switch]$NonInteractive
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Ask([string]$Question, [string]$Default) {
  if ($NonInteractive) { return $Default }
  $suffix = if ($Default) { " [$Default]" } else { "" }
  $answer = Read-Host "$Question$suffix"
  if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
  return $answer.Trim()
}

function AskYesNo([string]$Question, [bool]$Default) {
  if ($NonInteractive) { return $Default }
  $hint = if ($Default) { "[Y/n]" } else { "[y/N]" }
  while ($true) {
    $a = (Read-Host "$Question $hint").Trim().ToLowerInvariant()
    if ($a -eq '') { return $Default }
    if ($a -in @('y', 'yes')) { return $true }
    if ($a -in @('n', 'no')) { return $false }
  }
}

function Fail([string]$Message) { Write-Host "`n  ERROR: $Message" -ForegroundColor Red; exit 1 }
function Step([string]$Message) { Write-Host "`n> $Message" -ForegroundColor Cyan }
function Ok([string]$Message) { Write-Host "  $Message" -ForegroundColor Green }
function Note([string]$Message) { Write-Host "  $Message" -ForegroundColor DarkGray }

Write-Host ""
Write-Host "  Aethrom setup wizard" -ForegroundColor White
Write-Host "  Builds a second brain that remembers across sessions."

# --- language ---------------------------------------------------------------
# Asked first because it decides how the thing you are building will talk to you.
# The wizard itself stays in English; this is the vault's language, not the
# installer's. Free text on purpose: write it however you name it.
Step "Language"
if (-not $Language) {
  $langDefault = switch -Wildcard ((Get-Culture).TwoLetterISOLanguageName) {
    'tr' { 'Turkish' }; 'de' { 'German' }; 'fr' { 'French' }; 'es' { 'Spanish' }
    'it' { 'Italian' }; 'pt' { 'Portuguese' }; 'nl' { 'Dutch' }; 'ru' { 'Russian' }
    'ja' { 'Japanese' }; 'zh' { 'Chinese' }; 'ar' { 'Arabic' }
    default { 'English' }
  }
  Write-Host "  Which language should your companion speak to you in?"
  $Language = Ask "  Language" $langDefault
}
Ok "your companion will speak $Language"

# --- prerequisites ----------------------------------------------------------
Step "Prerequisites"

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) { Fail "git not found. Install it from https://git-scm.com/download/win" }

# The hooks are bash scripts. System32\bash.exe is the WSL launcher and cannot
# see the vault at a Windows path, so Git Bash is what we need.
$bashPath = Join-Path (Split-Path -Parent (Split-Path -Parent $gitCmd.Source)) 'bin\bash.exe'
if (-not (Test-Path $bashPath)) {
  $bashPath = $gitCmd.Source -replace '\\cmd\\git\.exe$', '\bin\bash.exe'
}
if (-not (Test-Path $bashPath)) { Fail "Git Bash not found (looked for: $bashPath)." }
& $bashPath -c "echo ok" *> $null
if ($LASTEXITCODE -ne 0) { Fail "Git Bash does not run: $bashPath" }
Ok "git and Git Bash are ready"

if (-not (Test-Path "$env:LOCALAPPDATA\Programs\Obsidian\Obsidian.exe")) {
  Note "Obsidian does not look installed. The vault is still set up; afterwards: winget install Obsidian.Obsidian"
}
else { Ok "Obsidian is installed" }

# --- existing vault or a new one -------------------------------------------
Step "Vault source"

$alreadyInstalled = $false
if ($VaultPath -and (Test-Path (Join-Path $VaultPath '.claude\hooks'))) {
  # Re-run against a vault that is already in place: skip straight to wiring.
  $alreadyInstalled = $true
  Ok "$VaultPath is already an Aethrom vault, only the wiring will be rechecked"
}

if (-not $VaultRepo -and -not $NonInteractive -and -not $alreadyInstalled) {
  Write-Host "  If you already have a vault repo, enter its URL (leave empty to start fresh)."
  $VaultRepo = Ask "  Vault repo URL" ""
}
$cloning = (-not [string]::IsNullOrWhiteSpace($VaultRepo)) -and (-not $alreadyInstalled)

if (-not $OsName) {
  $default = if ($cloning) {
    ($VaultRepo -replace '\.git$', '' -split '[/\\]')[-1]
  }
  else {
    $n = ($env:COMPUTERNAME -replace "[^A-Za-z0-9]", "")
    if ($n) { $n.Substring(0, 1).ToUpper() + $n.Substring(1).ToLower() + "OS" } else { "MyOS" }
  }
  $OsName = Ask "  Name of your system" $default
}
if (-not $VaultPath) {
  $VaultPath = Ask "  Vault path" (Join-Path ([Environment]::GetFolderPath('MyDocuments')) $OsName)
}

if ((Test-Path $VaultPath) -and (-not $alreadyInstalled)) {
  $existing = @(Get-ChildItem $VaultPath -Force -ErrorAction SilentlyContinue)
  if ($existing.Count -gt 0) {
    Write-Host "  $VaultPath already exists and holds $($existing.Count) items:" -ForegroundColor Yellow
    $existing | Select-Object -First 8 | ForEach-Object { Note "  - $($_.Name)" }
    if (-not (AskYesNo "  Continue? (existing files are NOT overwritten)" $false)) {
      Fail "Cancelled. Pick another path."
    }
  }
}

# --- fetch or scaffold ------------------------------------------------------
if ($alreadyInstalled) {
  Step "Using the existing vault"
  Note $VaultPath
}
elseif ($cloning) {
  Step "Fetching the vault"
  if (Test-Path (Join-Path $VaultPath '.git')) {
    Note "Already a git repo, pulling"
    git -C $VaultPath pull --ff-only
    if ($LASTEXITCODE -ne 0) { Fail "pull failed. Resolve it by hand first." }
  }
  else {
    # Cloning into a non-empty directory fails, so clone beside it and move in.
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("aethrom-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
    git clone $VaultRepo $tmp
    if ($LASTEXITCODE -ne 0) { Fail "clone failed: $VaultRepo" }
    New-Item -ItemType Directory -Force -Path $VaultPath | Out-Null
    Get-ChildItem $tmp -Force | ForEach-Object {
      $target = Join-Path $VaultPath $_.Name
      if (Test-Path $target) { Note "skipped (already there): $($_.Name)" }
      else { Move-Item $_.FullName $target }
    }
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
  }
  Ok "vault ready: $VaultPath"
}
else {
  Step "Scaffolding a fresh vault"
  if (-not $UserName) { $UserName = Ask "  Your name" $env:USERNAME }
  if (-not $Companion) { $Companion = Ask "  Name for your AI companion" "Echo" }

  $template = Join-Path $RepoRoot 'template'
  if (-not (Test-Path $template)) { Fail "template/ not found: $template" }
  New-Item -ItemType Directory -Force -Path $VaultPath | Out-Null

  Get-ChildItem $template -Force | ForEach-Object {
    $target = Join-Path $VaultPath $_.Name
    if (Test-Path $target) { Note "skipped (already there): $($_.Name)" }
    else { Copy-Item $_.FullName $target -Recurse }
  }

  # The companion's memory folder is named after the companion.
  $memSrc = Join-Path $VaultPath ([char]0xD83D + [char]0xDD2E + " 850-Companion")
  $memDst = Join-Path $VaultPath ([char]0xD83D + [char]0xDD2E + " 850-$Companion")
  if ((Test-Path $memSrc) -and -not (Test-Path $memDst)) { Rename-Item $memSrc $memDst }

  # Resolve every placeholder.
  $today = Get-Date -Format 'yyyy-MM-dd'
  $venvPy = Join-Path $VaultPath '.claude\mem0-venv\Scripts\python.exe'
  $map = @{
    '{{OS_NAME}}'     = $OsName
    '{{USER_NAME}}'   = $UserName
    '{{COMPANION}}'   = $Companion
    '{{LANGUAGE}}'    = $Language
    '{{USER_BIO}}'    = "(fill this in inside CLAUDE.md)"
    '{{TODAY}}'       = $today
    '{{USER_ID}}'     = $UserName.ToLowerInvariant()
    '{{VAULT_PATH}}'  = $VaultPath
    '{{VENV_PYTHON}}' = $venvPy
  }
  Get-ChildItem $VaultPath -Recurse -File -Force |
  Where-Object { $_.Extension -in @('.md', '.sh', '.py', '.json') } |
  ForEach-Object {
    $raw = [System.IO.File]::ReadAllText($_.FullName)
    if ($raw -notmatch '\{\{') { return }
    foreach ($k in $map.Keys) { $raw = $raw.Replace($k, $map[$k]) }
    # 850-Companion is also referenced by path inside the hooks.
    $raw = $raw.Replace("850-Companion", "850-$Companion")
    [System.IO.File]::WriteAllText($_.FullName, $raw)
  }
  Ok "scaffolded and personalised"
}

# --- hooks ------------------------------------------------------------------
Step "Continuity hooks"

$claudeDir = Join-Path $VaultPath '.claude'
$hooksDir = Join-Path $claudeDir 'hooks'
if (-not (Test-Path $hooksDir)) {
  Fail "$hooksDir is missing. The vault you fetched does not look like an Aethrom vault."
}
New-Item -ItemType Directory -Force -Path (Join-Path $hooksDir '.state') | Out-Null

$settings = Join-Path $claudeDir 'settings.local.json'
if (Test-Path $settings) {
  Note "settings.local.json already exists, left alone"
}
else {
  # A cloned vault will not carry settings.local.json: it holds the API key and is
  # gitignored by design. Fall back to this repo's template so a pulled vault still
  # gets wired up.
  $winTemplate = Join-Path $claudeDir 'settings.windows.json'
  if (-not (Test-Path $winTemplate)) {
    $winTemplate = Join-Path $RepoRoot 'template\.claude\settings.windows.json'
    if (Test-Path $winTemplate) { Note "the vault carries no settings of its own (gitignored), generating from the template" }
  }
  if (-not (Test-Path $winTemplate)) { Fail "settings.windows.json found neither in the vault nor in the template." }

  $fwd = $VaultPath.Replace('\', '/')
  $raw = [System.IO.File]::ReadAllText($winTemplate)
  $raw = $raw.Replace('{{BASH_PATH}}', $bashPath.Replace('\', '/')).Replace('{{VAULT_PATH_FWD}}', $fwd)
  [System.IO.File]::WriteAllText($settings, $raw)
  Ok "settings.local.json written (Git Bash: $bashPath)"
}

# The POSIX variant does not work on Windows, and the Windows file is a template
# with placeholders, not something the vault should carry once it is resolved.
$posix = Join-Path $claudeDir 'settings.json'
if (Test-Path $posix) { Remove-Item $posix -Force; Note "removed settings.json (POSIX form), it does not work on Windows" }
$vaultWinTemplate = Join-Path $claudeDir 'settings.windows.json'
if (Test-Path $vaultWinTemplate) { Remove-Item $vaultWinTemplate -Force }

# --- prove the hook actually runs -------------------------------------------
Step "Verification"

$hookOut = & $bashPath (Join-Path $hooksDir 'session-start.sh') 2>&1 | Out-String
if ([string]::IsNullOrWhiteSpace($hookOut)) {
  Fail "session-start.sh printed nothing. The hook is broken and continuity dies silently. Fix this first."
}
try { $null = $hookOut | ConvertFrom-Json } catch { Fail "session-start.sh did not emit valid JSON:`n$hookOut" }
Ok "session-start.sh emits valid JSON"

$leftovers = @(Get-ChildItem $VaultPath -Recurse -File -Force |
  Where-Object { $_.Extension -in @('.md', '.sh', '.py', '.json') } |
  Where-Object { (Get-Content $_.FullName -Raw) -match '\{\{[A-Z_]+\}\}' })
if ($leftovers.Count -gt 0) {
  Write-Host "  Files with unresolved placeholders:" -ForegroundColor Yellow
  $leftovers | ForEach-Object { Note "  - $($_.FullName.Substring($VaultPath.Length + 1))" }
}
else { Ok "no unresolved placeholders" }

# --- launcher ---------------------------------------------------------------
if (-not $NoLauncher) {
  Step "Desktop shortcut"
  if (AskYesNo "  Create a desktop shortcut with a brain icon?" $true) {
    & (Join-Path $PSScriptRoot 'launcher-windows.ps1') -VaultName $OsName -VaultPath $VaultPath
  }
}

# --- scheduled backup -------------------------------------------------------
# Only offered when the vault has a remote to push to, since backup.sh needs one.
$backupScript = Join-Path $claudeDir 'backup.sh'
if (-not $NoBackup -and (Test-Path $backupScript)) {
  Step "Hourly backup"
  git -C $VaultPath rev-parse '@{u}' *> $null
  if ($LASTEXITCODE -eq 0) {
    Note "backup.sh commits and pushes whatever changed, and pulls first so a push never gets rejected."
    if (AskYesNo "  Schedule it to run hourly?" $true) {
      & (Join-Path $PSScriptRoot 'schedule-backup.ps1') -VaultPath $VaultPath -VaultName $OsName -BashPath $bashPath
    }
  }
  else {
    Note "the vault has no upstream branch yet, so there is nothing to push to."
    Note "push it once (git push -u origin HEAD), then run:"
    Note "  powershell -ExecutionPolicy Bypass -File scripts\schedule-backup.ps1 -VaultPath `"$VaultPath`" -VaultName `"$OsName`""
  }
}

# --- done -------------------------------------------------------------------
Write-Host ""
Write-Host "  Setup complete." -ForegroundColor Green
Write-Host "  Vault: $VaultPath"
Write-Host ""
Write-Host "  Next:"
Write-Host "    1. Open Obsidian and pick this folder as a vault (the shortcut works after that)."
Write-Host "    2. Run 'claude' in the same folder."
Write-Host "    3. Say something, /exit, open it again. It will remember the last session."
Write-Host ""
Write-Host "  Optional: semantic memory, see the header of .claude/semantic-memory.py,"
Write-Host "  and scripts\install-hermes.ps1 to share the vault with hermes."
Write-Host ""
