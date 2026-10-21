"""Parse the daily entry point without running it or opening its database."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("shell", ["powershell.exe", "pwsh"])
def test_daily_entrypoint_parses_and_preserves_chinese(shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not installed")
    script = Path(__file__).resolve().parents[2] / "scripts" / "start_workbench.ps1"
    # Only the parser runs. In particular, do not dot-source the entry point.
    command = r"""
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '__SCRIPT__', [ref]$tokens, [ref]$parseErrors)
$literals = @($ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.StringConstantExpressionAst]
}, $true) | ForEach-Object { $_.Value })
[pscustomobject]@{
    errors = @($parseErrors | ForEach-Object { $_.ErrorId })
    literals = $literals
} | ConvertTo-Json -Depth 3 -Compress
""".replace("__SCRIPT__", str(script).replace("'", "''"))
    result = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, encoding="utf-8-sig", check=True, timeout=30,
    )
    parsed = json.loads(result.stdout)
    assert parsed["errors"] == []
    assert "无法读取 Git 分支；请确认工作区是有效的 Git 仓库。" in parsed["literals"]
