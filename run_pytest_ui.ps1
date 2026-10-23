# UI pytest entry: trace + failure screenshot + defect drafts + Allure（默认开启）
param(
    [switch]$Allure,
    [switch]$NoAllure,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:DEFECT_DRAFTS = if ($env:DEFECT_DRAFTS) { $env:DEFECT_DRAFTS } else { "1" }
$env:DEFECT_DRAFT_DIR = if ($env:DEFECT_DRAFT_DIR) { $env:DEFECT_DRAFT_DIR } else { "output/bugs" }
$env:UI_ARTIFACTS_DIR = if ($env:UI_ARTIFACTS_DIR) { $env:UI_ARTIFACTS_DIR } else { "output/ui_artifacts" }
if (-not $env:PROGRESS_REPORT) { $env:PROGRESS_REPORT = "1" }
if (-not $env:PROGRESS_REPORT_DIR) { $env:PROGRESS_REPORT_DIR = "output/reports" }
if (-not $env:FAILURE_ANALYSIS) { $env:FAILURE_ANALYSIS = "1" }
if (-not $env:FAILURE_ANALYSIS_DIR) { $env:FAILURE_ANALYSIS_DIR = "output/reports" }
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root\codegen;$env:PYTHONPATH" } else { "$Root\codegen" }

New-Item -ItemType Directory -Force -Path $env:UI_ARTIFACTS_DIR | Out-Null

. (Join-Path $Root "scripts\AllureReport.ps1")

$isCollectOnly = $false
foreach ($a in $PytestArgs) {
    if ($a -eq "--collect-only" -or $a -like "--collect-only=*") { $isCollectOnly = $true; break }
}

# UI 默认生成 Allure；仅 -NoAllure / ALLURE=0 / collect-only 跳过
$useAllure = -not $NoAllure -and -not $isCollectOnly
if ($env:ALLURE -match '^(0|false|no|off)$') { $useAllure = $false }
if ($Allure) { $useAllure = $true }

$allureResults = $null
if ($useAllure) {
    if (-not $env:ALLURE_RESULTS_DIR) { $env:ALLURE_RESULTS_DIR = "output/allure-results-ui" }
    if (-not $env:ALLURE_HTML_DIR) { $env:ALLURE_HTML_DIR = "output/allure-report-ui" }
    Set-AllureReportContext -TestType "ui" -PytestArgs $PytestArgs -DefaultBusiness "UI 通用"
    $allureResults = Get-AllureResultsDir -Root $Root
}

if ($env:UI_PRETEST -eq "1") {
    $base = if ($env:TEST_BASE_URL) { $env:TEST_BASE_URL } else { "http://your-server:5001" }
    $pyCode = "import sys; sys.path.insert(0, 'codegen'); from ui_lib.pretest import assert_readiness; assert_readiness('" + ($base -replace "'", "''") + "')"
    python -c $pyCode
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$defaults = @(
    "--tracing=retain-on-failure",
    "--screenshot=only-on-failure",
    "--output", (Join-Path $env:UI_ARTIFACTS_DIR "playwright-output")
)

Write-Host "[run_pytest_ui] UI_ARTIFACTS_DIR=$($env:UI_ARTIFACTS_DIR)"
Write-Host "[run_pytest_ui] DEFECT_DRAFT_DIR=$($env:DEFECT_DRAFT_DIR)"
if ($useAllure) {
    $env:ALLURE_REPORT_INCLUDE = "test_ui_,test_ui_batch"
    $htmlDir = Get-AllureHtmlDir -Root $Root
    Write-Host "[run_pytest_ui] ALLURE=1 (default) → results: $allureResults"
    Write-Host "[run_pytest_ui] ALLURE HTML → $htmlDir\standalone.html (clean-alluredir)"
}
elseif ($isCollectOnly) {
    Write-Host "[run_pytest_ui] ALLURE skipped (--collect-only)"
}
elseif ($NoAllure -or ($env:ALLURE -match '^(0|false|no|off)$')) {
    Write-Host "[run_pytest_ui] ALLURE=0 (-NoAllure or ALLURE=0)"
}
Write-Host ""

$allArgs = $defaults + $PytestArgs
if ($useAllure) {
    $allArgs = Add-AllurePytestArgs -PytestArgs $allArgs -ResultsDir $allureResults
}

python -m pytest @allArgs
$exitCode = $LASTEXITCODE

if ($useAllure) {
    $exitCode = Invoke-AllurePostPytest -Root $Root -ResultsDir $allureResults -PytestExitCode $exitCode
}

if ($useAllure -and (Test-Path (Join-Path (Get-AllureHtmlDir -Root $Root) "standalone.html"))) {
    Write-Host ""
    Write-Host "UI Allure report: $((Resolve-Path (Join-Path (Get-AllureHtmlDir -Root $Root) 'standalone.html')).Path)" -ForegroundColor Green
}

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "Artifacts: $((Resolve-Path $env:UI_ARTIFACTS_DIR).Path)" -ForegroundColor Yellow
    if (Test-Path $env:DEFECT_DRAFT_DIR) {
        Write-Host "Defect drafts: $((Resolve-Path $env:DEFECT_DRAFT_DIR).Path)" -ForegroundColor Yellow
    }
}

exit $exitCode
