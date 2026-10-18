# TASK-009：GitHub PR 治理矩阵

核查日期：2026-10-18（Asia/Shanghai）。以下仅为处理建议，**没有 merge、close、删除分支或移除工作树**。执行记录见 [实施报告](IMPLEMENTATION_TASK_009.md)，远端字段/CI 的脱敏摘要见 [Git 审计](evidence/TASK_009_GIT_AUDIT.json)。文本可合并不等于数据源或生产验收通过。

## 基线与逐项建议

最新 main 经分支 API 确认：`c65a3189daf72c1aa97b5930e3a22215bda3f1c8`。CLI fetch 低速超时，未把缓存假称 fetch 成功。#11 API 的 base.sha 仍显示 `0578f9c…`，因此覆盖比较使用已单独核实的最新 main，而非该字段。

| PR | head SHA / base | 最新状态、CI、冲突 | 独有内容与结论 | 建议及条件 |
| --- | --- | --- | --- | --- |
| [#11](https://github.com/fengjnah/a-share-quant-v1/pull/11) | `39be058d35f5ebc49ab88af4fcbcf0b356a96c97` / main | open、非 draft、未合并；无该 head 的 PR workflow run；`mergeable=false, dirty` | TASK-004 的代码、测试、README、数据/接口契约与最新 main 相同；独有研究价值是 004A 报告，另有旧状态文字 | **不整支合并**。先保留/审查独有报告，再由用户决定关闭旧 PR；004A 真实来源验收仍未完成 |
| [#13](https://github.com/fengjnah/a-share-quant-v1/pull/13) | `b31847ff41e200d5b7cb8ef9193c785e1e3e16be` / main | open draft、未合并；[CI success](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39051447382)；`clean` | callback 点击编号与 processed 编号防 rerun 重复采集；无响应时显示未知；附离线 AppTest 与历史报告 | 技术检查未发现阻断此局部修复合并的缺陷，可提交用户审批；保留独立 H 审查条件。真实东财失败不否定离线可复现的安全修复，也不等于真实链路通过 |
| [#14](https://github.com/fengjnah/a-share-quant-v1/pull/14) | `365a01ca3d6400225ea130188187655211a1cdd1` / main | open draft、未合并；[CI success](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39052636700)；`clean` | 有界白名单异常类型链、不保存消息/URL/凭据、状态分类不变；循环/未知类有测试 | 技术检查未发现阻断此局部日志修复合并的缺陷，可提交用户审批；完整底层链和网络子阶段仍可能未知，不得删去 `OtherError` / `network_phase=undetermined` 的限制 |
| [#15](https://github.com/fengjnah/a-share-quant-v1/pull/15) | `b7cbe9ef05623aa99e081b1141528f14817f553e` / main | open draft、未合并；[CI success](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39087404130)；`clean` | 仅 TASK-DEMO-003 报告；保留代理 TLS 失败、独立直连 TLS 成功、手写 GET 失败的先后证据；未虚报 AKShare/SQLite 成功 | **建议作为历史报告合并归档**，不算功能验收。若用户选择关闭，应先保留报告可检索位置和 SHA，再考虑删分支 |
| [#16](https://github.com/fengjnah/a-share-quant-v1/pull/16) | `d4701c826ca1eed65074b48ffc6da90e6ff908ad` / #14 分支 | open draft、未合并；`clean`；无该 head 的 PR workflow run | 独有单次正式请求工具、脱敏审计、4 个控制测试及报告；TLS/本地发送完成，状态行断开；连续上层异常链未完整保留 | **建议保留并归档工具/报告**。#14 处理后 retarget/rebase 到 main，重新跑 CI 再审批。当前 CI 仅监听目标 main，因此无 run 不能写作 CI 通过或失败 |

本 TASK 同时做集成与自检，不把它冒称为对新集成“独立、干净上下文的 H 审查”。G12 要求的新集成来源边界独立只读 H 审查应另立 TASK、绑定最终 SHA；本次未调用其他模型或启动后续任务。

## 实际比较证据

- #10 已合并为 main 祖先 `0578f9c30039cf3f8e9f4618a6806c5c8411b1dd`。其 tree 与 TASK-004 原 head `bb596a9bcf9d34c2ae29b43334873cc8e08c3313` 同为 `4d28793a0466e381a805cffa268a98074714666a`，不是凭提交名判定覆盖。
- `git diff c65a3189 39be058 -- src/ai_trade tests README.md docs/DATA_CONTRACT.md docs/INTERFACE_CONTRACT.md` 无差异。整树比较还显示旧分支缺少后加治理文件和项目状态文字；这不意味着三方合并必然删除后加文件，但不能用旧树覆盖 main，且 GitHub 已报告冲突。
- 本地 `docs/task-004a-report-only@b0a1ba100244a25ea2a29091b0ae51efda1a694c` 只比治理 main 多一份 004A 报告，blob 与 #11 同为 `40ff735f1423b670000055a9c63c3fcaa96652b2`。该分支仍有独有材料，本任务保留且不顺带发布另一个 004A PR。
- #13 改 demo_app/UI 测试，#14 改 ingestor/采集测试，组合应用无文本冲突。新集成保留两项 patch，并修正腾讯元数据误标、数值校验和页面代理“配置推断/实际路线”混淆。
- #15 本地 `01721716acd6173556c7ef6dbeb495648326504b` 与远端 head 不同，tree 同为 `3132465477c70b7cf5b4074593b92360335df460`；#16 本地 `6bb1ed06c6cd1d672140291df6b3224f48a74ec6` 与远端 head 不同，tree 同为 `977b9f2371a1823f74357f15b66e6e877a7aced1`。不能把提交元数据差异误判成独有代码修复。

## 用户确认后可清理的远端分支候选

下表逐一验证了**当前 head tree 与 main 祖先提交 tree 完全相同**；squash 后不一定满足提交祖先关系，不能只依赖 `--merged`。删除前仍须重新核实 head 未变、无关联独有工作。

| 远端分支 | head → main 中等价提交 | 共同 tree |
| --- | --- | --- |
| `feature/task-002-sqlite-foundation` | `4b73f8a… → cd1b2b1…` | `7a4bb379ae6c6f7513602f129d8f31d43f8e0ba6` |
| `feature/task-003-akshare-adapter-rebased` | `08388c5… → a102ac9…` | `cc8066ee376457c567abdc5240807439fe1b9fb6` |
| `feature/task-003c-tls-rebased` | `9df3660… → 804a331…` | `99e060ccff6da7c4384eb3d8ac61008e7c50e90b` |
| `feature/local-market-demo-rebased` | `b3e4e31… → 74536e0…` | `01e411a75ff364d9b5b7ea72fb0cd7a821d41c95` |
| `chore/project-baseline-20261017` | `0ab86e1… → 824d634…` | `2a949c8e02ebe31c974c09b2af6801286f332613` |
| `docs/trading-system-conversation-archive-20261017` | `b7113d1… → d09a259…` | `397a62097e4b40e9f8b5a01ec7e4cf09e47c98f9` |
| `codex/task-004-master-calendar-resumed` | `bb596a9… → 0578f9c…` | `4d28793a0466e381a805cffa268a98074714666a` |
| `docs/model-routing-governance` | `b53e5b7… → c65a318…` | `4417b04d46892c6dd791ac10a800cc5c10598a87` |

本地清理另受工作树约束：治理分支正被工作树检出，不能直接删本地分支；原 TASK-004 目录有暂存/未暂存内容。`codex/task-local-reconcile-001` 有 TASK-008 及 005/006/008A 未提交材料，**即使 #13 合并也不能据此移除工作树**。#11、#13–#16、报告专用分支和新集成分支仍有未合并内容，不列入当前无条件候选。其他早期分支没有逐项等价证明时保持待核对，不能因名称旧而宣称可删。

## 建议审批顺序

1. 先审批 #13、#14；若用户合并，再将新集成 PR 更新到最新 main、移除重复 patch、重跑测试。新 PR 当前以 main 为 base，自包含两项修复，未假定旧 PR 已合并。
2. 对新集成最终 SHA 安排独立 H 审查，只按本地候选 Demo 处理。也可选择直接审批自包含新 PR，再对照合入内容由用户关闭被替代的 #13/#14；不要机械执行两套方案。
3. #15 作为历史报告归档；#16 在 #14 处理后改目标 main，运行 CI、审查控制脚本，再审批。
4. 单独保留/审查 004A 报告后，由用户决定是否关闭 #11。最后重新核实远端 head 和本地独有内容，再审批上述分支清理。

以上操作均未执行。Draft PR 交付后停止，等待用户选择方案。
