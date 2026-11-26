[CmdletBinding()]
param(
    [string]$UsbPort = 'auto',
    [ValidateRange(1, 86400)][int]$Seconds = 7200,
    [ValidateRange(1.0, 64.0)][double]$GuestClockMHz = 4.5,
    [ValidateRange(1.0, 64.0)][double]$UsbClockMHz,
    [switch]$AutoCalibrate,
    [switch]$FastStorage,
    [switch]$BootTrace,
    [switch]$NativeTls = $true,
    [switch]$OwnedWindowCandidate,
    [string]$StockProjectionImage,
    [string]$DiskPath,
    [string]$OutputDirectory,
    [string]$StatePath
)

$ErrorActionPreference = 'Stop'
$phaseRoot = Split-Path -Parent $PSScriptRoot
$phaseBuild = Join-Path $phaseRoot 'build\gd13my-native-menu'
$phasePython = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv\Scripts\python.exe'
$phaseDisk = if ($DiskPath) { $DiskPath } else { Join-Path $env:LOCALAPPDATA 'i30-gd13my\gd13my-media-v2.img' }
$phaseApp = Join-Path $phaseBuild 'gd13my-aa-native-menu.img'
$clockArgs = @()
if (-not $StockProjectionImage -and -not $OwnedWindowCandidate -and -not $PSBoundParameters.ContainsKey('NativeTls')) {
    $stockRoot = Join-Path $phaseRoot 'build\gd13my-native-oem-screen'
    foreach ($stockBuild in @((Join-Path $stockRoot 'phone-wait'), $stockRoot)) {
        $stockImage = Join-Path $stockBuild 'gd13my-aa-stock-display.img'
        if ((Test-Path -LiteralPath $stockImage -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $stockBuild 'image.json') -PathType Leaf)) {
            $StockProjectionImage = $stockImage
            break
        }
    }
}
if ($StockProjectionImage) {
    $phaseApp = (Get-Item -LiteralPath $StockProjectionImage).FullName
    $phaseBuild = Split-Path -Parent $phaseApp
    $phaseManifest = Get-Content -LiteralPath (Join-Path $phaseBuild 'image.json') -Raw | ConvertFrom-Json
    if (-not $phaseManifest.stock_display_sha256 -or $phaseManifest.emulator_utc_offset -le 0) {
        throw 'The DiskA manifest is missing the stock display patches or the UTC mailbox.'
    }
    if (!$PSBoundParameters.ContainsKey('UsbClockMHz')) {
        $UsbClockMHz = if ($phaseManifest.tls_profile -eq 'aare') { 12.0 } else { 64.0 }
    }
    $clockArgs = @('--host-utc-offset', [string]$phaseManifest.emulator_utc_offset)
    $AutoCalibrate = $true
} elseif ($NativeTls -or $OwnedWindowCandidate) {
    $phaseBuild = Join-Path $phaseRoot 'build\gd13my-ce-video-focus'
    $phaseApp = Join-Path $phaseBuild 'gd13my-aa-ce-video-short-read.img'
    $manifestName = 'image-short-read.json'
    if ($OwnedWindowCandidate) {
        $phaseBuild = Join-Path $phaseRoot 'build\gd13my-ce-owned-window'
        $phaseApp = Join-Path $phaseBuild 'gd13my-aa-owned-window.img'
        $manifestName = 'image.json'
    }
    $phaseManifest = Get-Content -LiteralPath (Join-Path $phaseBuild $manifestName) -Raw | ConvertFrom-Json
    if ($phaseManifest.emulator_utc_offset -le 0) {
        throw 'GD13MY emulator UTC mailbox is missing from the image manifest.'
    }
    if (!$PSBoundParameters.ContainsKey('UsbClockMHz')) { $UsbClockMHz = 64.0 }
    $clockArgs = @('--host-utc-offset', [string]$phaseManifest.emulator_utc_offset)
}
if ($UsbClockMHz) {
    $clockArgs += @('--usb-clock-mhz', $UsbClockMHz.ToString([Globalization.CultureInfo]::InvariantCulture))
}
$phaseNavi = Join-Path $phaseRoot 'firmware\extracted\GD13MY\APP\00d12869_GDdNavi.exe'
$phaseRom = Join-Path $phaseRoot 'firmware\extracted\GD13MY\BSP\0002dfc7_kernel'
$phaseViewer = Join-Path $PSScriptRoot 'view_gd13my.py'

foreach ($phaseFile in @($phasePython, $phaseDisk, $phaseApp, $phaseNavi, $phaseRom)) {
    if (-not (Test-Path -LiteralPath $phaseFile -PathType Leaf)) {
        throw "GD13MY emulator input is missing ($phaseFile)"
    }
}
if (-not $StatePath) {
    $StatePath = Join-Path $phaseBuild 'user-diska.sqlite3'
}

$outputDir = if ($OutputDirectory) { $OutputDirectory } else { Join-Path $phaseRoot 'build\gd13my-boot' }
$tempDir = Join-Path $phaseRoot 'build\temp'
[void][IO.Directory]::CreateDirectory($tempDir)
if ($FastStorage) {
    $runtimePath = Join-Path $env:LOCALAPPDATA 'i30-gd13my\phase78-runtime'
    [void][IO.Directory]::CreateDirectory($runtimePath)
    $runtimeDrive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($runtimePath))
    $cached = @{}
    foreach ($sourcePath in @($phaseApp, $phaseNavi, $phaseRom)) {
        $source = Get-Item -LiteralPath $sourcePath
        $destination = Join-Path $runtimePath "$($source.Name)-$($source.Length)-$($source.LastWriteTimeUtc.Ticks)"
        if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
            if ($runtimeDrive.AvailableFreeSpace -lt ($source.Length + 16MB)) {
                $cached[$sourcePath] = $source.FullName
                continue
            }
            $temporary = Join-Path $runtimePath "$([Guid]::NewGuid()).pending"
            try {
                [IO.File]::Copy($source.FullName, $temporary)
                if ((Get-Item -LiteralPath $temporary).Length -ne $source.Length) {
                    throw "GD13MY input changed during copy ($sourcePath)"
                }
                try {
                    [IO.File]::Move($temporary, $destination)
                } catch [IO.IOException] {
                    if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) { throw }
                }
            } finally {
                if (Test-Path -LiteralPath $temporary -PathType Leaf) {
                    Remove-Item -LiteralPath $temporary
                }
            }
        }
        $cached[$sourcePath] = $destination
    }
    $phaseApp, $phaseNavi, $phaseRom = $cached[$phaseApp], $cached[$phaseNavi], $cached[$phaseRom]
}

$guestClock = $GuestClockMHz.ToString([Globalization.CultureInfo]::InvariantCulture)
$viewerArgs = @($phaseViewer, '--image', $phaseRom, '--disk', $phaseDisk, '--app-volume', $phaseApp, '--save-state', $StatePath,
                '--micom-display', 'navi', '--assist-navi-start', '--assist-touch-calibration',
                '--software-gl-app', $phaseNavi, '--guest-clock-mhz', $guestClock, '--seconds', $Seconds,
                '--output-dir', $outputDir)
$viewerArgs += $clockArgs
if ($UsbPort) {
    $viewerArgs += @('--usb-port', $UsbPort, '--usb-on-test')
}
if ($AutoCalibrate) {
    $viewerArgs += '--auto-calibrate'
}
if ($BootTrace) {
    $viewerArgs += '--boot-trace'
}
$previousTemp, $previousTmp = $env:TEMP, $env:TMP
try {
    $env:TEMP = $tempDir
    $env:TMP = $tempDir
    & $phasePython @viewerArgs
    $viewerExit = $LASTEXITCODE
} finally {
    $env:TEMP, $env:TMP = $previousTemp, $previousTmp
}
exit $viewerExit
