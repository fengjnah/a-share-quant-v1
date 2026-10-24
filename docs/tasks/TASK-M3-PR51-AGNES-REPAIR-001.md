# TASK-M3-PR51-AGNES-REPAIR-001：PR #51 七项失败定向修复

| 字段 | 值 |
| --- | --- |
| TASK ID | TASK-M3-PR51-AGNES-REPAIR-001 |
| 类型 | 定向修复（测试夹具） |
| 目标 PR | #51 |
| 模型 | Agnes 3.0 Flash |
| 基线 SHA | 29d11241b8f33f7d12214d1ea100bc8e504fc07d（PR #51 head） |
| 分支 | codex/m3-pr51-agnes-repair-001 |
| 修复 SHA | 73323c5 |
| H-gate 结论 | REPAIR_AUTHORIZED（§6 定向范围：T1/T2 测试夹具） |

## 1. 修复内容

### T1（6 项）：m3_storage_fixtures.py:95

问题：cffex_diagnostic() 不接受 contract 参数；合约来自 request.symbol。
调用时 request.symbol=IF（品种）而非 IF2611（具体合约），scope.symbols 也需同步。

修复：
- scope() 中 symbols 从 [TEST_INDEX, IF] 改为 [TEST_INDEX, IF2611]
- compute() 中 Request symbol 从 IF 改为 IF2611
- 移除 contract=IF2611 非法关键字参数

影响文件：tests/unit/m3_storage_fixtures.py（仅测试夹具，不修改生产代码）

### T2（1 项）：test_m3_storage_market.py:152 [blank]

问题：测试期望空会员（有数值）payload 先通过 build_record 获得合法 record，
再走 save_cffex 的 BLOCKED 路径。实际上解析器在 build_record 阶段就抛出
RankingValidationError（数值字段需要显式会员名，契约要求）。

修复：
- [blank] 分支：直接断言 build_record 抛出 RankingValidationError；
  验证 raw evidence bytes 保留、无 typed report、无 run。
- [mixed] 分支（legacy 格式）：保持原 BLOCKED 断言不变。

影响文件：tests/unit/test_m3_storage_market.py（仅测试，不修改解析器契约）

## 2. 测试结果

| 测试组 | 结果 |
| --- | --- |
| 原 7 项失败 | 26 passed, 0 failed |
| M3 存储全量（5 文件） | 143 passed |
| CFFEX 解析 + 市场核心验证/边界 | 564 passed |
| 完整离线 | 3030 passed, 5 failed, 1 skipped |

5 项残留失败全部为既有环境缺陷（venv 路径污染、Windows GBK 编码、
streamlit 新安装后原 SKIPPED 测试激活），非 PR #51 代码问题。

## 3. 门禁合规

- 未修改 market_analysis_core.py / market_analysis_contract.py / market_data/cffex_rankings*.py
- 未修改 M3 评分算法、六因子权重、数据库结构
- 未引入兼容性包装
- H1（快照准入用途权限）和 M1（CFFEX 失败证据关联）为 H 级，本任务（L）未处理
- PR #51 保持 Draft，未合并，未触发正式库迁移

## 4. 交付

- 修复 commit：73323c5
- 分支：codex/m3-pr51-agnes-repair-001（已推送 origin）
- 手动 PR 创建 URL：https://github.com/fengjnah/a-share-quant-v1/pull/new/codex/m3-pr51-agnes-repair-001
- 等待 CI 通过后由 H-gate 任务复核新 SHA
