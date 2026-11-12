# Builds dist\YT Downloader.exe with Deno and ffmpeg packed inside,
# so end users only need the single .exe.
#
#   powershell -ExecutionPolicy Bypass -File build.ps1            # full build
#   powershell -ExecutionPolicy Bypass -File build.ps1 -ToolsOnly # just fetch deno/ffmpeg into bin\
#
# Running from source also picks up bin\deno.exe and bin\ffmpeg.exe automatically.
# Delete bin\ to force fresh copies of deno/ffmpeg.

param([switch]$ToolsOnly)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # makes Invoke-WebRequest much faster
Set-Location $PSScriptRoot

$bin = Join-Path $PSScriptRoot 'bin'
New-Item -ItemType Directory -Force $bin | Out-Null
$tmp = Join-Path $env:TEMP 'ytdownloader-build'
New-Item -ItemType Directory -Force $tmp | Out-Null

function Get-ExeFromZip($url, $exeName) {
    $zip = Join-Path $tmp "$exeName.zip"
    $out = Join-Path $tmp "$exeName-extract"
    Write-Host "Downloading $exeName ..."
    Invoke-WebRequest $url -OutFile $zip
    if (Test-Path $out) { Remove-Item $out -Recurse -Force }
    Expand-Archive $zip -DestinationPath $out
    $exe = Get-ChildItem $out -Recurse -Filter $exeName | Select-Object -First 1
    if (-not $exe) { throw "$exeName not found in $url" }
    Copy-Item $exe.FullName (Join-Path $bin $exeName) -Force
}

if (-not (Test-Path "$bin\deno.exe")) {
    Get-ExeFromZip 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip' 'deno.exe'
}
if (-not (Test-Path "$bin\ffmpeg.exe")) {
    Get-ExeFromZip 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' 'ffmpeg.exe'
}
if ($ToolsOnly) { Write-Host "Tools ready in bin\"; exit 0 }

Write-Host "Installing/updating Python packages ..."
py -m pip install -U -r requirements.txt -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "Creating icon ..."
New-Item -ItemType Directory -Force assets | Out-Null
py -m ytdownloader.ui.icons assets\icon.ico
if ($LASTEXITCODE -ne 0) { throw "icon export failed" }

Write-Host "Building executable ..."
py -m PyInstaller --onefile --windowed --clean --noconfirm `
    --name "YT Downloader" `
    --icon assets\icon.ico `
    --collect-data yt_dlp_ejs `
    --add-binary "bin\deno.exe;." `
    --add-binary "bin\ffmpeg.exe;." `
    --exclude-module tkinter `
    run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host ""
Write-Host "Done: dist\YT Downloader.exe (Deno and ffmpeg included)"
