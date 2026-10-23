# Windows: spec → pytest（可选 --report 生成并打开 Allure）
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$wantReport = $false
$runSpecArgs = New-Object System.Collections.Generic.List[string]
foreach ($a in $Args) {
    if ($a -eq "--report") {
        $wantReport = $true
        continue
    }
    [void]$runSpecArgs.Add($a)
}

if ($runSpecArgs.Count -eq 0) {
    Write-Host "用法: powershell -File generate.ps1 <spec.md> [-o output/xxx.py] [--report]"
    exit 1
}

python -u (Join-Path $Root "codegen\run_spec.py") @runSpecArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $wantReport) { exit 0 }

. (Join-Path $Root "scripts\AllureReport.ps1")
$outPy = Get-GenerateOutputPyPath -RunSpecArgs $runSpecArgs.ToArray() -Root $Root
if (-not $outPy -or -not (Test-PytestArtifact -Path $outPy)) {
    Write-Host "[generate.ps1] --report 仅适用于 pytest 产物 (.py)，当前输出: $outPy" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "[generate.ps1] 运行 pytest + Allure: $outPy" -ForegroundColor Cyan

$specPath = $runSpecArgs | Where-Object { $_ -match '\.md$' } | Select-Object -First 1
$isUi = $false
if ($specPath) {
    $sp = if ([System.IO.Path]::IsPathRooted($specPath)) { $specPath } else { Join-Path $Root $specPath }
    if (Test-Path $sp) {
        $head = Get-Content $sp -TotalCount 30 -ErrorAction SilentlyContinue | Out-String
        if ($head -match 'kind:\s*ui_pytest') { $isUi = $true }
    }
}
if (-not $isUi -and $outPy -match 'ui[_-]') { $isUi = $true }

$runner = if ($isUi) { "run_pytest_ui.ps1" } else { "run_pytest.ps1" }
if ($isUi) {
    & (Join-Path $Root $runner) @($outPy, "-v")
} else {
    & (Join-Path $Root $runner) -Allure @($outPy, "-v")
}
exit $LASTEXITCODE
