# HAR → k6/JMeter 压测一键流水线（load-testing skills）
param(
    [Parameter(Mandatory = $true)]
    [string]$Har,
    [ValidateSet("k6", "jmeter", "both")]
    [string]$Engine = "k6",
    [switch]$Smoke,
    [switch]$SkipRun,
    [string]$AuthProfile = "templates/auth_profiles/generic_rest.yaml",
    [string]$ToolsRoot = $(if ($env:PERF_TOOLS_ROOT) { $env:PERF_TOOLS_ROOT } else { "C:\perf-tools" })
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$K6Exe = Join-Path $ToolsRoot "k6\k6.exe"
$HarPath = if ([System.IO.Path]::IsPathRooted($Har)) { $Har } else { Join-Path $Root $Har }
if (-not (Test-Path $HarPath)) {
    Write-Error "HAR 不存在: $HarPath"
}

function Import-PerfEnv {
    param([string]$EnvFile)
    if (-not (Test-Path $EnvFile)) { return }
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim()
        }
    }
}

$smokeFlag = if ($Smoke) { "--smoke" } else { $null }
$k6Spec = "templates/har_perf_k6.md"
$jmSpec = "templates/har_perf_jmeter.md"

Write-Host "== Step 1: HAR -> perf spec =="
if ($Engine -eq "both" -or $Engine -eq "k6") {
    if ($smokeFlag) {
        python codegen/har_to_perf.py -i $HarPath -o $k6Spec --engine k6 $smokeFlag
    } else {
        python codegen/har_to_perf.py -i $HarPath -o $k6Spec --engine k6
    }
}
if ($Engine -eq "both" -or $Engine -eq "jmeter") {
    if ($smokeFlag) {
        python codegen/har_to_perf.py -i $HarPath -o $jmSpec --engine jmeter $smokeFlag
    } else {
        python codegen/har_to_perf.py -i $HarPath -o $jmSpec --engine jmeter
    }
}

Write-Host "== Step 2: spec -> 脚本 =="
if ($Engine -eq "both" -or $Engine -eq "k6") {
    python codegen/run_spec.py $k6Spec -o output/har_perf_k6.js
}
if ($Engine -eq "both" -or $Engine -eq "jmeter") {
    python codegen/run_spec.py $jmSpec -o output/har_perf_jmeter.jmx
}

Write-Host "== Step 3: Token =="
python codegen/fetch_perf_token.py --auth-profile $AuthProfile --output-env output/.perf_env
Import-PerfEnv (Join-Path $Root "output/.perf_env")

if ($SkipRun) {
    Write-Host "已生成脚本（SkipRun），Token 已写入 output/.perf_env"
    exit 0
}

$exitCode = 0
$ran = $false
$token = $env:PERF_ACCESS_TOKEN
$tenant = $env:PERF_TENANT_ID

if (($Engine -eq "both" -or $Engine -eq "k6") -and (Test-Path $K6Exe)) {
    Write-Host "== Step 4: k6 =="
    & $K6Exe run `
        -e "BASE_URL=$env:TEST_BASE_URL" `
        -e "PERF_ACCESS_TOKEN=$token" `
        -e "PERF_TENANT_ID=$tenant" `
        --summary-export=(Join-Path $Root "output/k6_summary.json") `
        "output/har_perf_k6.js"
    if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
    $ran = $true
}

if ($Engine -eq "both" -or $Engine -eq "jmeter") {
    Write-Host "== Step 4: JMeter (run_jmeter_perf.py) =="
    python (Join-Path $Root "codegen/run_jmeter_perf.py") --skip-token
    if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
    $ran = $true
}

if (-not $ran) {
    Write-Host "未找到 k6 可执行文件，改用 Python 冒烟校验..."
    python codegen/perf_smoke_validate.py -i $HarPath --rounds 3
    exit $LASTEXITCODE
}

exit $exitCode
