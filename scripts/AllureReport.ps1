# Shared Allure helpers for run_pytest.ps1 / run_pytest_ui.ps1 / generate.ps1

function Ensure-JavaHomeForAllure {
    if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
        $env:Path = "$(Join-Path $env:JAVA_HOME 'bin');$env:Path"
        return
    }
    $candidates = @(
        "C:\Program Files\Microsoft\jdk-*",
        "C:\Program Files\Eclipse Adoptium\jdk-*",
        "C:\Program Files\Java\jdk-*"
    )
    foreach ($pattern in $candidates) {
        $jdk = Get-ChildItem $pattern -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            Select-Object -First 1
        if ($jdk -and (Test-Path (Join-Path $jdk.FullName "bin\java.exe"))) {
            $env:JAVA_HOME = $jdk.FullName
            $env:Path = "$(Join-Path $jdk.FullName 'bin');$env:Path"
            Write-Host "[allure] JAVA_HOME=$($env:JAVA_HOME)" -ForegroundColor DarkCyan
            return
        }
    }
}

function Ensure-NodeNpmOnPath {
    $nodeDir = "C:\Program Files\nodejs"
    if (Test-Path $nodeDir) {
        $env:Path = "$nodeDir;$env:APPDATA\npm;$env:Path"
    }
}

function Get-AllureCommand {
    $cmd = Get-Command allure -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $npmAllure = Join-Path $env:APPDATA "npm\allure.cmd"
    if (Test-Path $npmAllure) { return $npmAllure }

    $root = Split-Path $PSScriptRoot -Parent
    if (-not $root) { return $null }
    $bat = Get-ChildItem (Join-Path $root "tools\allure") -Recurse -Filter "allure.bat" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($bat) { return $bat.FullName }
    return $null
}

function Get-AllureResultsDir {
    param([string]$Root)
    $raw = if ($env:ALLURE_RESULTS_DIR) { $env:ALLURE_RESULTS_DIR } else { "output/allure-results" }
    $p = [System.IO.Path]::GetFullPath((Join-Path $Root $raw))
    New-Item -ItemType Directory -Force -Path $p | Out-Null
    return $p
}

function Get-AllureHtmlDir {
    param([string]$Root)
    $raw = if ($env:ALLURE_HTML_DIR) { $env:ALLURE_HTML_DIR } else { "output/allure-report" }
    return [System.IO.Path]::GetFullPath((Join-Path $Root $raw))
}

function Test-AllureEnabled {
    param([switch]$AllureSwitch)
    if ($AllureSwitch) { return $true }
    $v = if ($env:ALLURE) { $env:ALLURE.Trim().ToLowerInvariant() } else { "" }
    return $v -in @("1", "true", "yes", "on")
}

function Resolve-AllureBusinessFromArgs {
    param(
        [string[]]$PytestArgs,
        [string]$Default = "通用业务"
    )
    foreach ($a in $PytestArgs) {
        $target = ($a -split '::')[0]
        if ($target -notmatch '\.(py|md)$') { continue }
        $base = [System.IO.Path]::GetFileNameWithoutExtension($target).ToLowerInvariant()
        if ($base -match 'mcp|_ui_|ui_smoke') {
            return "UI 控制台"
        }
        if ($base -match 'api_smoke|_smoke$') {
            return "API 冒烟"
        }
    }
    return $Default
}

function Set-AllureReportContext {
    param(
        [string]$TestType,
        [string[]]$PytestArgs,
        [string]$DefaultBusiness
    )
    $env:ALLURE_TEST_TYPE = $TestType
    if (-not $env:ALLURE_BUSINESS) {
        $env:ALLURE_BUSINESS = Resolve-AllureBusinessFromArgs -PytestArgs $PytestArgs -Default $DefaultBusiness
    }
}

function Write-AllureEnvironment {
    param([string]$ResultsDir)
    if (-not (Test-Path $ResultsDir)) { return }
    $props = @(
        "Test-Type=$($env:ALLURE_TEST_TYPE)",
        "Business=$($env:ALLURE_BUSINESS)",
        "Report-Time=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    )
    $path = Join-Path $ResultsDir "environment.properties"
    $props | Set-Content -Path $path -Encoding UTF8
}

function Add-AllurePytestArgs {
    param(
        [string[]]$PytestArgs,
        [string]$ResultsDir
    )
    $hasDir = $false
    for ($i = 0; $i -lt $PytestArgs.Count; $i++) {
        $a = $PytestArgs[$i]
        if ($a -eq "--alluredir" -or $a -like "--alluredir=*") { $hasDir = $true; break }
    }
    if ($hasDir) { return $PytestArgs }
    return @($PytestArgs + @("--alluredir=$ResultsDir", "--clean-alluredir"))
}

function Invoke-AllurePostPytest {
    param(
        [string]$Root,
        [string]$ResultsDir,
        [int]$PytestExitCode
    )

    Write-Host ""
    Write-Host "[allure] results: $ResultsDir" -ForegroundColor Cyan
    Write-Host "[allure] test_type=$($env:ALLURE_TEST_TYPE) business=$($env:ALLURE_BUSINESS)" -ForegroundColor Cyan

    Write-AllureEnvironment -ResultsDir $ResultsDir

    $htmlDir = Get-AllureHtmlDir -Root $Root
    $standaloneHtml = Join-Path $htmlDir "standalone.html"
    $indexHtml = Join-Path $htmlDir "index.html"
    $fallback = Join-Path $Root "scripts\allure_fallback_report.py"

    # 1) 可选：官方 Allure SPA（需 node + java）
    Ensure-NodeNpmOnPath
    Ensure-JavaHomeForAllure
    $nodeOk = $null -ne (Get-Command node -ErrorAction SilentlyContinue)
    $javaOk = $null -ne (Get-Command java -ErrorAction SilentlyContinue)
    $allureExe = if ($nodeOk -and $javaOk) { Get-AllureCommand } else { $null }

    if ($allureExe) {
        & $allureExe generate $ResultsDir -o $htmlDir --clean 2>$null
        if (Test-Path $indexHtml) {
            Write-Host "[allure] official SPA: $indexHtml (use: python scripts/allure_serve.py --page index.html)" -ForegroundColor DarkCyan
        }
    }
    else {
        Write-Host "[allure] skip official generate (needs node and java)" -ForegroundColor DarkYellow
    }

    # 2) 始终最后生成 standalone（避免被 allure generate --clean 删掉）
    if (Test-Path $fallback) {
        python $fallback $ResultsDir $standaloneHtml
        if (Test-Path $standaloneHtml) {
            Write-Host "[allure] standalone report: $standaloneHtml" -ForegroundColor Green
            Write-Host "[allure] tip: open standalone.html, not index.html (file:// causes 500)" -ForegroundColor DarkCyan
        }
    }

    $open = if ($env:ALLURE_OPEN_BROWSER) { $env:ALLURE_OPEN_BROWSER.Trim() } else { "1" }
    if ($open -ne "0" -and (Test-Path $standaloneHtml)) {
        Start-Process $standaloneHtml | Out-Null
    }

    return $PytestExitCode
}

function Test-PytestArtifact {
    param([string]$Path)
    return $Path -match '\.(py)$' -and (Test-Path $Path)
}

function Get-GenerateOutputPyPath {
    param(
        [string[]]$RunSpecArgs,
        [string]$Root
    )
    for ($i = 0; $i -lt $RunSpecArgs.Count; $i++) {
        if ($RunSpecArgs[$i] -in @("-o", "--out") -and ($i + 1) -lt $RunSpecArgs.Count) {
            $p = $RunSpecArgs[$i + 1]
            if (-not [System.IO.Path]::IsPathRooted($p)) {
                $p = Join-Path $Root $p
            }
            return [System.IO.Path]::GetFullPath($p)
        }
    }
    $spec = $RunSpecArgs | Where-Object { $_ -match '\.md$' } | Select-Object -First 1
    if (-not $spec) { return $null }
    if (-not [System.IO.Path]::IsPathRooted($spec)) {
        $spec = Join-Path $Root $spec
    }
    $base = [System.IO.Path]::GetFileNameWithoutExtension($spec)
    return [System.IO.Path]::GetFullPath((Join-Path $Root "output\$base.py"))
}
