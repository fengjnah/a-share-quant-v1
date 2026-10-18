# TASK-022A-H-VERIFY：独立上下文结论

2026-10-18，独立执行上下文 `/root/task_022a_h_verify`；显式配置 GPT-6.1 Sol / High，无独立运行时型号/费用读数，不声称异模型交叉验证。依据用户 TASK-022A-H 第6节的明确要求，使用空白上下文只读审查，不参与实现，不调用网络、其他模型或 GitHub，不修改项目文件。

## 冻结范围

- 首版 `0f7cb1cca96dc8ccac66f5501c485c1fc6bd2d12`，对比原 `33e33c8e0583b70e1864ca7fb40e94152a338b6c`。
- 修复后 `72b176aac256f1f6dd2eb6ce9f2a864919c21711`。
- 读完四个 CFFEX 模块、两个测试文件、适用 AGENTS/模型/开源/数据/接口契约、F01—F11 起始问题及局部契约。两个 detached 审查工作树最终均干净，保留原树。

## 实际发现而非实现者自述

首版 `cffex_rankings.py` 的段完整性只检查有数据的集合：

1. legacy header+两个类别+两行 named header、删除全部具名数据时，实际 parse=legacy/6 行、ingest=success、net_count=0。
2. 删除全部 legacy 类别但保留其表头及完整 named 段时，实际 parse=named/60 行、ingest=success、net_count=37。

判 HIGH：混合文件整段截断被静默降级。该失败没有用“支持纯 legacy”掩盖。主会话只补两个已声明段非空条件与两个精确反例，独立上下文重新验证新 SHA 解析失败、schema_error 且不返回记录，确认最小修复，无仓储/日历范围扩建。

## 实际执行

| 检查 | 输出 / 退出码 |
| --- | --- |
| 首版定向 | 120 passed，0.77s / 0 |
| 首版首次完整 | **2 failed, 564 passed, 1 skipped**，37.37s / 1 |
| 首版进程 UTF-8 重跑 | 566 passed, 1 skipped，41.73s / 0 |
| 新 SHA 定向 | 122 passed，0.82s / 0 |
| 新 SHA 完整 | **568 passed, 1 skipped**，42.99s / 0 |
| pip check | No broken requirements found. / 0 |

首次失败为既有 project_progress 的 Windows 子进程输出编码，保留原日志；只加 PYTHONUTF8=1、PYTHONIOENCODING=utf-8 后重跑，没有排除测试或改期望。另设 PYTHONDONTWRITEBYTECODE=1、禁用 pytest 缓存、basetemp 在外部目录，真实 AKShare 集成始终未启用。实际版本、命令及根会话对照见 [主报告](TASK_022A_HIGH_ASSURANCE_REVIEW.md)。

## 最终结论原意与限制

**新 SHA 的限定离线修复范围通过独立复核，未发现剩余 BLOCKER/HIGH；生产及真实数据验收不在通过范围内。**

确认：缺失/错误/未来日历阻断建记录；event_time 来自会话收盘；404 原因不确定；净额强制单合约/已知 scope，缺侧 UNKNOWN；volume 分开；调用方单链执行双时间过滤、拒绝缺父/分叉/重复版本；重复载荷不重写原版本。局部契约对实现与限制的表述准确。

不能据此批准真实 CFFEX 日历/来源/发布时间、正式 SQLite 持仓仓储/持久版本/跨进程幂等/断点恢复、权威完整历史、回测/日报/策略、真实网络/UI/样本外、HTTPS 生产网络或 R04 授权。纯函数不能识别调用方隐瞒后继，内存比较不能称为完整仓储。未解集成门禁继续保留。

该结论绑定上述 SHA，不自动覆盖后续源码修改；最终交付若仅追加报告和脱敏元数据，应检查其未改变被审源码及测试。
