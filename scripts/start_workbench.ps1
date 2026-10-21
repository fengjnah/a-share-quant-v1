param(
    [string]$Python = 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe',
    [string]$Root = 'F:\codex-agnes\AI-trade\data\sqlite',
    [int]$Port = 8524
)
$ErrorActionPreference = 'Stop'
$codeRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $codeRoot 'src'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:AI_TRADE_WORKBENCH_ROOT = $Root
$env:QUANT_DB_PATH = Join-Path $Root 'workbench.sqlite3'
$env:QUANT_DB_ENV = 'local'
$env:QUANT_DB_JOURNAL = 'DELETE'
$env:AI_TRADE_STRICT_WORKBENCH = '1'
$env:AI_TRADE_READ_ONLY = '1'
Remove-Item Env:AI_TRADE_DEMO_ROOT -ErrorAction SilentlyContinue
# Checks the actual SQLite connection, checksum, DDL and integrity. No initialize.
& $Python -m ai_trade.storage.workbench_cli diagnose --root $Root
if ($LASTEXITCODE -ne 0) { throw '正式数据库检查失败；停止，不创建替代库。' }
& $Python -m streamlit run (Join-Path $codeRoot 'src\ai_trade\demo_app.py') --server.address 127.0.0.1 --server.port $Port --server.headless true --browser.gatherUsageStats false
exit $LASTEXITCODE
