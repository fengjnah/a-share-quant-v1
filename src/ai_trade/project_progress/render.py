"""Generate both formal Markdown views from the same validated metrics."""
from .core import calculate, dependency_failures, snapshots
from .views import recent_deliveries


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def board(data):
    result, current = calculate(data), snapshots(data)
    lines = ["# V1.3 正式任务看板", "", "<!-- Generated from TASK_METRICS.json; edit reviewed data, then --render. -->", "",
             f"数据截止：{data['updated_at']}；计划版本 {data['plan_version']}。",
             f"**按首版规划口径的已证实完成率：{result['project_percent']:.4f}%**；不是生产就绪率。",
             "", "公式：Σ阶段权重 × Σ阶段内任务权重 × Σ有类型匹配证据的 PASS 验收点权重；三层均除以 100。",
             "PLANNED/REJECTED 计零；PARTIAL/BLOCKED 仅计已有通过点。历史诊断任务权重为 0，避免反复修复增加项目分母或重复计分。",
             "未验证与失败均不计分；代码、离线、真实源、UI、独立审查、PR、生产资格分列。所有旧结果是有日期的历史证据，不代表本轮实时可用。",
             "", "模型列的指定值为唯一分配/续执行建议；actual=null 表示历史模型未知，绝不追溯伪造。实际工时未知保持 null；未来工时范围是未经实测的首版估计。",
             "SUGGESTION 表示仅建议立项，尚未创建、执行或完成；READY 只表示已经批准且依赖满足。状态来自人工快照，重算不改变状态。",
             "新模块/重要接口/依赖/高风险变更按[开源调研制度](OPEN_SOURCE_RESEARCH_POLICY.md)先检查已有研究及实际源码/测试/许可证；历史 TASK-REF-001 尚未自动获得通过结论。",
             "", "## 下一项与阻塞", ""]
    nxt = result['next']
    lines.append(f"推荐：**{nxt['id']}**（{nxt['origin']}）：{nxt['reason']}。" if nxt else "没有依赖满足的可推荐任务；先人工解除阻塞。")
    lines += ["", "## 近期交付与实际能力", "",
              "以下为当前快照引用、绑定提交的交付证据，不是新增正式任务或生产准入；原计划与权重保持不变。", ""]
    for e in recent_deliveries(data):
        lines.append(f"- {_cell(e['summary'])}（{e['id']}；提交 `{e['source_commit']}`）")
    lines += ["", "## 状态总表", "", "| TASK / 名称 | 类型/优先级 | 唯一指定模型 / 实际模型 | 估计小时 / 实际小时 | 状态 / 验收率 | 前置条件 | 审查 / PR / 生产 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for t in data['tasks']:
        e = current[t['id']]
        estimate = t['estimated_hours']
        hours = f"{estimate['low']}–{estimate['high']}" if estimate else "未知"
        deps = "; ".join(d['task'] + (":" + ",".join(d['acceptance']) if d['acceptance'] else ":全部强制") for d in t['depends_on']) or "无"
        prs = ", ".join(f"#{p['number']} {p['state']}" for p in e['prs']) or "无/未创建"
        row = [t['id']+" · "+t['title']+" ["+t['origin']+"]", t['type']+"/"+t['priority'],
               t['assigned_model']+" / "+(t['actual_model'] or '未知'), hours+" / "+str(e['actual_hours'] if e['actual_hours'] is not None else '未知'),
               e['state']+f" / {result['task_percent'][t['id']]:g}%", deps, e['review']['status']+" / "+prs+" / "+e['production']['status']]
        lines.append("| "+" | ".join(_cell(v) for v in row)+" |")
    lines += ["", "## 逐项目标与验收", ""]
    for t in data['tasks']:
        e = current[t['id']]
        lines += [f"### {t['id']} · {t['title']}", "", f"目标：{t['goal']}。阶段 {t['stage']}；阶段内权重 {t['weight']}%。",
                  f"结果依据：{e['reason']}（{e['at']}）；快照序号 {e['seq']}。", "",
                  "| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |", "| --- | --- | --- | --- | --- |"]
        for a in t['acceptance']:
            r = e['results'][a['id']]
            lines.append(f"| {a['id']} · {_cell(a['label'])} | {a['weight']}% | {a['mandatory']} | {r['status']} | {', '.join(r['evidence']) or '无'} |")
        blockers = e['blockers'] + dependency_failures(t, current)
        children = [v['id'] for v in data['tasks'] if any(d['task'] == t['id'] for d in v['depends_on'])]
        lines += ["", "阻塞："+_cell("；".join(blockers) or "无已记录阻塞；未通过验收点仍须完成。"),
                  "后续候选（仍须满足其全部依赖）："+(", ".join(children) or "按路线图人工规划，不自动创建。"), ""]
    lines += ["## 证据登记", "", "| ID / 类型 | 固定来源 | 摘要及边界 |", "| --- | --- | --- |"]
    for e in data['evidence']:
        lines.append(f"| {e['id']} / {e['kind']} | {_cell(e['ref'])} | {_cell(e['summary'])}；SHA256 {e['sha256']} |")
    lines += ["", "## 反馈与重算操作", "", "使用 `python -m ai_trade.project_progress --check-docs` 验证 JSON Schema、权重、依赖图、事件链和两份 Markdown 一致性。",
              "`python -m ai_trade.project_progress` 只读重算，退出码 0 仅代表管理数据合法，不代表业务通过。",
              "手工结束任务后，将完整新快照及新证据写入 feedback.json，使用 `--propose feedback.json --candidate <新路径>` 生成独占候选文件；不改变正式 TASK_METRICS 或任何状态。",
              "审查差异并通过独立 PR 接纳候选，保留旧 events/evidence 为完全相同前缀；再显式 `--render` 生成两个 Markdown。权重/任务定义/验收门槛变更需独立计划修订及审查，不由反馈命令放宽。",
              "使用 `--baseline <可信旧版 TASK_METRICS.json>` 核对历史前缀；仅哈希链不能防止整链被重算，没有可信旧版时仍必须审查 Git diff。计划修订需在单独人工 PR 中保留旧计划/Git SHA 和审查依据；普通反馈入口只允许同版本追加。",
              "候选反馈结构为 `{\"event\": <完整快照，不含 seq/hash/previous_hash>, \"new_evidence\": [...]}`；可从最新对应快照复制，填写 at/state/results/blockers/reason/basis/工时/审查/PR/生产，不复用未适用的通过证据。",
              "只读 `--simulate TASK-ID ACCEPTANCE-ID FAIL` 展示验收点失败后的分数和下游阻塞，不写文件或发网络。新证据需记录来源、SHA256、类型、时点和适用范围；证据内容真实性仍需人工/独立审查，Schema 不是真实性认证。",
              "未知模型/工时/许可证/真实可用性不会自动补齐，GitHub 不会被页面后台轮询。首版阶段和任务分配是规划参数，不是开发耗时或收益预测。", ""]
    lines += ["文本证据新 SHA256 按 UTF-8 LF 计算；既有 Windows CRLF 哈希的明确 ID 清单见 [TASK_018_HASH_FORMAT](evidence/TASK_018_HASH_FORMAT.json)，核验时只重建已记录换行，不忽略其他字节。", ""]
    return "\n".join(lines)


def roadmap(data):
    result, current = calculate(data), snapshots(data)
    lines = ["# A股量化系统 V1.3 路线图", "", "<!-- Generated from TASK_METRICS.json; edit reviewed data, then --render. -->", "",
             f"计划 {data['plan_version']}；截止 {data['updated_at']}。十阶段总权重 100%；源数据是 TASK_METRICS.json。",
             "治理 10%=S1 4%+S2 6%；数据可靠性 25%=S3 8%+S4 17%；市场/选股 20%=S5 8%+S6 12%；风险 S7 10%、回测 S8 20%、日报 S9 10%、最终准入 S10 5%。",
             "这些是首版规划分配；没有工时/业务收益实测校准，不声称百分比是客观软件完成度。调整须保留旧计划依据、独立审查并解释前后数值，不能为了升分降低门槛。", ""]
    lines += ["阶段依赖描述整体验收顺序；必要的基础审查可并行。具体任务启动只按显式 TASK 验收点依赖判断，不因阶段编号较早就推定其通过。新模块调研按 [OPEN_SOURCE_RESEARCH_POLICY](OPEN_SOURCE_RESEARCH_POLICY.md)执行。", ""]
    for s in data['stages']:
        lines += [f"## {s['id']} {s['name']}（{s['weight']}%）", "", "阶段依赖："+(", ".join(s['depends_on']) or "无")+"。",
                  f"交付：{s['deliverables']}。", f"退出条件：{s['exit_condition']}。", f"已证实验收进度：{result['stage_percent'][s['id']]:g}%。", "",
                  "| TASK | 状态 | 来源 | 前置验收 |", "| --- | --- | --- | --- |"]
        for t in data['tasks']:
            if t['stage'] == s['id']:
                deps = "; ".join(d['task']+":"+(",".join(d['acceptance']) or "全部强制") for d in t['depends_on']) or "无"
                lines.append(f"| {t['id']} | {current[t['id']]['state']} | {t['origin']} | {deps} |")
        lines.append("")
    lines += ["建议立项不代表任务已经创建。正式策略回测必须通过数据时点、主数据/日历/复权、执行约束及独立未来函数门禁；默认不发真实请求、不部署或接交易账户。", ""]
    return "\n".join(lines)
