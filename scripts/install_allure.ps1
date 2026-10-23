# 一键安装 Allure 报告依赖（Windows）
# 用法（技能包根目录）: powershell -File scripts/install_allure.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

Write-Host "=== Allure 环境检查 / 安装 ===" -ForegroundColor Cyan

# 1. Python allure-pytest
python -m pip install -q "allure-pytest>=2.0"
Write-Host "[OK] allure-pytest" -ForegroundColor Green

# 2. Node.js（winget，已装则跳过）
$node = "C:\Program Files\nodejs\node.exe"
if (-not (Test-Path $node)) {
    Write-Host "安装 Node.js LTS..." -ForegroundColor Yellow
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
}
if (Test-Path $node) {
    $env:Path = "C:\Program Files\nodejs;$env:APPDATA\npm;$env:Path"
    Write-Host "[OK] Node $( & $node -v )" -ForegroundColor Green
}
else {
    Write-Host "[WARN] 未找到 Node.js，请手动安装后重跑本脚本" -ForegroundColor Yellow
    exit 1
}

# 3. allure-commandline（npm 全局）
npm install -g allure-commandline
Write-Host "[OK] allure-commandline (npm global)" -ForegroundColor Green

# 4. Java（Allure CLI 需要 JAVA_HOME）
$java = Get-ChildItem "C:\Program Files\Microsoft\jdk-*" -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1
if (-not $java) {
    Write-Host "安装 Microsoft OpenJDK 17..." -ForegroundColor Yellow
    winget install Microsoft.OpenJDK.17 --accept-package-agreements --accept-source-agreements
    $java = Get-ChildItem "C:\Program Files\Microsoft\jdk-*" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
}
if ($java) {
    Write-Host "[OK] JAVA_HOME=$($java.FullName)" -ForegroundColor Green
}
else {
    Write-Host "[WARN] 未找到 Java；Allure 将回退到 scripts/allure_fallback_report.py 简易 HTML" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "验证:" -ForegroundColor Cyan
Write-Host "  powershell -File run_pytest.ps1 -Allure output/api_smoke.py -v"
Write-Host "  报告: output/allure-report/index.html"
Write-Host ""
Write-Host "可选：把 Node 加入用户 PATH（新开终端生效）" -ForegroundColor DarkGray
Write-Host "  C:\Program Files\nodejs"
Write-Host "  $env:APPDATA\npm"
