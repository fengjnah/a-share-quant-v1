# TASK-WINDOWS-STARTUP-UTF8-001

类型 implementation / L；仅修复 Windows PowerShell 5.1 对中文启动脚本的文件编码识别，不改变启动条件、分支/路径约束、环境配置或数据库语义。

- 唯一执行：OpenAI / Codex Desktop `gpt-6.1-sol / high`；本会话 turn_context 2026-10-21T15:41:35.161Z 核验，无子代理；费用 UNKNOWN。
- 预算：45分钟，同一问题最多两次有不同依据的修复。
- 基线：GitHub main `603715b08b40dfa33ff75987bd21f5d193f7e5a1`。依赖 PR47 已合并，head `149c2df1ee880ef60500031751ddc38deffa3351`，merge 即基线。
- 实施：`F:/codex-agnes/AI-trade-windows-startup-001`，`codex/windows-startup-utf8-001`；日常 `AI-trade-dev/main` 保持已提交版本，不直接修改或提交 main。
- 已读：AGENTS、MODEL_ROUTING_POLICY v1、TASK_TEMPLATE、PROJECT_STATUS、DECISIONS、OPEN_SOURCE_RESEARCH_POLICY v1、LOCAL_STREAMLIT_STARTUP、LOCAL_WORKBENCH、正式工作台源码/启动脚本及 tests/conftest。无下级 AGENTS/override。适用 G01—G12；纯编码兼容修复不涉及开源采用，新来源/依赖/算法研究不适用。
- 允许：启动脚本 UTF-8 BOM、操作说明、只解析不执行的回归测试、本记录；用户授权补齐 AI-trade-dev 缺失的独立 .venv。
- 禁止：改变启动守卫、切换日常分支、初始化/迁移/写正式库、采集、AWS、代理/TLS、自动合并或清理既有修改。
- 用户后续确认 8524 已从其他目录运行：保留服务，取消重复启动/重启；仅核对进程来源。服务可访问不是 AI-trade-dev 启动脚本已运行的证据。
- 用户随后明确要求停止8524：核对监听进程 PID17620，命令为从 `C:/Users/iyoyi/.codex/worktrees/m0-production-db-001/AI-trade/src/ai_trade/demo_app.py` 运行 Streamlit，参数端口8524；只停止该已核对进程，随后端口无监听。不重启、不启动替代服务。

## 复现与修复

旧脚本没有 BOM，Windows PowerShell 5.1 Parser.ParseFile 返回9处解析错误（行31/36/46/69/73）。同文件在 PowerShell 7 可正确解释 UTF-8。依据 [Microsoft 编码说明](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding)，保留脚本内容，只添加 UTF-8 BOM。

回归用各可用 PowerShell 的 AST 解析器读取实际文件，核对语法错误为0、中文错误文案正确；不执行启动脚本或访问数据库。缺少对应 shell 的平台明确 skip。

## 验收与结果

- 定向：`python -m pytest -q tests/unit/test_start_workbench_encoding.py`，2 passed / exit0；再加已有 M4 AppTest 共3 passed / exit0。
- 完整：`python -m pytest -q`，默认网络阻断、仅隔离临时测试库；**2892 passed / 1 skipped，261.28秒，exit0**。唯一skip为未显式启用的真实AKShare测试；日志 `artifacts/windows-startup-001/pytest-full-prepared.log`。
- 依赖：`python -m pip check`，No broken requirements found / exit0，日志 `artifacts/windows-startup-001/pip-check.log`；`git diff --check` / exit0。
- 8524 既有服务：用户确认可访问；本轮不重复启动，不将其记为新入口 E2E。
- 真实行情、样本外、部署：NOT RUN。

本机独立 `.venv` 已创建，安装项目已有 demo/test 所需依赖，主要版本与已存在的可用环境一致（Streamlit1.66.0、pandas3.0.6、jsonschema4.26.0、pytest8.4.2、requests2.34.2、tzdata2026.5），另以 editable 安装 AI-trade-dev。无仓库依赖定义升级；包安装使用正常 TLS，未改代理。

首轮完整测试环境未准备完：子进程报 `ModuleNotFoundError: ai_trade`，因此主动停止运行，exit-1（保留 artifacts/windows-startup-001/pytest-full.log，不作为完整结果）。补齐 editable 安装并在本次测试进程设置 PYTHONPATH=实施树/src、PYTHONUTF8=1、PYTHONIOENCODING=utf-8；已有失败用例加编码回归3项通过后重新运行完整套件。未修改既有断言或业务代码。

交付范围4文件。暂存脚本逐字节验证：修复后的 Git blob 严格等于原始 blob 加3字节UTF-8 BOM；无其他内容改动。`.venv`及测试日志均忽略，不提交。AI-trade-dev/main仍为基线且干净；原工作区、2条stash保留。8524无监听；正式库未连接/写入，测试前后文件SHA256均为 `48511c2092d0e08c02e9384647e5d51365feb04232248f7b95e0df1b5c998f64`。

按用户最新要求，启动/E2E **NOT RUN（取消启动、服务保持关闭）**。本轮解析器/离线测试通过不等于已从AI-trade-dev真实启动，亦不构成独立H、来源或生产准入通过。兼容修复待PR人工处理后才能进入日常main；不自动合并或更改分支启动限制。

审查批次 `BATCH-WINDOWS-STARTUP-001`；计划 `TASK-WINDOWS-STARTUP-UTF8-001-REVIEW`，待指派并绑定最终交付 SHA，不由本会话换角色自审。不借本次修复解除既有核心、来源或生产门禁。最终 SHA / PR 在 PR 正文绑定。
