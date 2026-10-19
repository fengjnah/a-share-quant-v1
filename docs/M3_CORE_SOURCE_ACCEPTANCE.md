# TASK-M3-CORE-001：真实来源与覆盖验收

2026-10-19 UTC 执行；不沿用旧任务的通过状态。离线夹具、真实来源、UI、样本外及独立审查分列。数据公开可获取不等于研究/自动采集/存储/商业/公开展示/再分发已授权，以上用途的源条款均保持 UNKNOWN，不能用 SDK MIT 代替。

## 实际受限请求

命令：`python scripts/verify_m3_sources.py --enable-live --output-dir artifacts/m3-core-001 --cffex-date 2026-10-16`，退出0表示报告生成，**不是所有源成功**。每源一次、0重试，正常代理解析，TLS verify=true；SDK连接/读取5/8秒，worker总限30秒、8MB；CFFEX5/5秒、2MB。禁止重定向/换源，未关闭证书校验，未改系统代理。原始观察仅本机忽略目录 `artifacts/m3-core-001/m3-observations/`，不提交。

脱敏机器证据：[TASK_M3_CORE_001_SOURCES.json](evidence/TASK_M3_CORE_001_SOURCES.json)。起始2026-10-19T15:53:59.862900Z；指数观察15:54:06.478989Z、实际本机入库15:54:06.596523Z。此入库是观察文件采集流程的真实系统时点，**不是历史首次发布/可得时点**，不涉及SQLite。

| 来源 / 请求 | 实际结果、日期、数量及字段 | 历史/时点/授权限制 |
| --- | --- | --- |
| 新浪，经AKShare1.19.1 `stock_zh_index_daily(sh000300)`；`https://finance.sina.com.cn/realstock/company/sh000300/hisdata/klc_kl.js`，固定SDK参数d=2020_2_4 | HTTP200，一次；保留550日，2024-07-09～2026-10-16；date/open/high/low/close（SDK另有volume，本次未作为指标因子）。响应SHA256见JSON | 此端点返回单指数历史载荷，客户端解码后截取550条，不能宣称服务器只返回550行。未核验权威日历分母、逐日历史发布/可得时点或完整复权元数据；无成交额/全A历史因子。不能历史回放到本次采集前 |
| 乐咕，经固定SDK `stock_market_activity_legu()`；`https://legulegu.com/stockdata/market-activity` | 一次；ReadTimeout，HTTP状态未获得；0个已验收快照 | 原函数字段为上涨/下跌/平盘/涨停/跌停/统计日期；本次未收到，不能报告真实家数。即使成功也只有当日聚合，无历史实体股票池分母、停牌/缺失分区和全A额，不回填历史 |
| CFFEX，既有adapter；`https://www.cffex.com.cn/sj/ccpm/202610/16/IF_1.csv` | 一次；RankingTransportError，链内SSLError；HTTP状态未获得；0已验收行 | 只覆盖本次IF/2026-10-16尝试；IH/IC/IM未请求。无可用于本轮验收的真实会员/合约行，日历、发布时点、scope及授权未认证；不输出综合方向 |

响应失败不解释为休市/无持仓/没有交易；TLS失败不代表数据不存在。下步最小操作是核实运行环境可信证书链及源访问条件，再单独授权定向请求；当前预算不重试、不绕过TLS、不换代理。

## 各指标结论

| 指标 | 本轮真实计算/覆盖 | 准入 |
| --- | --- | --- |
| 指数趋势 | 真实550行，MA20/60公式可计算，实际截止10-16 | L1，TIME_UNCERTIFIED；来源认证/授权/日历/价格口径仍未完成 |
| 周线 | 可聚合116个已结束周（原始请求排除不完整首周及分析日所在周） | L1；周内完整性分母 UNKNOWN，不宣称全历史完整 |
| 波浪/转折 | 真实价格上可复现右3条确认候选；first_usable_at未认证处null | L1；研究解释，不是已验证反转或策略信号 |
| 价格行为代理 | 前3价格因子具备公式历史；单独返回，与完整分数分离 | L1实验性观察；不是六因子完整分数 |
| 完整恐贪及分位 | 缺全A上涨/涨停比例与全A成交额历史，完整score=null，完整分位null | L1诊断，FACTOR_MISSING；不得用价格代理冒充完整分数 |
| 全A宽度 | 本轮超时；既有源也缺当日历史池分母/身份/分区认证 | ENV_BLOCKED/UNKNOWN；仅离线规则测试通过 |
| CFFEX | 本轮TLS失败，无可认证记录 | ENV_BLOCKED；净仓/换月隔离规则只做离线验证，综合方向null |
| 综合环境 / L3 | 三类研究级证据不齐；无真实L2/L3、无样本外及执行审查 | 数据不足；不能将单项L1升级为研究/策略/实盘 |

未新增UI：本地UI端到端 NOT_RUN；旧M3显示结果不是本轮接口验收。样本外回测 NOT_RUN。生产/EC2/真实账户 NOT_RUN。完整离线结果和H审查门禁见[任务记录](tasks/TASK-M3-CORE-001.md)。

## 有界开源参考（只借鉴思想，不复制/安装框架）

用户明确要求可参考GitHub减少重复工作。本轮仅两个候选，读取默认分支一次并冻结SHA；分别读README、直接相关模块、相关测试及许可证，到此停止，不扩展项目列表。外部测试均仅阅读，**未执行**；未实测其数据/性能/授权能力。

| 项目 / 固定SHA / 许可证 | 实际阅读及与本项目差异 | 决定 |
| --- | --- | --- |
| microsoft/qlib `54355232463878d2eebb91fe0ee5fa7fa1f5976c`；LICENSE MIT | [README](https://github.com/microsoft/qlib/blob/54355232463878d2eebb91fe0ee5fa7fa1f5976c/README.md)、[check_data_health.py](https://github.com/microsoft/qlib/blob/54355232463878d2eebb91fe0ee5fa7fa1f5976c/scripts/check_data_health.py)、[test_dump_data.py](https://github.com/microsoft/qlib/blob/54355232463878d2eebb91fe0ee5fa7fa1f5976c/tests/test_dump_data.py)、[LICENSE](https://github.com/microsoft/qlib/blob/54355232463878d2eebb91fe0ee5fa7fa1f5976c/LICENSE)。缺字段/null/日期集合检查与本项目已有验证相近；该检查器不是本项目as_of或权威日历认证 | 采用分项缺失诊断思想；拒绝引入数据下载、模型训练/回测框架及容忍缺失阈值。复用本地ReferenceResult和CFFEX更严格时点端口 |
| unionai-oss/pandera `50f9e62bd0e54920fa44e1cc7580a4cfe9b7157e`；LICENSE.txt MIT | [README](https://github.com/unionai-oss/pandera/blob/50f9e62bd0e54920fa44e1cc7580a4cfe9b7157e/README.md)、[error_handler.py](https://github.com/unionai-oss/pandera/blob/50f9e62bd0e54920fa44e1cc7580a4cfe9b7157e/pandera/api/base/error_handler.py)、[test_errors.py](https://github.com/unionai-oss/pandera/blob/50f9e62bd0e54920fa44e1cc7580a4cfe9b7157e/tests/pandas/test_errors.py)、[LICENSE.txt](https://github.com/unionai-oss/pandera/blob/50f9e62bd0e54920fa44e1cc7580a4cfe9b7157e/LICENSE.txt)。按原因/字段汇总失败，本项目已有jsonschema依赖 | 适配机器原因码+缺失字段+多项问题保留的接口思想；不新增依赖，不自动coerce/drop不合格行，不把schema通过当来源认证 |

未直接引入外部源码或传递依赖；软件许可读取仅覆盖以上文件和本任务触达的固定AKShare源，不声称全量法律审计。研究采用决定与新时点接口一起待独立H审查。

固定AKShare1.19.1实际读取：`index/index_stock_zh.py` SHA256 `fc217076e71ce6a4a70f8344de0f4c0332b4b4cfa77a71e2ca3bc8a428e39d0a`，`index/cons.py` `b2cb71be1b5d1b79b68a722113681e6599c7a8d2d7acae86ba172a7c8ff313a4`，`stock_feature/stock_market_legu.py` `ea07f4f3ac82c1cf2febf93f23b20d34ea5a3f45f44e82f888e667af0c25323e`，dist-info `licenses/LICENSE` MIT `d1c84fbaccd5fdbc75cd12ab9a05f4f791d89ee266569bc976c8b0befafc2d65`。仅人工核验这两个函数/常量/软件许可证，不认证供应商数据条款。
