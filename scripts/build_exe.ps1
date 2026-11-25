# Build standalone single-file Windows EXE for 开开陪玩
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = "python"
if (Get-Command py -ErrorAction SilentlyContinue) {
    $Python = "py"
    $PyPrefix = @("-3")
} else {
    $PyPrefix = @()
}

Write-Host "Building 开开陪玩.exe ..."
& $Python @PyPrefix -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "开开陪玩" `
    --icon "assets\app_icon.ico" `
    --add-data "assets\sprites_v5;assets\sprites_v5" `
    --add-data "assets\app_icon.ico;assets" `
    --exclude-module tkinter `
    --exclude-module matplotlib `
    --exclude-module scipy `
    --exclude-module pandas `
    --exclude-module unittest `
    "src\desktop_pet.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host "Build succeeded: $ProjectRoot\dist\开开陪玩.exe"
