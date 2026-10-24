# TASK-M3-CFFEX-RAW-PREVIEW-005 — 第一阶段

## 开始记录（2026-10-24，Asia/Shanghai）

- 类型 implementation；H，涉及正式数据展示边界。唯一执行模型 OpenAI `gpt-6.1-sol`，固定推理强度 `medium`：本会话运行日志 turn_context 核实模型，用户在本会话确认档位“中”。日志未提供档位，不能用旧任务的 high 替代。费用/额度未知；预算 60 分钟，同一验收问题最多两次不同诊断修复。无子代理、外部模型或切换。
- 最新 main `20112111dbe287a770e5b845b3e036ba33d068ef`，GitHub branches/main 与本次 git fetch 一致。PR60 已合并，head `d4b27f538ed5db12008abdf306918ca3f61f7865`、base `3975e2e6c35fe7c1f1bc01a0276ef65b55fbc028`；PR61 仍 Draft/open，base 同 main、head `bb75b7c9daff3bff5d6c3ca162ae16e111da42a9`，只作旁证，不依赖未合并报告。
- 独立分支 `codex/m3-cffex-raw-preview-005`，从最新 main 创建在当前聊天 work/repo，起始干净。原 dev/main `3975e2e6c35fe7c1f1bc01a0276ef65b55fbc028` 干净、8524 绑定该工作区；保留原运行进程与其他工作区。
- 已实际阅读该 main 的 AGENTS.md、MODEL_ROUTING_POLICY.md v1.0、OPEN_SOURCE_RESEARCH_POLICY.md v1.0、tasks/TASK_TEMPLATE.md、PROJECT_STATUS.md、DECISIONS.md、DATA_CONTRACT.md、INTERFACE_CONTRACT.md、M3_CORE_CONTRACT.md v1、architecture/M3_CORE_DATA_MODEL_DICTIONARY.md B02/B03/B06/B07/R03、reviews/TASK_022A_CFFEX_CONTRACT.md、H1/M1 任务单/结果报告、原 UI 任务单，以及 Catalog/MarketInput/page/db/parser 与相应测试。仅根 AGENTS，无下级规则或 override。适用 G01–G12。
- 调研不适用外部引入：本轮检查既有授权边界，复用既有 parser、Evidence/Catalog、只读 Database 和 Streamlit，不新增依赖、数据源或准入算法。未取得供应商许可，不认证法律权限。

## 权限结论与允许范围

H1 是 research+storage 用途检查，M1 是失败尝试到原始证据的关联；二者均未授予独立 display 例外。B07 将 display 单列、要求独立签发者及信任根；M3 的 L1 受限观察不等于对任意私有原始响应的 display 授权。原 UI 任务的一次例外明确仅限原始观察保存。当前没有找到本地维护展示授权路径，正式原始数据预览保持 BLOCKED，不能由开关或警告文案授权。

用户明确允许这一情况下进行隔离代码准备。本阶段仅添加**未接入正式 M3 的合成证据预览组件**和离线测试：要求显式 test 数据库、synthetic 证据、只读重开；默认关闭，启用只允许测试夹具。生产 source_payload 即使位于测试库也拒绝，local/production 句柄在打开连接之前拒绝。复用原解析器，不构造正式 CffexRankingsRecord、不生成 available_at，不调用写入接口。日期/品种/合约/会员/类别筛选及原始来源/hash/采集时间用合成证据验证。

禁止正式数据展示或结构化入库、修改 allowed_uses/quality/Schema/AWS、修改正式页路由、重启/替换8524、自动合并。8524 本轮仅验证现状及服务健康；不能将隔离 AppTest 称为真实数据 UI 验收。

## 验收与审查

1. 临时 SQLite/Catalog 合成证据、四品种解析和筛选；hash/大小/路径完整性失败必须拒绝。
2. 默认关闭及显式启用；非 test 句柄在连接前拒绝；非 synthetic 证据不读取正文；传入可写 test 句柄必须重开 mode=ro，数据库前后字节一致。
3. 固定警示 UNVERIFIED / NOT ADMITTED / NOT FOR RESEARCH OR TRADING，并另标 SYNTHETIC TEST FIXTURE；不以夹具代替真实 840 行或中信期货验收。
4. 针对测试、完整离线 pytest、pip check、git diff --check，保存命令/退出码/数量；默认禁外网，AppTest 仅允许本地 IPC。已存在基线失败单独披露，不调整断言或扩大修复。
5. 正式库只读元数据库存和前后 hash，8524 HTTP 健康及可用界面验证分别记录；未完成浏览器 E2E 则明确未执行。

交付 Draft PR 和结果报告。独立 H 审查计划 `TASK-M3-CFFEX-RAW-PREVIEW-005-REVIEW`（待独立会话指派，绑定最终 SHA），审查权限结论、隔离边界、只读、失败路径和 UI 标识；本实现会话自检不构成独立审查，不通过生产/业务阶段验收。

## 最小授权路径（待独立批准，不在本任务执行）

提供能覆盖 2026-10-23 IF/IH/IC/IM 已存响应的用途依据，由现有治理认可的授权方明确：本地维护人员、仅 loopback、指定四份证据/hash、期限、用途、禁止研究/策略/再分发，以及是否允许未经独立来源认证的原始内容。现有契约没有该例外时，需单独 H 契约/权限任务批准及独立审查；或走现有 B07 合法 display 收据/信任根流程。不能由当前实现模型自签、从 storage 推导 display、或修改现有 allowed_uses。本任务不签发收据、不变更配置。获准后再审查并接通正式只读 Evidence/Catalog 适配器，进行 8524 真实数据验收；日历/正式结构化研究准入继续独立。
