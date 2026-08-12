# Aethrom setup wizard (Windows).
#
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
#
# Asks where the vault should live, pulls an existing vault repo if you have one,
# scaffolds a fresh vault from template/ if you do not, wires the hooks for this
# platform and offers the desktop launcher.
#
# Idempotent: it never overwrites an existing vault without asking.
[CmdletBinding()]
param(
  [string]$VaultRepo,
  [string]$VaultPath,
  [string]$OsName,
  [string]$UserName,
  [string]$Companion,
  [switch]$NoLauncher,
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
  $hint = if ($Default) { "[E/h]" } else { "[e/H]" }
  while ($true) {
    $a = (Read-Host "$Question $hint").Trim().ToLowerInvariant()
    if ($a -eq '') { return $Default }
    if ($a -in @('e', 'evet', 'y', 'yes')) { return $true }
    if ($a -in @('h', 'hayir', 'hayır', 'n', 'no')) { return $false }
  }
}

function Fail([string]$Message) { Write-Host "`n  HATA: $Message" -ForegroundColor Red; exit 1 }
function Step([string]$Message) { Write-Host "`n> $Message" -ForegroundColor Cyan }
function Ok([string]$Message) { Write-Host "  $Message" -ForegroundColor Green }
function Note([string]$Message) { Write-Host "  $Message" -ForegroundColor DarkGray }

Write-Host ""
Write-Host "  Aethrom kurulum sihirbazi" -ForegroundColor White
Write-Host "  Oturumlar arasi hafizasi olan bir ikinci beyin kurar."

# --- prerequisites ----------------------------------------------------------
Step "Gereksinimler"

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) { Fail "git bulunamadi. https://git-scm.com/download/win adresinden kur." }

# The hooks are bash scripts. System32\bash.exe is the WSL launcher and cannot
# see the vault at a Windows path, so Git Bash is what we need.
$bashPath = Join-Path (Split-Path -Parent (Split-Path -Parent $gitCmd.Source)) 'bin\bash.exe'
if (-not (Test-Path $bashPath)) {
  $bashPath = $gitCmd.Source -replace '\\cmd\\git\.exe$', '\bin\bash.exe'
}
if (-not (Test-Path $bashPath)) { Fail "Git Bash bulunamadi (aranan: $bashPath)." }
& $bashPath -c "echo ok" *> $null
if ($LASTEXITCODE -ne 0) { Fail "Git Bash calismiyor: $bashPath" }
Ok "git ve Git Bash hazir"

if (-not (Test-Path "$env:LOCALAPPDATA\Programs\Obsidian\Obsidian.exe")) {
  Note "Obsidian kurulu gorunmuyor. Vault yine kurulur; sonra: winget install Obsidian.Obsidian"
}
else { Ok "Obsidian kurulu" }

# --- existing vault or a new one -------------------------------------------
Step "Vault kaynagi"

$alreadyInstalled = $false
if ($VaultPath -and (Test-Path (Join-Path $VaultPath '.claude\hooks'))) {
  # Re-run against a vault that is already in place: skip straight to wiring.
  $alreadyInstalled = $true
  Ok "$VaultPath zaten bir Aethrom vault'u, sadece baglantilar kontrol edilecek"
}

if (-not $VaultRepo -and -not $NonInteractive -and -not $alreadyInstalled) {
  Write-Host "  Hazir bir vault repon varsa URL'sini gir (bos birak = sifirdan kur)."
  $VaultRepo = Ask "  Vault repo URL'si" ""
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
  $OsName = Ask "  Sistemin adi" $default
}
if (-not $VaultPath) {
  $VaultPath = Ask "  Vault yolu" (Join-Path ([Environment]::GetFolderPath('MyDocuments')) $OsName)
}

if ((Test-Path $VaultPath) -and (-not $alreadyInstalled)) {
  $existing = @(Get-ChildItem $VaultPath -Force -ErrorAction SilentlyContinue)
  if ($existing.Count -gt 0) {
    Write-Host "  $VaultPath zaten var ve $($existing.Count) ogesi mevcut:" -ForegroundColor Yellow
    $existing | Select-Object -First 8 | ForEach-Object { Note "  - $($_.Name)" }
    if (-not (AskYesNo "  Devam edilsin mi? (var olan dosyalarin uzerine YAZILMAZ)" $false)) {
      Fail "Iptal edildi. Baska bir yol sec."
    }
  }
}

# --- fetch or scaffold ------------------------------------------------------
if ($alreadyInstalled) {
  Step "Var olan vault kullaniliyor"
  Note $VaultPath
}
elseif ($cloning) {
  Step "Vault cekiliyor"
  if (Test-Path (Join-Path $VaultPath '.git')) {
    Note "Zaten bir git deposu, pull ediliyor"
    git -C $VaultPath pull --ff-only
    if ($LASTEXITCODE -ne 0) { Fail "pull basarisiz. Once elle coz." }
  }
  else {
    # Cloning into a non-empty directory fails, so clone beside it and move in.
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("aethrom-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
    git clone $VaultRepo $tmp
    if ($LASTEXITCODE -ne 0) { Fail "clone basarisiz: $VaultRepo" }
    New-Item -ItemType Directory -Force -Path $VaultPath | Out-Null
    Get-ChildItem $tmp -Force | ForEach-Object {
      $target = Join-Path $VaultPath $_.Name
      if (Test-Path $target) { Note "atlandi (zaten var): $($_.Name)" }
      else { Move-Item $_.FullName $target }
    }
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
  }
  Ok "vault hazir: $VaultPath"
}
else {
  Step "Sifirdan vault kuruluyor"
  if (-not $UserName) { $UserName = Ask "  Ismin" $env:USERNAME }
  if (-not $Companion) { $Companion = Ask "  AI ortaginin adi" "Echo" }

  $template = Join-Path $RepoRoot 'template'
  if (-not (Test-Path $template)) { Fail "template/ bulunamadi: $template" }
  New-Item -ItemType Directory -Force -Path $VaultPath | Out-Null

  Get-ChildItem $template -Force | ForEach-Object {
    $target = Join-Path $VaultPath $_.Name
    if (Test-Path $target) { Note "atlandi (zaten var): $($_.Name)" }
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
    '{{USER_BIO}}'    = "(bunu CLAUDE.md icinde doldur)"
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
  Ok "iskelet kuruldu ve kisisellestirildi"
}

# --- hooks ------------------------------------------------------------------
Step "Sureklilik hook'lari"

$claudeDir = Join-Path $VaultPath '.claude'
$hooksDir = Join-Path $claudeDir 'hooks'
if (-not (Test-Path $hooksDir)) {
  Fail "$hooksDir yok. Cekilen repo bir Aethrom vault'u degil gibi gorunuyor."
}
New-Item -ItemType Directory -Force -Path (Join-Path $hooksDir '.state') | Out-Null

$settings = Join-Path $claudeDir 'settings.local.json'
if (Test-Path $settings) {
  Note "settings.local.json zaten var, dokunulmadi"
}
else {
  # A cloned vault will not carry settings.local.json: it holds the API key and is
  # gitignored by design. Fall back to this repo's template so a pulled vault still
  # gets wired up.
  $winTemplate = Join-Path $claudeDir 'settings.windows.json'
  if (-not (Test-Path $winTemplate)) {
    $winTemplate = Join-Path $RepoRoot 'template\.claude\settings.windows.json'
    if (Test-Path $winTemplate) { Note "vault kendi settings'ini tasimiyor (gitignore), sablondan uretiliyor" }
  }
  if (-not (Test-Path $winTemplate)) { Fail "settings.windows.json ne vault'ta ne sablonda bulundu." }

  $fwd = $VaultPath.Replace('\', '/')
  $raw = [System.IO.File]::ReadAllText($winTemplate)
  $raw = $raw.Replace('{{BASH_PATH}}', $bashPath.Replace('\', '/')).Replace('{{VAULT_PATH_FWD}}', $fwd)
  [System.IO.File]::WriteAllText($settings, $raw)
  Ok "settings.local.json yazildi (Git Bash: $bashPath)"
}

# The POSIX variant does not work on Windows, and the Windows file is a template
# with placeholders, not something the vault should carry once it is resolved.
$posix = Join-Path $claudeDir 'settings.json'
if (Test-Path $posix) { Remove-Item $posix -Force; Note "settings.json (POSIX) kaldirildi, Windows'ta calismaz" }
$vaultWinTemplate = Join-Path $claudeDir 'settings.windows.json'
if (Test-Path $vaultWinTemplate) { Remove-Item $vaultWinTemplate -Force }

# --- prove the hook actually runs -------------------------------------------
Step "Dogrulama"

$hookOut = & $bashPath (Join-Path $hooksDir 'session-start.sh') 2>&1 | Out-String
if ([string]::IsNullOrWhiteSpace($hookOut)) {
  Fail "session-start.sh hicbir sey yazmadi. Hook bozuk, sureklilik sessizce olmez. Once bunu coz."
}
try { $null = $hookOut | ConvertFrom-Json } catch { Fail "session-start.sh gecerli JSON uretmedi:`n$hookOut" }
Ok "session-start.sh gecerli JSON uretiyor"

$leftovers = @(Get-ChildItem $VaultPath -Recurse -File -Force |
  Where-Object { $_.Extension -in @('.md', '.sh', '.py', '.json') } |
  Where-Object { (Get-Content $_.FullName -Raw) -match '\{\{[A-Z_]+\}\}' })
if ($leftovers.Count -gt 0) {
  Write-Host "  Doldurulmamis placeholder kalan dosyalar:" -ForegroundColor Yellow
  $leftovers | ForEach-Object { Note "  - $($_.FullName.Substring($VaultPath.Length + 1))" }
}
else { Ok "doldurulmamis placeholder yok" }

# --- launcher ---------------------------------------------------------------
if (-not $NoLauncher) {
  Step "Masaustu kisayolu"
  if (AskYesNo "  Beyin ikonlu masaustu kisayolu olusturulsun mu?" $true) {
    & (Join-Path $PSScriptRoot 'launcher-windows.ps1') -VaultName $OsName -VaultPath $VaultPath
  }
}

# --- done -------------------------------------------------------------------
Write-Host ""
Write-Host "  Kurulum tamam." -ForegroundColor Green
Write-Host "  Vault: $VaultPath"
Write-Host ""
Write-Host "  Sirasiyla:"
Write-Host "    1. Obsidian'i ac ve bu klasoru vault olarak sec (kisayol bundan sonra calisir)."
Write-Host "    2. Ayni klasorde 'claude' calistir."
Write-Host "    3. Bir sey konus, /exit yap, tekrar ac. Gecen oturumu hatirlayacak."
Write-Host ""
Write-Host "  Istege bagli: semantik hafiza icin .claude/semantic-memory.py dosyasinin basindaki"
Write-Host "  adimlar, ve hermes ile paylasim icin scripts\install-hermes.ps1"
Write-Host ""
