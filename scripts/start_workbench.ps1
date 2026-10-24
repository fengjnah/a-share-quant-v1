param(
    [int]$Port = 8524,
    [string]$DataRoot
)

$ErrorActionPreference = 'Stop'

# The daily entry point is intentionally pinned to the clean main checkout.
$ExpectedWorkspace = 'F:\codex-agnes\AI-trade-dev'
$ExpectedBranch = 'main'
$Python = Join-Path $ExpectedWorkspace '.venv\Scripts\python.exe'

# An explicit independent data root; no checkout-relative or old-path fallback.
if (-not $PSBoundParameters.ContainsKey('DataRoot')) {
    if (Test-Path Env:AI_TRADE_DATA_ROOT) {
        $DataRoot = $env:AI_TRADE_DATA_ROOT
    } else {
        $DataRoot = 'F:\codex-agnes\AI-trade-data'
    }
}
if ([string]::IsNullOrWhiteSpace($DataRoot) -or $DataRoot -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+)') {
    throw 'AI_TRADE_DATA_ROOT 必须是明确的绝对数据目录；不会回退旧数据库。'
}
$DataRoot = [System.IO.Path]::GetFullPath($DataRoot).TrimEnd([char]'\')
$Root = Join-Path $DataRoot 'sqlite'
$DatabasePath = Join-Path $Root 'workbench.sqlite3'

if (-not (Test-Path -LiteralPath $ExpectedWorkspace -PathType Container)) {
    throw "固定工作区不存在：$ExpectedWorkspace"
}

$codeRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd([char]'\')
$expectedRoot = [System.IO.Path]::GetFullPath($ExpectedWorkspace).TrimEnd('\')
if (-not [string]::Equals($codeRoot, $expectedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "启动脚本必须来自固定工作区 $ExpectedWorkspace；实际位置：$codeRoot"
}

$branch = (& git -C $codeRoot branch --show-current 2>$null).Trim()
if ($LASTEXITCODE -ne 0) {
    throw '无法读取 Git 分支；请确认工作区是有效的 Git 仓库。'
}
if ($branch -ne $ExpectedBranch) {
    throw "当前分支为 '$branch'，日常启动只允许 '$ExpectedBranch'。不会自动切换分支。"
}

$worktreeStatus = @(& git -C $codeRoot status --porcelain --untracked-files=normal 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw '无法读取 Git 工作区状态；停止启动。'
}
if ($worktreeStatus.Count -gt 0) {
    throw "工作区不是干净状态。为避免运行未提交代码，已停止启动。请先自行检查：git -C '$codeRoot' status --short"
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "AI-trade-dev 的虚拟环境解释器不存在：$Python。请在该工作区按项目依赖说明准备 .venv；脚本不会回退到其他目录的 Python。"
}
if (-not (Test-Path -LiteralPath $DatabasePath -PathType Leaf)) {
    throw "正式数据库不存在：$DatabasePath。日常启动不会创建或初始化数据库，也不会回退到 Demo。"
}

# Inherited aliases are assertions, never competing sources of the DB path.
$ExpectedPaths = @{
    AI_TRADE_DATA_ROOT = $DataRoot
    AI_TRADE_WORKBENCH_ROOT = $Root
    QUANT_DB_PATH = $DatabasePath
}
foreach ($Name in $ExpectedPaths.Keys) {
    if (Test-Path "Env:$Name") {
        $Actual = [Environment]::GetEnvironmentVariable($Name, 'Process')
        if ([string]::IsNullOrWhiteSpace($Actual) -or $Actual -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+)' -or
            -not [string]::Equals([IO.Path]::GetFullPath($Actual).TrimEnd([char]'\'), $ExpectedPaths[$Name], [StringComparison]::OrdinalIgnoreCase)) {
            throw "$Name 与独立数据根不一致。请检查配置或打开新 PowerShell；不会静默选择旧库。"
        }
    }
}

$env:PYTHONPATH = Join-Path $codeRoot 'src'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:AI_TRADE_DATA_ROOT = $DataRoot
$env:AI_TRADE_WORKBENCH_ROOT = $Root
$env:QUANT_DB_PATH = $DatabasePath
$env:QUANT_DB_ENV = 'local'
$env:QUANT_DB_JOURNAL = 'DELETE'
$env:AI_TRADE_STRICT_WORKBENCH = '1'
$env:AI_TRADE_READ_ONLY = '1'
Remove-Item Env:AI_TRADE_DEMO_ROOT -ErrorAction SilentlyContinue

Write-Host "Workspace : $codeRoot"
Write-Host "Branch    : $branch"
Write-Host "Commit    : $(& git -C $codeRoot rev-parse HEAD)"
Write-Host "Python    : $Python"
Write-Host "Database  : $DatabasePath"
Write-Host "Read-only : enabled"

# Diagnose the existing DB before starting Streamlit. This command must not initialize it.
& $Python -m ai_trade.storage.workbench_cli diagnose --root $Root
if ($LASTEXITCODE -ne 0) {
    throw '正式数据库检查失败；停止，不创建替代库。'
}

& $Python -m streamlit run (Join-Path $codeRoot 'src\ai_trade\demo_app.py') --server.address 127.0.0.1 --server.port $Port --server.headless true --browser.gatherUsageStats false
exit $LASTEXITCODE
