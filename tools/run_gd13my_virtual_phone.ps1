[CmdletBinding()]
param(
    [string]$OutputDirectory,
    [switch]$LcdBench,
    [switch]$OwnedWindow,
    [ValidateRange(1, 1800)][int]$Seconds = 230
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root 'build\gd13my-ce-video-focus'
$image = 'gd13my-aa-ce-video-short-read.img'
$manifest = 'image-short-read.json'
if ($LcdBench) {
    $build = Join-Path $root 'build\gd13my-virtual-lcd'
    $image = 'virtual-lcd.img'
    $manifest = 'image.json'
}
if ($OwnedWindow) {
    if ($LcdBench) { throw 'Select one virtual-phone test mode.' }
    $build = Join-Path $root 'build\gd13my-ce-owned-window'
    $image = 'gd13my-aa-owned-window.img'
    $manifest = 'image.json'
}
$python = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv\Scripts\python.exe'
$compiler = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools\arm-gnu-14.2\bin\arm-none-eabi-gcc.exe'
$disk = Join-Path $env:LOCALAPPDATA 'i30-gd13my\gd13my-media-v2.img'
$diskPackages = Join-Path $PSScriptRoot 'venv\gd13my-disk\Lib\site-packages'
$openssl = Join-Path $env:ProgramFiles 'Git\usr\bin\openssl.exe'
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $root ('build\gd13my-virtual-phone\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}

$verifyArgs = @(
    (Join-Path $PSScriptRoot 'verify_gd13my_virtual_phone.py'),
    '--image', (Join-Path $build $image),
    '--manifest', (Join-Path $build $manifest),
    '--disk', $disk, '--compiler', $compiler, '--openssl', $openssl,
    '--output', $OutputDirectory, '--seconds', $Seconds
)
if ($LcdBench) { $verifyArgs += '--lcd-bench' }
if ($OwnedWindow) { $verifyArgs += '--owned-window' }
$priorPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = if ($priorPythonPath) { "$diskPackages;$priorPythonPath" } else { $diskPackages }
    & $python @verifyArgs
    $verifyExit = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $priorPythonPath
}
exit $verifyExit
