# Install k6 / JMeter to PERF_TOOLS_ROOT (default C:\perf-tools)
# Usage: powershell -ExecutionPolicy Bypass -File install_perf_tools.ps1 [-K6Only] [-JMeterOnly] [-SkipJava]

param(
    [string]$InstallRoot = $(if ($env:PERF_TOOLS_ROOT) { $env:PERF_TOOLS_ROOT } else { "C:\perf-tools" }),
    [string]$JMeterVersion = "5.6.3",
    [switch]$K6Only,
    [switch]$JMeterOnly,
    [switch]$SkipJava,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$K6Dir = Join-Path $InstallRoot "k6"
$JMeterDir = Join-Path $InstallRoot "jmeter"
$JavaDir = Join-Path $InstallRoot "java"
$Tmp = Join-Path $env:TEMP "perf-tools-install"
New-Item -ItemType Directory -Force -Path $K6Dir, $JMeterDir, $Tmp | Out-Null

function Install-K6Tool {
    $k6Exe = Join-Path $K6Dir "k6.exe"
    if (Test-Path $k6Exe) {
        Write-Host "k6 already installed: $k6Exe"
        return
    }
    $wingetK6 = "C:\Program Files\k6\k6.exe"
    if (Test-Path $wingetK6) {
        Copy-Item -Force $wingetK6 $k6Exe
        Write-Host "k6 copied from winget: $k6Exe"
        return
    }
    Write-Host "Installing k6 via winget ..."
    winget install --id GrafanaLabs.k6 --accept-package-agreements --accept-source-agreements --location $K6Dir
    if (-not (Test-Path $k6Exe) -and (Test-Path $wingetK6)) {
        Copy-Item -Force $wingetK6 $k6Exe
    }
    if (-not (Test-Path $k6Exe)) { throw "k6 install failed" }
    Write-Host "k6 installed: $k6Exe"
}

function Test-JMeterVersion {
    param([string]$Dir, [string]$Expected)
    $doc = Join-Path $Dir "printable_docs\download_jmeter.html"
    if (Test-Path $doc) {
        $hit = Select-String -Path $doc -Pattern "Apache JMeter $Expected" -Quiet
        if ($hit) { return $true }
    }
    return $false
}

function Install-JMeterTool {
    $bat = Join-Path $JMeterDir "bin\jmeter.bat"
    if ((Test-Path $bat) -and (Test-JMeterVersion -Dir $JMeterDir -Expected $JMeterVersion) -and (-not $Force)) {
        Write-Host "JMeter $JMeterVersion already installed: $bat"
        return
    }
    if ((Test-Path $JMeterDir) -and $Force) {
        Remove-Item -Recurse -Force $JMeterDir
    }
    $zipName = "apache-jmeter-$JMeterVersion.zip"
    $zip = Join-Path $Tmp $zipName
    if (-not (Test-Path $zip) -or (Get-Item $zip).Length -lt 80000000) {
        $url = "https://archive.apache.org/dist/jmeter/binaries/$zipName"
        Write-Host "Downloading JMeter $JMeterVersion ..."
        curl.exe --ssl-no-revoke -L -o $zip $url
    }
    if (-not (Test-Path $zip)) { throw "JMeter download failed" }
    $extract = Join-Path $Tmp "jmeter-extract"
    if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
    New-Item -ItemType Directory -Force -Path $extract | Out-Null
    Expand-Archive -Path $zip -DestinationPath $extract -Force
    $folder = Get-ChildItem -Path $extract -Directory -Filter "apache-jmeter-$JMeterVersion" | Select-Object -First 1
    if (-not $folder) {
        $folder = Get-ChildItem -Path $extract -Directory -Filter "apache-jmeter-*" | Select-Object -First 1
    }
    if (-not $folder) { throw "JMeter extract folder not found" }
    if (Test-Path $JMeterDir) { Remove-Item -Recurse -Force $JMeterDir }
    Move-Item $folder.FullName $JMeterDir
    if (-not (Test-JMeterVersion -Dir $JMeterDir -Expected $JMeterVersion)) {
        throw "Installed JMeter version mismatch (expected $JMeterVersion)"
    }
    Write-Host "JMeter $JMeterVersion installed: $bat"
}

function Install-JavaForJMeter {
    if ($SkipJava) { return }
    $javaExe = Get-ChildItem -Path $JavaDir -Recurse -Filter "java.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "\\bin\\java\.exe$" } | Select-Object -First 1
    if ($javaExe) {
        Write-Host "Java already present: $($javaExe.FullName)"
        return
    }
    $sysJava = Get-Command java -ErrorAction SilentlyContinue
    if ($sysJava) {
        Write-Host "Java on PATH: $($sysJava.Source)"
        return
    }
    Write-Host "Installing Temurin JDK 17 (JMeter requires Java) ..."
    winget install --id EclipseAdoptium.Temurin.17.JDK `
        --accept-package-agreements --accept-source-agreements `
        --location $JavaDir 2>&1 | Out-Host
}

$installK6 = (-not $JMeterOnly)
$installJm = (-not $K6Only)

if ($installK6) { Install-K6Tool }
if ($installJm) {
    Install-JMeterTool
    Install-JavaForJMeter
}

Write-Host ""
Write-Host "Install root: $InstallRoot"
Write-Host "  k6:     $K6Dir\k6.exe"
Write-Host "  JMeter: $JMeterDir\bin\jmeter.bat (v$JMeterVersion)"
Write-Host "  Java:   $JavaDir (or system PATH)"
Write-Host ""
Write-Host "Verify:"
if ($installK6 -and (Test-Path (Join-Path $K6Dir "k6.exe"))) {
    & (Join-Path $K6Dir "k6.exe") version
}
if ($installJm -and (Test-Path (Join-Path $JMeterDir "bin\jmeter.bat"))) {
    $env:JAVA_HOME = $null
    $j = Get-ChildItem -Path $JavaDir -Recurse -Filter "java.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "\\bin\\java\.exe$" } | Select-Object -First 1
    if ($j) {
        $env:JAVA_HOME = Split-Path (Split-Path $j.FullName -Parent) -Parent
        if (-not (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
            $env:JAVA_HOME = Split-Path $j.FullName -Parent
        }
    }
    & (Join-Path $JMeterDir "bin\jmeter.bat") -v 2>&1 | Select-Object -First 2
}
