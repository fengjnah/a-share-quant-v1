"""Read-only Streamlit page; imports neither market adapters nor SQLite."""
import streamlit as st

from .core import METRICS, PlanError, calculate, dependency_failures, load, snapshots
from .views import recent_deliveries, task_rows


def render():
    st.title("项目进度")
    st.caption("A股量化系统 V1.3 · 只读看板 · 不采集行情、不创建数据库")
    try:
        data = load()
        result, current = calculate(data), snapshots(data)
    except (PlanError, OSError) as exc:
        st.error(f"任务数据无效，未显示伪造的完成率：{exc}")
        st.stop()
    st.metric("有证据的加权完成率", f"{result['project_percent']:.4f}%")
    st.caption(f"强制验收通过 {result['state_counts']['PASS']} / {len(data['tasks'])} 项 · 阻塞或依赖缺口 {len(result['blockers'])} 项")
    st.info("正式验收进度，不是生产就绪率。研究 Demo 单独展示；未知、失败和未执行项不计分。")
    st.caption(f"数据截止：{data['updated_at']} · 计划 {data['plan_version']}")
    with st.expander("数据版本与计算依据"):
        st.write("依据 main：", data['baseline'])
        st.write("阶段权重 × 阶段内任务权重 × 通过验收点权重；代码、测试、独立审查、合并和生产准入分列。")
    st.subheader("近期交付与实际能力")
    deliveries = recent_deliveries(data)
    if not deliveries:
        st.info("暂无当前快照引用、绑定提交的交付记录；不从任务名称推断能力。")
    for evidence in deliveries:
        with st.container(border=True):
            title, separator, body = evidence['summary'].partition(' · ')
            if separator:
                st.markdown(f"**{title}**")
                st.markdown(body)
            else:
                st.markdown(title)
            st.caption(f"证据 {evidence['id']} · 提交 {evidence['source_commit'][:12]} · 记录 {evidence['recorded_at']}")
    st.caption("交付证据不会自动增加正式计划分母或权重，也不替代独立审查、历史覆盖或生产授权。详见任务详情和原始证据。")
    nxt = result['next']
    if nxt:
        st.success(f"推荐下一项：{nxt['id']} · {nxt['title']}")
        st.write(nxt['reason'])
        if nxt['origin'] == 'SUGGESTION':
            st.warning("仅建议立项，尚未创建或执行；建议本身不会改变任务状态。")
    else:
        st.warning("没有前置条件满足的候选任务；先人工处理阻塞。")
    st.subheader("阶段进度")
    for s in data['stages']:
        value = result['stage_percent'][s['id']]
        st.progress(value/100, text=f"{s['id']} {s['name']} · 权重 {s['weight']}% · 已证实 {value:g}%")
    st.subheader("TASK 状态分布")
    st.bar_chart(result['state_counts'], use_container_width=True)
    st.subheader("正式任务总览")
    st.caption("未单列表示原任务没有此类独立验收项；不是通过。仅建议立项的任务仍保持 PLANNED。")
    filters = st.columns(2)
    states = filters[0].multiselect("按状态筛选", list(result['state_counts']), key="progress_states")
    stages = filters[1].multiselect("按阶段筛选", [s['id'] for s in data['stages']], key="progress_stages")
    query = st.text_input("搜索 TASK 或名称", key="progress_search").strip().casefold()
    rows = [r for r in task_rows(data, result)
            if (not states or r['状态'] in states) and (not stages or r['阶段'] in stages)
            and (not query or query in (r['TASK'] + ' ' + r['名称']).casefold())]
    st.caption(f"显示 {len(rows)} / {len(data['tasks'])} 项；筛选只改变展示，不改变完成率。")
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("没有符合筛选条件的任务。可清空筛选后查看全部任务。")
    options = [t['id'] for t in data['tasks']]
    selected = st.selectbox("任务详情", options)
    task = next(t for t in data['tasks'] if t['id'] == selected)
    event = current[selected]
    st.write(task['title'], " · ", event['state'], " · ", task['origin'])
    st.write("目标：", task['goal'])
    st.write("唯一指定模型：", task['assigned_model'], task['assigned_effort'],
             "；分配依据：", task['model_assignment'], "；历史实际模型：", task['actual_model'] or '未知')
    st.caption(task['model_basis'])
    st.write("估计工时：", task['estimated_hours'] or '未知', "；实际小时：", event['actual_hours'] if event['actual_hours'] is not None else '未知')
    st.write("独立审查：", event['review']['status'], "；生产准入：", event['production']['status'])
    st.write("PR（独立记录）：", event['prs'] or '无 / 尚未创建')
    st.dataframe([{"验收点":a['label'],"权重":a['weight'],"强制":a['mandatory'],
                   "结果":event['results'][a['id']]['status'],
                   "证据":', '.join(event['results'][a['id']]['evidence']) or '无'} for a in task['acceptance']],
                 hide_index=True, use_container_width=True)
    st.write("最近更新依据：", event['at'], event['reason'], "；证据 ID：", event['basis'])
    with st.expander("查看本任务最近更新证据"):
        for evidence in data['evidence']:
            if evidence['id'] in event['basis']:
                st.write(evidence['id'], ' · ', evidence['kind'], ' · ', evidence['summary'])
                st.caption(f"{evidence['ref']} · SHA256 {evidence['sha256']} · 依据提交 {evidence['source_commit'] or '未记录'}")
    missing = dependency_failures(task, current)
    if missing:
        st.warning("当前前置条件缺口（不篡改旧验收记录）："+'；'.join(missing))
    st.subheader("当前阻塞与未满足依赖")
    if not result['blockers']:
        st.info("没有已记录阻塞；未验证验收点仍不能视为通过。")
    for item in result['blockers']:
        st.write(item['id'], '；'.join(item['reasons']+item['dependencies']))
    with st.expander("计算口径、更新方法与证据边界"):
        st.write(data['weight_basis'])
        st.code("python -m ai_trade.project_progress --check-docs\npython -m ai_trade.project_progress --simulate TASK-002 offline FAIL")
        st.write("人工反馈 → --propose 生成新候选 → 审查独立 PR → --render；正式状态不会由页面、测试或 GitHub 自动更新。")
        st.write("低风险边界明确任务可提议 Agnes 3.0 Flash；时点、Schema、未来函数及独立审查指定 GPT-6.1 Sol / High。提议型号不证明已可用；历史未知型号不补造。")
        st.caption(str(METRICS))
