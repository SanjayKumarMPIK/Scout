# Builds dist\installer\ScoutSetup-<version>.exe
#   Usage (from repo root):  powershell -ExecutionPolicy Bypass -File installer\build.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# ── Version from scout/__init__.py ─────────────────────────────────────
$Version = (Select-String -Path "scout\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
Write-Host "==> Building Scout v$Version" -ForegroundColor Cyan

# ── 1. Python deps + PyInstaller ───────────────────────────────────────
Write-Host "==> Installing dependencies" -ForegroundColor Cyan
python -m pip install --quiet --upgrade pyinstaller
python -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# ── 2. PyInstaller -> dist\scout\scout.exe ─────────────────────────────
Write-Host "==> Running PyInstaller" -ForegroundColor Cyan
python -m PyInstaller installer\scout.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# ── 3. Locate (or install) Inno Setup ──────────────────────────────────
$IsccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    Write-Host "==> Inno Setup not found, installing via winget" -ForegroundColor Yellow
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    $Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $Iscc) { throw "Inno Setup install failed. Install it from https://jrsoftware.org/isdl.php" }
}

# ── 4. Compile installer ───────────────────────────────────────────────
Write-Host "==> Compiling installer" -ForegroundColor Cyan
& $Iscc "/DAppVersion=$Version" "installer\scout.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed" }

$Out = Join-Path $Root "dist\installer\ScoutSetup-$Version.exe"
Write-Host "`n==> Done: $Out" -ForegroundColor Green
