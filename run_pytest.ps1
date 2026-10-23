# Windows API pytest entry (progress + failure analysis + defect drafts + optional Allure)
param(
    [switch]$Allure,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not $env:PROGRESS_REPORT) { $env:PROGRESS_REPORT = "1" }
if (-not $env:PROGRESS_REPORT_DIR) { $env:PROGRESS_REPORT_DIR = "output/reports" }
if (-not $env:FAILURE_ANALYSIS) { $env:FAILURE_ANALYSIS = "1" }
if (-not $env:FAILURE_ANALYSIS_DIR) { $env:FAILURE_ANALYSIS_DIR = "output/reports" }
if (-not $env:DEFECT_DRAFTS) { $env:DEFECT_DRAFTS = "1" }
if (-not $env:DEFECT_DRAFT_DIR) { $env:DEFECT_DRAFT_DIR = "output/bugs" }

. (Join-Path $Root "scripts\AllureReport.ps1")
$useAllure = Test-AllureEnabled -AllureSwitch:$Allure
$allureResults = $null
if ($useAllure) {
    if (-not $env:ALLURE_RESULTS_DIR) { $env:ALLURE_RESULTS_DIR = "output/allure-results" }
    if (-not $env:ALLURE_HTML_DIR) { $env:ALLURE_HTML_DIR = "output/allure-report" }
    Set-AllureReportContext -TestType "api" -PytestArgs $PytestArgs -DefaultBusiness "API 通用"
    $allureResults = Get-AllureResultsDir -Root $Root
    $PytestArgs = Add-AllurePytestArgs -PytestArgs $PytestArgs -ResultsDir $allureResults
}

Write-Host "[run_pytest] PROGRESS_REPORT_DIR=$($env:PROGRESS_REPORT_DIR)"
Write-Host "[run_pytest] DEFECT_DRAFT_DIR=$($env:DEFECT_DRAFT_DIR)"
if ($useAllure) {
    Write-Host "[run_pytest] ALLURE=1 → $allureResults"
}
Write-Host ""

python -m pytest @PytestArgs
$exitCode = $LASTEXITCODE

if ($useAllure) {
    $exitCode = Invoke-AllurePostPytest -Root $Root -ResultsDir $allureResults -PytestExitCode $exitCode
}
elseif ($exitCode -ne 0) {
    $R = Join-Path $Root $env:PROGRESS_REPORT_DIR
    if (Test-Path (Join-Path $R "progress.md")) {
        Write-Host "进度报告: $R\progress.md" -ForegroundColor Cyan
    }
    if (Test-Path (Join-Path $Root $env:DEFECT_DRAFT_DIR)) {
        Write-Host "缺陷草稿: $(Join-Path $Root $env:DEFECT_DRAFT_DIR)" -ForegroundColor Yellow
    }
}

exit $exitCode
